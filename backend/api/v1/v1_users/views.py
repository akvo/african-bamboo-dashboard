from datetime import datetime

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    PendingLoginResponseSerializer,
    UpdateUserSerializer,
    UserSerializer,
)
from api.v1.v1_users.services.approval import bind_pending_login
from utils.custom_serializer_fields import (
    validate_serializers_message,
)
from utils.default_serializers import DefaultResponseSerializer
from utils.encryption import encrypt
from utils.kobo_client import KoboClient

_PENDING_MESSAGES = {
    UserStatus.PENDING: (
        "Your access is awaiting administrator approval."
    ),
    UserStatus.SUSPENDED: "Access denied.",
}


@extend_schema(
    request=LoginSerializer,
    responses={
        200: LoginResponseSerializer,
        400: DefaultResponseSerializer,
        401: DefaultResponseSerializer,
        403: PendingLoginResponseSerializer,
    },
    tags=["Auth"],
)
@api_view(["POST"])
def login(request, version):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "message": validate_serializers_message(
                    serializer.errors
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    kobo_url = serializer.validated_data["kobo_url"]
    kobo_username = serializer.validated_data["kobo_username"]
    kobo_password = serializer.validated_data["kobo_password"]

    client = KoboClient(kobo_url, kobo_username, kobo_password)
    user_detail = client.verify_credentials()
    if not user_detail:
        return Response(
            {"message": "Invalid KoboToolbox credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    name_from_kobo = None
    email_from_kobo = None
    if isinstance(user_detail, dict):
        name_from_kobo = user_detail.get("name") or None
        email_from_kobo = user_detail.get("email") or None

    email_was_synthesized = email_from_kobo is None
    if email_was_synthesized:
        host = kobo_url.split("//")[-1].split("/")[0]
        email_from_kobo = f"{kobo_username}@{host}"

    user, _ = bind_pending_login(
        email_from_kobo=email_from_kobo,
        kobo_username=kobo_username,
        kobo_url=kobo_url,
        encrypted_password=encrypt(kobo_password),
        name_from_kobo=name_from_kobo,
        email_was_synthesized=email_was_synthesized,
    )

    if user.status != UserStatus.ACTIVE or not user.is_active:
        return Response(
            {
                "message": _PENDING_MESSAGES.get(
                    user.status, "Access denied."
                ),
                "status": UserStatus.fieldStr.get(
                    user.status, "suspended"
                ),
                "email": user.email,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    refresh = RefreshToken.for_user(user)
    expiration_time = datetime.fromtimestamp(
        refresh.access_token["exp"]
    )
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
        responses={
            200: UserSerializer,
            400: DefaultResponseSerializer,
        },
        tags=["Users"],
        summary="Update user profile",
    )
    def put(self, request, version):
        serializer = UpdateUserSerializer(
            instance=request.user, data=request.data
        )
        if not serializer.is_valid():
            return Response(  # pragma: no cover
                {
                    "message": validate_serializers_message(
                        serializer.errors
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = serializer.save()
        return Response(
            UserSerializer(instance=user).data,
            status=status.HTTP_200_OK,
        )
