from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from api.v1.v1_odk.constants import SyncStatus
from api.v1.v1_odk.models import (
    FormMetadata,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin

VIEWS = "api.v1.v1_odk.views"
SERIALIZERS = "api.v1.v1_odk.serializers"

CONFIG = {
    "enabled": True,
    "bot_token": "tok",
    "supervisor_group_id": "-100111",
    "enumerator_group_id": "-100222",
}


def config(**overrides):
    return {**CONFIG, **overrides}


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    TELEGRAM_MAX_ATTEMPTS=5,
)
class ResendNotificationEndpointTest(
    OdkTestHelperMixin, TestCase
):
    def setUp(self):
        self.user = self.create_kobo_user()
        form = FormMetadata.objects.create(
            asset_uid="formRS", name="Form RS"
        )
        sub = Submission.objects.create(
            uuid="sub-rs-001",
            form=form,
            kobo_id="950",
            submission_time=1700000000000,
            raw_data={},
        )
        plot = Plot.objects.create(
            plot_name="RS Plot",
            form=form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=sub,
        )
        self.audit = RejectionAudit.objects.create(
            plot=plot,
            submission=sub,
            validator=self.user,
            reason_category="overlap",
            sync_status=SyncStatus.SYNCED,
            telegram_attempts=5,
        )
        self.url = (
            f"/api/v1/odk/rejection-audits/"
            f"{self.audit.pk}/resend_notification/"
        )

    def _post(self, cfg=None):
        with patch(
            f"{VIEWS}.get_telegram_config",
            return_value=cfg or config(),
        ), patch(f"{VIEWS}.async_task") as mock_async:
            resp = self.client.post(
                self.url, **self.get_auth_header()
            )
        return resp, mock_async

    def test_resend_allowed_for_ordinary_user(self):
        """Accounts come from KoboToolbox with
        is_superuser=False, so a superuser gate would leave
        nobody able to resend. Authorization matches
        approve/reject; the 409s below are what bound it."""
        auth = self.get_auth_header()
        self.user.is_superuser = False
        self.user.save(update_fields=["is_superuser"])

        with patch(
            f"{VIEWS}.get_telegram_config",
            return_value=config(),
        ), patch(f"{VIEWS}.async_task") as mock_async:
            resp = self.client.post(self.url, **auth)
        self.assertEqual(resp.status_code, 200)
        mock_async.assert_called_once()

    def test_resend_enqueues_and_resets_attempts(self):
        resp, mock_async = self._post()
        self.assertEqual(resp.status_code, 200)
        mock_async.assert_called_once()
        self.audit.refresh_from_db()
        # Zeroing also re-arms the sweep, so one click
        # restores automatic recovery.
        self.assertEqual(self.audit.telegram_attempts, 0)

    def test_resend_rejects_unsynced_audit(self):
        self.audit.sync_status = SyncStatus.FAILED
        self.audit.save()
        resp, mock_async = self._post()
        self.assertEqual(resp.status_code, 409)
        mock_async.assert_not_called()

    def test_resend_rejects_delivered_audit(self):
        self.audit.telegram_sent_at = timezone.now()
        self.audit.save()
        resp, mock_async = self._post()
        self.assertEqual(resp.status_code, 409)
        mock_async.assert_not_called()

    def test_resend_rejects_when_disabled(self):
        resp, mock_async = self._post(
            cfg=config(enabled=False)
        )
        self.assertEqual(resp.status_code, 409)
        mock_async.assert_not_called()

    def test_sync_failure_is_not_reported_as_telegram(self):
        """A Kobo failure and an exhausted Telegram retry
        need different remedies, so they need different
        statuses."""
        self.audit.sync_status = SyncStatus.FAILED
        self.audit.save()
        with patch(
            f"{SERIALIZERS}.get_telegram_config",
            return_value=config(),
        ):
            resp = self.client.get(
                "/api/v1/odk/submissions/sub-rs-001/",
                **self.get_auth_header(),
            )
        audit = resp.json()["rejection_audits"][0]
        self.assertEqual(
            audit["telegram_status"], "sync_failed"
        )
        self.assertFalse(audit["can_resend"])

    def test_can_resend_flag_matches_endpoint(self):
        with patch(
            f"{SERIALIZERS}.get_telegram_config",
            return_value=config(),
        ):
            resp = self.client.get(
                "/api/v1/odk/submissions/sub-rs-001/",
                **self.get_auth_header(),
            )
        audit = resp.json()["rejection_audits"][0]
        self.assertEqual(
            audit["telegram_status"], "failed"
        )
        self.assertTrue(audit["can_resend"])

    def test_status_disabled_hides_resend(self):
        with patch(
            f"{SERIALIZERS}.get_telegram_config",
            return_value=config(enabled=False),
        ):
            resp = self.client.get(
                "/api/v1/odk/submissions/sub-rs-001/",
                **self.get_auth_header(),
            )
        audit = resp.json()["rejection_audits"][0]
        self.assertEqual(
            audit["telegram_status"], "disabled"
        )
        self.assertFalse(audit["can_resend"])
