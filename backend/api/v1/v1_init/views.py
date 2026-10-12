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
from api.v1.v1_init.models import SystemSetting, TelegramGroup
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

    # Every configured row is resolved with getChat, which
    # is authoritative and permanent, and its cached title
    # refreshed so the settings table renders offline.
    by_id = {g["id"]: g for g in groups}
    resolved_any = False
    for row in TelegramGroup.objects.order_by("pk"):
        try:
            chat = client.get_chat(row.chat_id)
            # get_chat returns the normalised {id, title, type}
            # dict. Anything else is a bug in the client, and
            # letting it reach the JSON encoder turns that bug
            # into an unbounded allocation rather than a clear
            # error.
            if not isinstance(chat, dict):
                raise TelegramSendError(
                    f"getChat returned {type(chat).__name__}, "
                    f"expected dict"
                )
        except TelegramSendError as e:
            # One unreachable chat must not empty the
            # whole list.
            logger.warning(
                "Telegram getChat failed for %s: %s",
                row.chat_id,
                e,
            )
            continue
        title = chat["title"]
        by_id[row.chat_id] = chat
        resolved_any = True
        if row.title != title:
            row.title = title
            row.save(update_fields=["title", "updated_at"])

    if discovery_error and not resolved_any:
        return Response(
            {"detail": discovery_error},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    for group in by_id.values():
        try:
            count = client.get_chat_member_count(group["id"])
        except TelegramSendError as e:
            logger.warning(
                "Telegram getChatMemberCount failed for "
                "%s: %s",
                group["id"],
                e,
            )
            count = None
        # Same guard as getChat: only a plain int may
        # reach the encoder.
        group["member_count"] = (
            count if isinstance(count, int) else None
        )
    return Response(list(by_id.values()))
