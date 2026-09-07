from django.apps import apps
from django.db.models.signals import post_migrate
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django_q.models import Schedule

from api.v1.v1_odk.apps import (
    TELEGRAM_SWEEP_FUNC,
    TELEGRAM_SWEEP_NAME,
    register_telegram_sweep,
)


class TelegramSweepRegistrationTest(TestCase):
    def test_ready_does_not_touch_database(self):
        """ready() runs for every management command,
        migrate included. A query here would crash on a
        fresh database before django_q_schedule exists."""
        config = apps.get_app_config("v1_odk")
        with CaptureQueriesContext(connection) as ctx:
            config.ready()
        self.assertEqual(len(ctx.captured_queries), 0)

    @override_settings(
        TEST_ENV=False,
        TELEGRAM_RETRY_COOLDOWN_MINUTES=7,
    )
    def test_post_migrate_registers_schedule(self):
        register_telegram_sweep(sender=None)
        rows = Schedule.objects.filter(
            name=TELEGRAM_SWEEP_NAME
        )
        self.assertEqual(rows.count(), 1)
        row = rows.first()
        self.assertEqual(row.func, TELEGRAM_SWEEP_FUNC)
        self.assertEqual(
            row.schedule_type, Schedule.MINUTES
        )
        self.assertEqual(row.minutes, 7)
        self.assertEqual(row.repeats, -1)

    @override_settings(
        TEST_ENV=False,
        TELEGRAM_RETRY_COOLDOWN_MINUTES=9,
    )
    def test_registration_is_idempotent_and_retunes(self):
        register_telegram_sweep(sender=None)
        register_telegram_sweep(sender=None)
        rows = Schedule.objects.filter(
            name=TELEGRAM_SWEEP_NAME
        )
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().minutes, 9)

    @override_settings(
        TEST_ENV=False,
        TELEGRAM_RETRY_COOLDOWN_MINUTES=5,
    )
    def test_real_post_migrate_signal_fires_handler(self):
        """Pins the sender wiring, not just the handler.

        Django emits post_migrate with sender=app_config --
        the AppConfig *instance* (see
        django/core/management/sql.py). Connecting with
        sender=V1OdkConfig (the class) would silently never
        match, so the schedule would never be created and
        undelivered notifications would never be retried.
        """
        Schedule.objects.filter(
            name=TELEGRAM_SWEEP_NAME
        ).delete()

        config = apps.get_app_config("v1_odk")
        post_migrate.send(
            sender=config,
            app_config=config,
            verbosity=0,
            interactive=False,
            using="default",
        )

        self.assertTrue(
            Schedule.objects.filter(
                name=TELEGRAM_SWEEP_NAME
            ).exists()
        )

    @override_settings(TEST_ENV=True)
    def test_skipped_under_test_env(self):
        # post_migrate already ran during test-database
        # creation (TEST_ENV is not exported by test.sh,
        # so the guard did not fire then). Clear the row
        # to prove the guard, not the leftover.
        Schedule.objects.filter(
            name=TELEGRAM_SWEEP_NAME
        ).delete()
        register_telegram_sweep(sender=None)
        self.assertFalse(
            Schedule.objects.filter(
                name=TELEGRAM_SWEEP_NAME
            ).exists()
        )
