from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.v1_init.helpers import (
    TELEGRAM_GROUP,
    get_telegram_config,
)
from api.v1.v1_init.models import SystemSetting
from api.v1.v1_init.serializers import (
    TelegramSettingsSerializer,
)


@extend_schema(
    description="Use to check System health",
    tags=["Dev"],
)
@api_view(["GET"])
def health_check(request, version):
    return Response(
        {"message": "OK"}, status=status.HTTP_200_OK
    )


@extend_schema(
    request=TelegramSettingsSerializer,
    responses=TelegramSettingsSerializer,
    tags=["Settings"],
)
@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def telegram_settings(request, version):
    if request.method == "GET":
        config = get_telegram_config()
        return Response(config)

    serializer = TelegramSettingsSerializer(
        data=request.data
    )
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    for key, value in data.items():
        if key == "enabled":
            value = str(value)
        SystemSetting.objects.update_or_create(
            group=TELEGRAM_GROUP,
            key=key,
            defaults={"value": value},
        )

    config = get_telegram_config()
    return Response(config)
