from datetime import datetime
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_users.models import SystemUser
from api.v1.v1_users.serializers import (LoginResponseSerializer,
                                         LoginSerializer, UpdateUserSerializer,
                                         UserSerializer)
from utils.custom_serializer_fields import validate_serializers_message
from utils.default_serializers import DefaultResponseSerializer
from utils.encryption import encrypt
from utils.kobo_client import KoboClient


@extend_schema(
    request=LoginSerializer,
    responses={
        200: LoginResponseSerializer,
        401: DefaultResponseSerializer,
    },
    tags=["Auth"],
)
@api_view(["POST"])
def login(request, version):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    kobo_url = serializer.validated_data["kobo_url"]
    kobo_username = serializer.validated_data["kobo_username"]
    kobo_password = serializer.validated_data["kobo_password"]

    # Validate credentials against KoboToolbox API
    client = KoboClient(kobo_url, kobo_username, kobo_password)
    if not client.verify_credentials():
        return Response(
            {"message": ("Invalid KoboToolbox credentials")},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Create or update SystemUser
    host = urlparse(kobo_url).hostname
    user, _ = SystemUser.objects.update_or_create(
        kobo_username=kobo_username,
        kobo_url=kobo_url,
        defaults={
            "name": kobo_username,
            "email": f"{kobo_username}@{host}.local",
            "kobo_password": encrypt(kobo_password),
        },
    )
    user.last_login = timezone.now()
    user.save()

    refresh = RefreshToken.for_user(user)
    expiration_time = datetime.fromtimestamp(refresh.access_token["exp"])
    expiration_time = timezone.make_aware(expiration_time)

    data = {
        "user": UserSerializer(instance=user).data,
        "token": str(refresh.access_token),
        "expiration_time": expiration_time,
    }
    response = Response(data, status=status.HTTP_200_OK)
    response.set_cookie(
        "AUTH_TOKEN",
        str(refresh.access_token),
        expires=expiration_time,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )
    return response


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: UserSerializer},
        tags=["Users"],
        summary="Get user profile",
    )
    def get(self, request, version):
        return Response(
            UserSerializer(instance=request.user).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=UpdateUserSerializer,
        responses={200: UserSerializer, 400: DefaultResponseSerializer},
        tags=["Users"],
        summary="Update user profile",
    )
    def put(self, request, version):
        serializer = UpdateUserSerializer(
            instance=request.user, data=request.data
        )
        if not serializer.is_valid():
            return Response(  # pragma: no cover
                {"message": validate_serializers_message(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = serializer.save()
        return Response(
            UserSerializer(instance=user).data, status=status.HTTP_200_OK
        )
