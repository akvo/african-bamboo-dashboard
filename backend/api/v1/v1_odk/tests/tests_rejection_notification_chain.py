"""End-to-end proof of the rejection -> Telegram chain.

TC19 reported that rejecting a plot sends no Telegram
message. Every hop of that chain runs on the Django-Q
worker, so the whole feature is invisible to a test
suite that only patches ``async_task`` at the first
dispatch -- which is what the existing tests do.

These tests stub only the outermost HTTP boundaries
(KoboToolbox and Telegram) and drive every hop for
real. If they pass, the application code is sound and
a production failure is a configuration or
infrastructure problem: a worker that is not running,
a worker pod without egress, or Telegram settings that
are not what they appear to be.

Note: ``Q_CLUSTER["sync"]`` is False during the test
run (TEST_ENV is never exported), so tasks queued with
``async_task`` do NOT execute inline. Each hop is
therefore invoked explicitly.
"""

import logging
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from requests import HTTPError

from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
    SyncStatus,
)
from api.v1.v1_odk.models import (
    FormMetadata,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_odk.tasks import (
    on_kobo_sync_complete,
    send_telegram_rejection_notification,
    sync_kobo_validation_status,
)
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin
from api.v1.v1_odk.utils.plot_id import (
    create_main_plot_for_submission,
)

TELEGRAM_ON = override_settings(
    TELEGRAM_ENABLED=True,
    TELEGRAM_BOT_TOKEN="test-token",
    TELEGRAM_SUPERVISOR_GROUP_ID="-100001",
    TELEGRAM_ENUMERATOR_GROUP_ID="-100002",
)

REASON_TEXT = "Boundary overlap detected"


class RejectionNotificationChainTest(
    OdkTestHelperMixin, TestCase
):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.header = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formCHAIN",
            name="Chain Form",
        )
        self.sub = Submission.objects.create(
            uuid="sub-chain-001",
            form=self.form,
            kobo_id="9001",
            submission_time=1700000000000,
            submitted_by="enumerator1",
            raw_data={"q": "a"},
        )
        self.plot = Plot.objects.create(
            plot_name="Chain Plot",
            form=self.form,
            region="Region A",
            sub_region="Sub A",
            created_at=1700000000000,
            submission=self.sub,
        )
        # A MainPlot only exists after an approval,
        # so create one to assert the Plot ID appears.
        create_main_plot_for_submission(self.sub)
        self.sub.refresh_from_db()

    def _reject(self):
        """PATCH the submission to rejected.

        Returns the dispatch call django_q would have
        been given for the Kobo sync task.
        """
        with patch(
            "api.v1.v1_odk.views.async_task"
        ) as mock_async:
            resp = self.client.patch(
                f"/api/v1/odk/submissions/{self.sub.uuid}/",
                {
                    "approval_status": (
                        ApprovalStatusTypes.REJECTED
                    ),
                    "reason_category": "overlap",
                    "reason_text": REASON_TEXT,
                },
                content_type="application/json",
                **self.header,
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_async.call_count, 1)
        return mock_async.call_args

    def test_full_chain_delivers_notification(self):
        """Reject -> Kobo sync -> hook -> Telegram."""
        call = self._reject()

        # Hop 1: the rejection dispatched the Kobo sync
        # with the completion hook attached.
        self.assertIn(
            "sync_kobo_validation_status",
            call.args[0],
        )
        self.assertIn(
            "on_kobo_sync_complete",
            call.kwargs["hook"],
        )
        audit_id = call.kwargs["audit_id"]
        audit = RejectionAudit.objects.get(
            pk=audit_id
        )
        self.assertEqual(
            audit.reason_text, REASON_TEXT
        )

        # Hop 2: the Kobo sync itself succeeds.
        with patch(
            "api.v1.v1_odk.tasks.KoboClient"
        ) as mock_kobo:
            kobo = mock_kobo.return_value
            kobo.update_validation_statuses.return_value = {  # noqa: E501
                "ok": True
            }
            sync_kobo_validation_status(
                *call.args[1:],
                audit_id=audit_id,
            )
            kobo.update_validation_statuses.assert_called_once()  # noqa: E501

        # Hop 3: the completion hook queues Telegram.
        task = MagicMock()
        task.success = True
        task.kwargs = {"audit_id": audit_id}
        with TELEGRAM_ON:
            with patch(
                "api.v1.v1_odk.tasks.async_task"
            ) as mock_async:
                on_kobo_sync_complete(task)

        audit.refresh_from_db()
        self.assertEqual(
            audit.sync_status, SyncStatus.SYNCED
        )
        self.assertEqual(mock_async.call_count, 1)
        self.assertIn(
            "send_telegram_rejection_notification",
            mock_async.call_args.args[0],
        )

        # Hop 4: the message is actually sent.
        with TELEGRAM_ON:
            with patch(
                "api.v1.v1_odk.tasks.TelegramClient"
            ) as mock_tg:
                client = MagicMock()
                client.send_message.return_value = 55
                mock_tg.return_value = client
                send_telegram_rejection_notification(
                    audit_id
                )

        self.assertEqual(
            client.send_message.call_count, 2
        )
        sent = client.send_message.call_args.args[1]
        self.assertIn("PLT", sent)
        self.assertIn(REASON_TEXT, sent)

        audit.refresh_from_db()
        self.assertIsNotNone(audit.telegram_sent_at)

    def test_chain_stops_when_kobo_update_fails(self):
        """A dead form in Kobo must suppress the send.

        The recipient acts on the message assuming the
        rejection is already in Kobo, so a failed sync
        must not notify anyone -- and must say so.
        """
        call = self._reject()
        audit_id = call.kwargs["audit_id"]

        response = MagicMock()
        response.status_code = 404
        response.text = "Not found"
        error = HTTPError("404")
        error.response = response

        with patch(
            "api.v1.v1_odk.tasks.KoboClient"
        ) as mock_kobo:
            kobo = mock_kobo.return_value
            kobo.update_validation_statuses.side_effect = (  # noqa: E501
                error
            )
            with self.assertLogs(
                "api.v1.v1_odk.tasks",
                level=logging.ERROR,
            ) as cm:
                with self.assertRaises(HTTPError):
                    sync_kobo_validation_status(
                        *call.args[1:],
                        audit_id=audit_id,
                    )

        self.assertTrue(
            any(
                "may have been deleted" in m
                for m in cm.output
            ),
            "the log must name the likely cause",
        )

        # django_q sees the raise, so the hook runs
        # with success=False.
        task = MagicMock()
        task.success = False
        task.kwargs = {"audit_id": audit_id}
        with TELEGRAM_ON:
            with patch(
                "api.v1.v1_odk.tasks.async_task"
            ) as mock_async:
                with self.assertLogs(
                    "api.v1.v1_odk.tasks",
                    level=logging.WARNING,
                ) as cm:
                    on_kobo_sync_complete(task)

        mock_async.assert_not_called()
        audit = RejectionAudit.objects.get(
            pk=audit_id
        )
        self.assertEqual(
            audit.sync_status, SyncStatus.FAILED
        )
        self.assertIsNone(audit.telegram_sent_at)
        self.assertTrue(
            any(
                "suppressing the Telegram" in m
                for m in cm.output
            ),
            "the log must explain the suppression",
        )
