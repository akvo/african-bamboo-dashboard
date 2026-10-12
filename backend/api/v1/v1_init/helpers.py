from django.conf import settings

from api.v1.v1_init.models import SystemSetting, TelegramGroup

TELEGRAM_GROUP = "telegram"

TELEGRAM_DEFAULTS = {
    "enabled": lambda: settings.TELEGRAM_ENABLED,
    "bot_token": lambda: settings.TELEGRAM_BOT_TOKEN,
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
    """Repoint the group row matching old_chat_id.

    Telegram issues a brand new id when a basic group is
    upgraded to a supergroup, and every send to the old
    id fails permanently from that moment. Persisting
    the replacement is the difference between a blip and
    a total outage of the feature.

    chat_id is unique, so when the new id is already a
    row the two are merged: the old row's regions are
    folded in and [] (all regions) wins.
    """
    old = TelegramGroup.objects.filter(
        chat_id=str(old_chat_id)
    ).first()
    if old is None:
        return
    new = TelegramGroup.objects.filter(
        chat_id=str(new_chat_id)
    ).first()
    if new is None:
        old.chat_id = str(new_chat_id)
        old.save(update_fields=["chat_id", "updated_at"])
        return
    new.regions = (
        list(dict.fromkeys(new.regions + old.regions))
        if old.regions and new.regions
        else []
    )
    new.save(update_fields=["regions", "updated_at"])
    old.delete()
