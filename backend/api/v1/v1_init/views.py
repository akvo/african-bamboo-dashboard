import logging

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
from utils.telegram_client import (
    TelegramClient,
    TelegramSendError,
)

logger = logging.getLogger(__name__)


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
            value = str(bool(value)).lower()
        # Clearing a field means "unset" — delete the
        # row so get_telegram_config falls back to the
        # env default instead of being shadowed by "".
        if not str(value).strip():
            SystemSetting.objects.filter(
                group=TELEGRAM_GROUP, key=key
            ).delete()
            continue
        SystemSetting.objects.update_or_create(
            group=TELEGRAM_GROUP,
            key=key,
            defaults={"value": value},
        )

    config = get_telegram_config()
    return Response(config)


@extend_schema(
    description=(
        "Fetch Telegram groups visible to the bot"
    ),
    tags=["Settings"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def telegram_groups(request, version):
    config = get_telegram_config()
    bot_token = (
        request.query_params.get("bot_token")
        or config.get("bot_token")
    )
    if not bot_token:
        return Response(
            {"detail": "No bot token configured"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    client = TelegramClient(bot_token)

    # getUpdates is DISCOVERY only: it sees just the
    # last 24h of activity and a bot's own messages
    # generate no updates, so the list empties itself
    # after a quiet day. That is why a configured group
    # used to render as a bare chat id.
    discovery_error = None
    try:
        groups = client.get_groups()
    except TelegramSendError as e:
        logger.warning(
            "Telegram getUpdates failed: %s", e
        )
        groups = []
        discovery_error = str(e)

    # Configured ids are resolved with getChat, which
    # is authoritative and permanent.
    by_id = {g["id"]: g for g in groups}
    resolved_any = False
    for key in (
        "supervisor_group_id",
        "enumerator_group_id",
    ):
        chat_id = config.get(key)
        if not chat_id or chat_id in by_id:
            continue
        try:
            chat = client.get_chat(chat_id)
            # Only ever hand the renderer a plain dict of the
            # three fields we use. Anything else is a bug in
            # the client, and letting it reach the JSON
            # encoder turns that bug into an unbounded
            # allocation rather than a clear error.
            if not isinstance(chat, dict):
                raise TelegramSendError(
                    f"getChat returned {type(chat).__name__}, "
                    f"expected dict"
                )
            by_id[chat_id] = {
                "id": str(chat.get("id", chat_id)),
                "title": chat.get("title", "Untitled"),
                "type": chat.get("type", ""),
            }
            resolved_any = True
        except TelegramSendError as e:
            # One unreachable chat must not empty the
            # whole list.
            logger.warning(
                "Telegram getChat failed for %s: %s",
                chat_id,
                e,
            )

    if discovery_error and not resolved_any:
        return Response(
            {"detail": discovery_error},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    return Response(list(by_id.values()))
