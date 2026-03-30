from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from api.v1.v1_odk.constants import SyncStatus
from api.v1.v1_odk.models import (
    FormMetadata,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_odk.tasks import (
    on_kobo_sync_complete,
    send_telegram_rejection_notification,
)
from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False, TEST_ENV=True)
class KoboSyncHookTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="formTG",
            name="Form TG",
        )
        self.sub = Submission.objects.create(
            uuid="sub-tg-001",
            form=self.form,
            kobo_id="700",
            submission_time=1700000000000,
            submitted_by="tester",
            raw_data={"q": "a"},
        )
        self.plot = Plot.objects.create(
            plot_name="TG Plot",
            form=self.form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=self.sub,
        )
        self.validator = (
            SystemUser.objects.create_superuser(
                email="tg-validator@test.local",
                password="Changeme123",
                name="tg-validator",
            )
        )
        self.audit = RejectionAudit.objects.create(
            plot=self.plot,
            submission=self.sub,
            validator=self.validator,
            reason_category="polygon_error",
            reason_text="Bad polygon",
        )

    @override_settings(TELEGRAM_ENABLED=True)
    @patch(
        "api.v1.v1_odk.tasks.async_task"
    )
    def test_hook_success_queues_telegram(
        self, mock_async
    ):
        task = MagicMock()
        task.success = True
        task.kwargs = {"audit_id": self.audit.pk}

        on_kobo_sync_complete(task)

        mock_async.assert_called_once()
        args = mock_async.call_args[0]
        self.assertIn(
            "send_telegram_rejection",
            args[0],
        )

    @patch(
        "api.v1.v1_odk.tasks.async_task"
    )
    def test_hook_failure_skips_telegram(
        self, mock_async
    ):
        task = MagicMock()
        task.success = False
        task.kwargs = {"audit_id": self.audit.pk}

        on_kobo_sync_complete(task)

        mock_async.assert_not_called()
        self.audit.refresh_from_db()
        self.assertEqual(
            self.audit.sync_status,
            SyncStatus.FAILED,
        )

    @patch(
        "api.v1.v1_odk.tasks.async_task"
    )
    def test_hook_updates_sync_status_synced(
        self, mock_async
    ):
        task = MagicMock()
        task.success = True
        task.kwargs = {"audit_id": self.audit.pk}

        on_kobo_sync_complete(task)

        self.audit.refresh_from_db()
        self.assertEqual(
            self.audit.sync_status,
            SyncStatus.SYNCED,
        )
        self.assertIsNotNone(self.audit.synced_at)

    @patch(
        "api.v1.v1_odk.tasks.async_task"
    )
    def test_hook_updates_sync_status_failed(
        self, mock_async
    ):
        task = MagicMock()
        task.success = False
        task.kwargs = {"audit_id": self.audit.pk}

        on_kobo_sync_complete(task)

        self.audit.refresh_from_db()
        self.assertEqual(
            self.audit.sync_status,
            SyncStatus.FAILED,
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class TelegramNotificationTaskTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="formTGN",
            name="Form TGN",
        )
        self.sub = Submission.objects.create(
            uuid="sub-tgn-001",
            form=self.form,
            kobo_id="800",
            submission_time=1700000000000,
            submitted_by="enumerator1",
            raw_data={"q": "a"},
        )
        self.plot = Plot.objects.create(
            plot_name="TGN Plot",
            form=self.form,
            region="Region A",
            sub_region="Sub A",
            created_at=1700000000000,
            submission=self.sub,
        )
        self.validator = (
            SystemUser.objects.create_superuser(
                email="tgn-val@test.local",
                password="Changeme123",
                name="tgn-validator",
            )
        )
        self.audit = RejectionAudit.objects.create(
            plot=self.plot,
            submission=self.sub,
            validator=self.validator,
            reason_category="polygon_error",
            reason_text="Bad polygon shape",
        )

    @override_settings(
        TELEGRAM_ENABLED=True,
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_SUPERVISOR_GROUP_ID="-100001",
        TELEGRAM_ENUMERATOR_GROUP_ID="-100002",
    )
    @patch(
        "api.v1.v1_odk.tasks.TelegramClient"
    )
    def test_sends_to_both_groups(
        self, mock_client_cls
    ):
        mock_client = MagicMock()
        mock_client.send_message.return_value = (
            12345
        )
        mock_client_cls.return_value = (
            mock_client
        )

        send_telegram_rejection_notification(
            self.audit.pk
        )

        self.assertEqual(
            mock_client.send_message.call_count,
            2,
        )

    @override_settings(
        TELEGRAM_ENABLED=True,
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_SUPERVISOR_GROUP_ID="-100001",
        TELEGRAM_ENUMERATOR_GROUP_ID="-100002",
    )
    @patch(
        "api.v1.v1_odk.tasks.TelegramClient"
    )
    def test_message_contains_fields(
        self, mock_client_cls
    ):
        mock_client = MagicMock()
        mock_client.send_message.return_value = (
            12345
        )
        mock_client_cls.return_value = (
            mock_client
        )

        send_telegram_rejection_notification(
            self.audit.pk
        )

        call_args = (
            mock_client.send_message.call_args
        )
        message = call_args[0][1]
        self.assertIn("#800", message)
        self.assertIn("Region A", message)
        self.assertIn("Sub A", message)
        self.assertIn("Polygon Error", message)
        self.assertIn(
            "Bad polygon shape", message
        )
        self.assertIn("tgn-validator", message)

    @override_settings(
        TELEGRAM_ENABLED=True,
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_SUPERVISOR_GROUP_ID="-100001",
        TELEGRAM_ENUMERATOR_GROUP_ID="-100002",
    )
    @patch(
        "api.v1.v1_odk.tasks.TelegramClient"
    )
    def test_updates_audit_fields(
        self, mock_client_cls
    ):
        mock_client = MagicMock()
        mock_client.send_message.return_value = (
            12345
        )
        mock_client_cls.return_value = (
            mock_client
        )

        send_telegram_rejection_notification(
            self.audit.pk
        )

        self.audit.refresh_from_db()
        self.assertIsNotNone(
            self.audit.telegram_sent_at
        )
        self.assertEqual(
            self.audit.telegram_chat_ids,
            ["-100001", "-100002"],
        )
        self.assertIsNotNone(
            self.audit.telegram_message_id
        )

    @override_settings(TELEGRAM_ENABLED=False)
    @patch(
        "api.v1.v1_odk.tasks.TelegramClient"
    )
    def test_skipped_when_disabled(
        self, mock_client_cls
    ):
        send_telegram_rejection_notification(
            self.audit.pk
        )
        mock_client_cls.assert_not_called()

    @override_settings(
        TELEGRAM_ENABLED=True,
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_SUPERVISOR_GROUP_ID="-100001",
        TELEGRAM_ENUMERATOR_GROUP_ID="-100002",
    )
    @patch(
        "api.v1.v1_odk.tasks.TelegramClient"
    )
    def test_failure_does_not_raise(
        self, mock_client_cls
    ):
        from utils.telegram_client import (
            TelegramSendError,
        )

        mock_client = MagicMock()
        mock_client.send_message.side_effect = (
            TelegramSendError("API error")
        )
        mock_client_cls.return_value = (
            mock_client
        )

        # Should not raise
        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level="ERROR",
        ):
            send_telegram_rejection_notification(
                self.audit.pk
            )

    @override_settings(
        TELEGRAM_ENABLED=True,
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_SUPERVISOR_GROUP_ID="-100001",
        TELEGRAM_ENUMERATOR_GROUP_ID="-100002",
    )
    @patch(
        "api.v1.v1_odk.tasks.TelegramClient"
    )
    def test_partial_failure(
        self, mock_client_cls
    ):
        from utils.telegram_client import (
            TelegramSendError,
        )

        mock_client = MagicMock()
        mock_client.send_message.side_effect = [
            111,
            TelegramSendError("fail"),
        ]
        mock_client_cls.return_value = (
            mock_client
        )

        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level="ERROR",
        ):
            send_telegram_rejection_notification(
                self.audit.pk
            )

        self.audit.refresh_from_db()
        self.assertIsNotNone(
            self.audit.telegram_sent_at
        )
        self.assertEqual(
            self.audit.telegram_chat_ids,
            ["-100001"],
        )

    @override_settings(
        TELEGRAM_ENABLED=True,
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_SUPERVISOR_GROUP_ID="-100001",
        TELEGRAM_ENUMERATOR_GROUP_ID="-100001",
    )
    @patch(
        "api.v1.v1_odk.tasks.TelegramClient"
    )
    def test_duplicate_group_sends_once(
        self, mock_client_cls
    ):
        mock_client = MagicMock()
        mock_client.send_message.return_value = (
            12345
        )
        mock_client_cls.return_value = (
            mock_client
        )

        send_telegram_rejection_notification(
            self.audit.pk
        )

        mock_client.send_message.assert_called_once()
        self.audit.refresh_from_db()
        self.assertEqual(
            self.audit.telegram_chat_ids,
            ["-100001"],
        )
