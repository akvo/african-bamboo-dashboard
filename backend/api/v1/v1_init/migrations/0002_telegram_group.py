import os
import sys

from django.db import migrations, models

TELEGRAM_GROUP = "telegram"
# (SystemSetting key, env var) in the order the old
# _telegram_targets sent to them.
GROUP_KEYS = (
    ("supervisor_group_id", "TELEGRAM_SUPERVISOR_GROUP_ID"),
    ("enumerator_group_id", "TELEGRAM_ENUMERATOR_GROUP_ID"),
)


def carry_over(apps, environ):
    """Turn the ids in effect today into All-regions rows.

    A non-blank DB value wins over the env var, matching
    the old get_telegram_config fallback. environ, not
    settings: the settings attributes are removed in the
    same change (spec D-5).
    """
    SystemSetting = apps.get_model("v1_init", "SystemSetting")
    TelegramGroup = apps.get_model("v1_init", "TelegramGroup")
    rows = SystemSetting.objects.filter(
        group=TELEGRAM_GROUP,
        key__in=[key for key, _ in GROUP_KEYS],
    )
    db = {s.key: s.value.strip() for s in rows}
    for key, env_name in GROUP_KEYS:
        chat_id = db.get(key) or environ.get(env_name, "").strip()
        if chat_id:
            TelegramGroup.objects.get_or_create(chat_id=chat_id)
    rows.delete()


def forwards(apps, schema_editor):
    # ponytail: the test runner migrates a fresh test DB with
    # the developer's .env loaded; carrying those ids over
    # would put a group row under every test. Tests call
    # carry_over directly instead.
    if "test" in sys.argv:
        return
    carry_over(apps, os.environ)


def backwards(apps, schema_editor):
    """Write the first two rows back to the role keys.

    Region scopes are lost -- acceptable for a feature
    rollback.
    """
    SystemSetting = apps.get_model("v1_init", "SystemSetting")
    TelegramGroup = apps.get_model("v1_init", "TelegramGroup")
    groups = TelegramGroup.objects.order_by("pk")[:2]
    for (key, _), group in zip(GROUP_KEYS, groups):
        SystemSetting.objects.update_or_create(
            group=TELEGRAM_GROUP,
            key=key,
            defaults={"value": group.chat_id},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("v1_init", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TelegramGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "chat_id",
                    models.CharField(max_length=64, unique=True),
                ),
                (
                    "title",
                    models.CharField(blank=True, max_length=255),
                ),
                (
                    "regions",
                    models.JSONField(blank=True, default=list),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
            ],
        ),
        migrations.RunPython(forwards, backwards),
    ]
