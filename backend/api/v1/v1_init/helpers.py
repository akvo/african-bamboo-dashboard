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
        if key in db_settings:
            val = db_settings[key]
            if key == "enabled":
                val = val.lower() in (
                    "true",
                    "1",
                    "yes",
                )
            config[key] = val
        else:
            config[key] = default_fn()

    return config
