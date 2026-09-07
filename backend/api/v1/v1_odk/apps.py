import logging

from django.apps import AppConfig
from django.conf import settings
from django.db import DatabaseError
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)

TELEGRAM_SWEEP_NAME = "telegram_retry_sweep"
TELEGRAM_SWEEP_FUNC = (
    "api.v1.v1_odk.tasks"
    ".retry_pending_telegram_notifications"
)


def register_telegram_sweep(sender, **kwargs):
    """Create or re-tune the delivery retry schedule.

    Registered unconditionally -- never gated on the
    "enabled" toggle. That setting is runtime state, so
    a conditional registration would mean switching
    Telegram on later leaves no sweeper and no retries,
    silently. The task itself short-circuits when the
    integration is off.
    """
    if getattr(settings, "TEST_ENV", False):
        return

    from django_q.models import Schedule

    minutes = settings.TELEGRAM_RETRY_COOLDOWN_MINUTES
    try:
        Schedule.objects.update_or_create(
            name=TELEGRAM_SWEEP_NAME,
            defaults={
                "func": TELEGRAM_SWEEP_FUNC,
                "schedule_type": Schedule.MINUTES,
                "minutes": minutes,
                "repeats": -1,
            },
        )
    except DatabaseError:
        logger.exception(
            "Could not register the %s schedule — "
            "undelivered Telegram notifications will "
            "not be retried automatically",
            TELEGRAM_SWEEP_NAME,
        )


class V1OdkConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.v1.v1_odk"

    def ready(self):
        # No database access here on purpose. ready()
        # runs for every management command, migrate
        # included, so touching django_q_schedule from
        # here would crash on a fresh database before
        # the table exists.
        post_migrate.connect(
            register_telegram_sweep, sender=self
        )
