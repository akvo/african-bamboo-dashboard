from django.conf import settings

from api.v1.v1_init.models import SystemSetting

TELEGRAM_GROUP = "telegram"

TELEGRAM_DEFAULTS = {
    "enabled": lambda: settings.TELEGRAM_ENABLED,
    "bot_token": lambda: settings.TELEGRAM_BOT_TOKEN,
    "supervisor_group_id": (
        lambda: settings.TELEGRAM_SUPERVISOR_GROUP_ID
    ),
    "enumerator_group_id": (
        lambda: settings.TELEGRAM_ENUMERATOR_GROUP_ID
    ),
}


def get_telegram_config():
    """Read Telegram config from DB, falling back
    to env-var defaults from settings.py."""
    db_settings = {
        s.key: s.value
        for s in SystemSetting.objects.filter(
            group=TELEGRAM_GROUP
        )
    }

    config = {}
    for key, default_fn in TELEGRAM_DEFAULTS.items():
        # A blank DB value means "unset", not
        # "empty string". Treating it as a value
        # would let one save of the settings tab
        # permanently shadow the env fallback.
        raw = (db_settings.get(key) or "").strip()
        if not raw:
            config[key] = default_fn()
        elif key == "enabled":
            config[key] = raw.lower() in (
                "true",
                "1",
                "yes",
            )
        else:
            config[key] = raw

    return config


def migrate_telegram_group_id(old_chat_id, new_chat_id):
    """Repoint any group setting matching old_chat_id.

    Telegram issues a brand new id when a basic group is
    upgraded to a supergroup, and every send to the old
    id fails permanently from that moment. Persisting
    the replacement is the difference between a blip and
    a total outage of the feature.

    Returns the setting keys that were updated.
    """
    config = get_telegram_config()
    updated = []
    for key in (
        "supervisor_group_id",
        "enumerator_group_id",
    ):
        if str(config.get(key)) != str(old_chat_id):
            continue
        SystemSetting.objects.update_or_create(
            group=TELEGRAM_GROUP,
            key=key,
            defaults={"value": str(new_chat_id)},
        )
        updated.append(key)
    return updated
