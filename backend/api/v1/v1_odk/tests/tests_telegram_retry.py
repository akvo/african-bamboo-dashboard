from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from api.v1.v1_init.models import TelegramGroup
from api.v1.v1_odk.constants import (
    TELEGRAM_NO_ROUTE_ERROR,
    SyncStatus,
)
from api.v1.v1_odk.models import (
    FormMetadata,
    FormOption,
    FormQuestion,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_odk.tasks import (
    retry_pending_telegram_notifications,
    send_telegram_rejection_notification,
)
from api.v1.v1_users.models import SystemUser
from utils.telegram_client import TelegramSendError

TASKS = "api.v1.v1_odk.tasks"
SUPERVISOR = "-100111"
ENUMERATOR = "-100222"

CONFIG = {
    "enabled": True,
    "bot_token": "tok",
}


def config(**overrides):
    return {**CONFIG, **overrides}


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    TELEGRAM_MAX_ATTEMPTS=5,
    TELEGRAM_RETRY_COOLDOWN_MINUTES=5,
)
class TelegramDeliveryLedgerTest(TestCase):
    """The ledger is what makes retrying safe."""

    def setUp(self):
        form = FormMetadata.objects.create(
            asset_uid="formRT", name="Form RT"
        )
        sub = Submission.objects.create(
            uuid="sub-rt-001",
            form=form,
            kobo_id="900",
            submission_time=1700000000000,
            raw_data={},
        )
        plot = Plot.objects.create(
            plot_name="RT Plot",
            form=form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=sub,
        )
        validator = SystemUser.objects.create_superuser(
            email="rt-validator@test.local",
            password="Changeme123",
            name="rt-validator",
        )
        self.audit = RejectionAudit.objects.create(
            plot=plot,
            submission=sub,
            validator=validator,
            reason_category="polygon_error",
            reason_text="Bad polygon",
            sync_status=SyncStatus.SYNCED,
        )

        TelegramGroup.objects.create(chat_id=SUPERVISOR)
        TelegramGroup.objects.create(chat_id=ENUMERATOR)

    def _run(self, side_effect=None, return_value=1):
        with patch(
            f"{TASKS}.get_telegram_config",
            return_value=config(),
        ), patch(f"{TASKS}.TelegramClient") as cls:
            client = MagicMock()
            if side_effect is not None:
                client.send_message.side_effect = side_effect
            else:
                client.send_message.return_value = return_value
            cls.return_value = client
            send_telegram_rejection_notification(self.audit.pk)
        self.audit.refresh_from_db()
        return client

    def test_partial_delivery_leaves_sent_at_null(self):
        client = self._run(
            side_effect=[1, TelegramSendError("nope")]
        )
        self.assertEqual(client.send_message.call_count, 2)
        self.assertIsNone(self.audit.telegram_sent_at)
        self.assertEqual(
            self.audit.telegram_chat_ids, [SUPERVISOR]
        )
        self.assertIn("nope", self.audit.telegram_last_error)

    def test_retry_skips_already_delivered_chat(self):
        self._run(side_effect=[1, TelegramSendError("nope")])
        client = self._run(return_value=2)
        # Only the outstanding chat is contacted.
        self.assertEqual(client.send_message.call_count, 1)
        self.assertEqual(
            client.send_message.call_args[0][0], ENUMERATOR
        )
        self.assertIsNotNone(self.audit.telegram_sent_at)
        self.assertEqual(
            self.audit.telegram_chat_ids,
            [SUPERVISOR, ENUMERATOR],
        )

    def test_full_delivery_sets_sent_at(self):
        self._run(return_value=7)
        self.assertIsNotNone(self.audit.telegram_sent_at)
        self.assertIsNone(self.audit.telegram_last_error)

    def test_task_never_raises_on_send_error(self):
        # No assertRaises: the task must complete, because
        # Q_CLUSTER pins max_attempts=1 and a raise would
        # simply lose the notification.
        self._run(side_effect=TelegramSendError("down"))
        self.assertIsNone(self.audit.telegram_sent_at)
        self.assertEqual(self.audit.telegram_attempts, 1)

    def test_attempts_incremented_and_error_recorded(self):
        self._run(side_effect=TelegramSendError("down"))
        self.assertEqual(self.audit.telegram_attempts, 1)
        self.assertIsNotNone(
            self.audit.telegram_last_attempt_at
        )
        self.assertIn("down", self.audit.telegram_last_error)

    def test_fully_delivered_audit_sends_nothing(self):
        self._run(return_value=1)
        client = self._run(return_value=1)
        client.send_message.assert_not_called()

    def test_timeout_after_delivery_sends_once(self):
        """Regression guard for the deleted fallback.

        TelegramClient turns a post-delivery timeout into a
        TelegramSendError. Nothing may resend on it, or the
        group gets two copies of the same message.
        """
        client = self._run(
            side_effect=TelegramSendError("timeout")
        )
        self.assertEqual(client.send_message.call_count, 2)
        for call in client.send_message.call_args_list:
            self.assertIn(
                call[0][0], (SUPERVISOR, ENUMERATOR)
            )


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    TELEGRAM_MAX_ATTEMPTS=5,
    TELEGRAM_RETRY_COOLDOWN_MINUTES=5,
)
class TelegramRetrySweepTest(TestCase):
    def setUp(self):
        form = FormMetadata.objects.create(
            asset_uid="formSW", name="Form SW"
        )
        self.sub = Submission.objects.create(
            uuid="sub-sw-001",
            form=form,
            kobo_id="901",
            submission_time=1700000000000,
            raw_data={},
        )
        self.plot = Plot.objects.create(
            plot_name="SW Plot",
            form=form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=self.sub,
        )
        self.audit = RejectionAudit.objects.create(
            plot=self.plot,
            submission=self.sub,
            reason_category="overlap",
            sync_status=SyncStatus.SYNCED,
        )

        TelegramGroup.objects.create(chat_id=SUPERVISOR)
        TelegramGroup.objects.create(chat_id=ENUMERATOR)

    def _sweep(self, cfg=None):
        with patch(
            f"{TASKS}.get_telegram_config",
            return_value=cfg or config(),
        ), patch(f"{TASKS}.async_task") as mock_async:
            retry_pending_telegram_notifications()
        return mock_async

    def test_sweeper_requeues_stuck_audit(self):
        mock_async = self._sweep()
        mock_async.assert_called_once()
        self.assertEqual(
            mock_async.call_args[0][1], self.audit.pk
        )

    def test_sweeper_respects_cooldown(self):
        self.audit.telegram_last_attempt_at = timezone.now()
        self.audit.save()
        self._sweep().assert_not_called()

    def test_sweeper_stops_at_max_attempts(self):
        self.audit.telegram_attempts = 5
        self.audit.save()
        self._sweep().assert_not_called()

    def test_sweeper_ignores_unsynced_audits(self):
        # A rejection that never reached Kobo must never
        # notify the enumerator.
        self.audit.sync_status = SyncStatus.FAILED
        self.audit.save()
        self._sweep().assert_not_called()

    def test_sweeper_ignores_delivered_audits(self):
        self.audit.telegram_sent_at = timezone.now()
        self.audit.save()
        self._sweep().assert_not_called()

    def test_stale_pending_audit_warns_not_notified(self):
        self.audit.sync_status = SyncStatus.PENDING
        self.audit.save()
        RejectionAudit.objects.filter(
            pk=self.audit.pk
        ).update(
            rejected_at=timezone.now()
            - timezone.timedelta(hours=1)
        )
        with self.assertLogs(TASKS, level="WARNING") as logs:
            mock_async = self._sweep()
        mock_async.assert_not_called()
        self.assertIn(
            "stuck at sync_status=pending",
            "\n".join(logs.output),
        )

    def test_retry_after_recorded_from_429(self):
        """Telegram extends the flood-wait every time it is
        ignored, so its own value has to be persisted."""
        err = TelegramSendError("rate limited", retry_after=90)
        with patch(
            f"{TASKS}.get_telegram_config",
            return_value=config(),
        ), patch(f"{TASKS}.TelegramClient") as cls:
            cls.return_value.send_message.side_effect = err
            send_telegram_rejection_notification(
                self.audit.pk
            )
        self.audit.refresh_from_db()
        self.assertIsNotNone(
            self.audit.telegram_next_attempt_at
        )
        delta = (
            self.audit.telegram_next_attempt_at
            - timezone.now()
        ).total_seconds()
        self.assertGreater(delta, 60)

    def test_sweeper_waits_for_retry_after(self):
        """Even once the cooldown has passed, a pending
        flood-wait must hold the audit back."""
        self.audit.telegram_last_attempt_at = (
            timezone.now() - timezone.timedelta(hours=1)
        )
        self.audit.telegram_next_attempt_at = (
            timezone.now() + timezone.timedelta(minutes=10)
        )
        self.audit.save()
        self._sweep().assert_not_called()

    def test_sweeper_requeues_once_retry_after_passes(self):
        self.audit.telegram_last_attempt_at = (
            timezone.now() - timezone.timedelta(hours=1)
        )
        self.audit.telegram_next_attempt_at = (
            timezone.now() - timezone.timedelta(minutes=1)
        )
        self.audit.save()
        self._sweep().assert_called_once()

    def test_sweeper_skips_when_disabled(self):
        self._sweep(
            cfg=config(enabled=False)
        ).assert_not_called()

    def test_sweeper_skips_when_no_bot_token(self):
        self._sweep(
            cfg=config(bot_token="")
        ).assert_not_called()


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    TELEGRAM_MAX_ATTEMPTS=5,
    TELEGRAM_RETRY_COOLDOWN_MINUTES=5,
)
class TelegramRegionRoutingTest(TestCase):
    """Spec v29: a group receives an alert only when its
    scope covers plot.region; [] covers everything."""

    def setUp(self):
        form = FormMetadata.objects.create(
            asset_uid="formRR", name="Form RR"
        )
        sub = Submission.objects.create(
            uuid="sub-rr-001",
            form=form,
            kobo_id="902",
            submission_time=1700000000000,
            raw_data={},
        )
        self.plot = Plot.objects.create(
            plot_name="RR Plot",
            form=form,
            region="ET16",
            sub_region="S",
            created_at=1700000000000,
            submission=sub,
        )
        self.audit = RejectionAudit.objects.create(
            plot=self.plot,
            submission=sub,
            reason_category="overlap",
            sync_status=SyncStatus.SYNCED,
        )

    def _run(self, side_effect=None):
        with patch(
            f"{TASKS}.get_telegram_config",
            return_value={"enabled": True, "bot_token": "tok"},
        ), patch(f"{TASKS}.TelegramClient") as cls:
            client = MagicMock()
            client.send_message.side_effect = side_effect
            client.send_message.return_value = 1
            cls.return_value = client
            send_telegram_rejection_notification(self.audit.pk)
        self.audit.refresh_from_db()
        return [c[0][0] for c in client.send_message.call_args_list]

    def _sweep(self):
        with patch(
            f"{TASKS}.get_telegram_config",
            return_value={"enabled": True, "bot_token": "tok"},
        ), patch(f"{TASKS}.async_task") as mock_async:
            retry_pending_telegram_notifications()
        return mock_async

    def test_scoped_and_all_regions_groups_receive(self):
        TelegramGroup.objects.create(chat_id="-1", regions=[])
        TelegramGroup.objects.create(
            chat_id="-2", regions=["SID", "ET16"]
        )
        TelegramGroup.objects.create(
            chat_id="-3", regions=["ORO", "ET04"]
        )
        self.assertEqual(self._run(), ["-1", "-2"])
        self.assertIsNotNone(self.audit.telegram_sent_at)

    def test_empty_plot_region_reaches_only_all_regions_groups(
        self,
    ):
        self.plot.region = ""
        self.plot.save()
        TelegramGroup.objects.create(chat_id="-1", regions=[])
        TelegramGroup.objects.create(chat_id="-2", regions=["ET16"])
        self.assertEqual(self._run(), ["-1"])

    def test_no_covering_group_abandons_with_reason(self):
        TelegramGroup.objects.create(chat_id="-3", regions=["ET04"])
        with self.assertLogs(TASKS, level="WARNING"):
            sent = self._run()
        self.assertEqual(sent, [])
        self.assertEqual(
            self.audit.telegram_attempts,
            settings.TELEGRAM_MAX_ATTEMPTS,
        )
        self.assertTrue(
            self.audit.telegram_last_error.startswith(
                TELEGRAM_NO_ROUTE_ERROR
            )
        )
        self.assertIn("ET16", self.audit.telegram_last_error)
        self.assertIsNone(self.audit.telegram_sent_at)
        # The latent v28 loop: the sweep must not re-enqueue.
        self._sweep().assert_not_called()

    def test_no_route_error_uses_region_option_label(self):
        form = self.plot.form
        q = FormQuestion.objects.create(
            form=form,
            name="region",
            label="Region",
            type="select_one",
        )
        FormOption.objects.create(
            question=q, name="ET16", label="Sidama"
        )
        sub = self.audit.submission
        sub.raw_data = {"region": "ET16"}
        sub.save()
        with self.assertLogs(TASKS, level="WARNING"):
            self._run()
        self.assertEqual(
            self.audit.telegram_last_error,
            "No Telegram group covers region Sidama (ET16)",
        )

    def test_zero_groups_is_no_route(self):
        with self.assertLogs(TASKS, level="WARNING"):
            sent = self._run()
        self.assertEqual(sent, [])
        self.assertEqual(
            self.audit.telegram_attempts,
            settings.TELEGRAM_MAX_ATTEMPTS,
        )

    def test_resend_after_scope_fix_delivers(self):
        group = TelegramGroup.objects.create(
            chat_id="-3", regions=["ET04"]
        )
        with self.assertLogs(TASKS, level="WARNING"):
            self._run()
        group.regions = ["ET04", "ET16"]
        group.save()
        # What the resend endpoint does before enqueueing.
        self.audit.telegram_attempts = 0
        self.audit.save()
        self.assertEqual(self._run(), ["-3"])
        self.assertIsNotNone(self.audit.telegram_sent_at)
        self.assertIsNone(self.audit.telegram_last_error)

    def test_scope_edit_never_resends_ledgered_chat(self):
        TelegramGroup.objects.create(chat_id="-1", regions=[])
        moved = TelegramGroup.objects.create(
            chat_id="-2", regions=["ET16"]
        )
        self._run(side_effect=[1, TelegramSendError("down")])
        moved.regions = ["ET04"]
        moved.save()
        TelegramGroup.objects.create(chat_id="-4", regions=["ET16"])
        self.assertEqual(self._run(), ["-4"])
        self.assertEqual(self.audit.telegram_chat_ids, ["-1", "-4"])
        self.assertIsNotNone(self.audit.telegram_sent_at)

    def test_all_targets_ledgered_marks_sent(self):
        """Spec D-4 second loop: the only failing group is
        removed from scope; nothing is outstanding."""
        TelegramGroup.objects.create(chat_id="-1", regions=[])
        failing = TelegramGroup.objects.create(
            chat_id="-2", regions=["ET16"]
        )
        self._run(side_effect=[1, TelegramSendError("down")])
        failing.delete()
        self.assertEqual(self._run(), [])
        self.assertIsNotNone(self.audit.telegram_sent_at)
        self.assertIsNone(self.audit.telegram_last_error)
        self._sweep().assert_not_called()
