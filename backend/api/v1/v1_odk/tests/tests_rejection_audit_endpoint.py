from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    ApprovalStatus,
    FormMetadata,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class RejectionAuditEndpointTest(
    TestCase, OdkTestHelperMixin
):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formAudit",
            name="Form Audit",
        )
        self.sub = Submission.objects.create(
            uuid="sub-audit-001",
            form=self.form,
            kobo_id="600",
            submission_time=1700000000000,
            submitted_by="tester",
            instance_name="Audit Instance",
            raw_data={"q1": "a1"},
        )
        self.plot = Plot.objects.create(
            plot_name="Audit Plot",
            form=self.form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=self.sub,
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_reject_with_category_creates_audit(
        self, mock_async
    ):
        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
                "reason_category": (
                    "polygon_error"
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            RejectionAudit.objects.filter(
                submission=self.sub
            ).exists()
        )

    def test_reject_without_category_returns_400(
        self,
    ):
        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)

    @patch("api.v1.v1_odk.views.async_task")
    def test_reject_with_reason_text(
        self, mock_async
    ):
        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
                "reason_category": (
                    "overlap"
                ),
                "reason_text": (
                    "Missing polygon data"
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        audit = RejectionAudit.objects.get(
            submission=self.sub
        )
        self.assertEqual(
            audit.reason_category,
            "overlap",
        )
        self.assertEqual(
            audit.reason_text,
            "Missing polygon data",
        )

    def test_reject_invalid_category_returns_400(
        self,
    ):
        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
                "reason_category": (
                    "invalid_category"
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)

    @patch("api.v1.v1_odk.views.async_task")
    def test_approve_does_not_create_audit(
        self, mock_async
    ):
        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            {
                "approval_status": (
                    ApprovalStatus.APPROVED
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            RejectionAudit.objects.filter(
                submission=self.sub
            ).exists()
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_approve_without_notes_succeeds(
        self, mock_async
    ):
        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            {
                "approval_status": (
                    ApprovalStatus.APPROVED
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)

    @patch("api.v1.v1_odk.views.async_task")
    def test_reject_dispatches_with_hook(
        self, mock_async
    ):
        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
                "reason_category": (
                    "polygon_error"
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        mock_async.assert_called_once()
        kwargs = mock_async.call_args[1]
        self.assertEqual(
            kwargs["hook"],
            "api.v1.v1_odk.tasks"
            ".on_kobo_sync_complete",
        )
        self.assertIn("audit_id", kwargs)

    @patch("api.v1.v1_odk.views.async_task")
    def test_audit_stores_validator(
        self, mock_async
    ):
        self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
                "reason_category": "other",
            },
            content_type="application/json",
            **self.auth,
        )
        audit = RejectionAudit.objects.get(
            submission=self.sub
        )
        self.assertEqual(
            audit.validator, self.user
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_audit_initial_sync_status_pending(
        self, mock_async
    ):
        self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
                "reason_category": "duplicate",
            },
            content_type="application/json",
            **self.auth,
        )
        audit = RejectionAudit.objects.get(
            submission=self.sub
        )
        self.assertEqual(
            audit.sync_status, "pending"
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_submission_detail_includes_audits(
        self, mock_async
    ):
        self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
                "reason_category": (
                    "polygon_error"
                ),
                "reason_text": "Test reason",
            },
            content_type="application/json",
            **self.auth,
        )
        resp = self.client.get(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(
            "rejection_audits", data
        )
        self.assertEqual(
            len(data["rejection_audits"]), 1
        )
        self.assertEqual(
            data["rejection_audits"][0][
                "reason_category"
            ],
            "polygon_error",
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_reviewer_notes_returns_latest(
        self, mock_async
    ):
        self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
                "reason_category": (
                    "polygon_error"
                ),
                "reason_text": "First reason",
            },
            content_type="application/json",
            **self.auth,
        )
        # Reset approval so we can reject again
        self.sub.refresh_from_db()
        self.sub.approval_status = None
        self.sub.save()

        self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
                "reason_category": "other",
                "reason_text": "Second reason",
            },
            content_type="application/json",
            **self.auth,
        )
        resp = self.client.get(
            "/api/v1/odk/submissions/"
            "sub-audit-001/",
            **self.auth,
        )
        data = resp.json()
        self.assertEqual(
            data["reviewer_notes"],
            "Second reason",
        )
