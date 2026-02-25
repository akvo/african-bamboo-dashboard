from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    ApprovalStatus,
    FormMetadata,
    Plot,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionViewTest(TestCase, OdkTestHelperMixin):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formX",
            name="Form X",
        )
        self.sub = Submission.objects.create(
            uuid="sub-001",
            form=self.form,
            kobo_id="100",
            submission_time=1700000000000,
            submitted_by="tester",
            instance_name="Test Instance",
            raw_data={"q1": "a1"},
            system_data={
                "_geolocation": [9.0, 38.7],
            },
        )

    def test_list_submissions(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertNotIn("raw_data", results[0])

    def test_list_includes_approval_status(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/",
            **self.auth,
        )
        results = resp.json()["results"]
        self.assertIn("approval_status", results[0])
        self.assertIsNone(results[0]["approval_status"])

    def test_filter_by_asset_uid(self):
        form_y = FormMetadata.objects.create(asset_uid="formY", name="Form Y")
        Submission.objects.create(
            uuid="sub-002",
            form=form_y,
            kobo_id="200",
            submission_time=1700000001000,
            raw_data={},
        )
        resp = self.client.get(
            "/api/v1/odk/submissions/" "?asset_uid=formX",
            **self.auth,
        )
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["uuid"], "sub-001")

    def test_retrieve_submission_detail(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/sub-001/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("raw_data", data)
        self.assertIn("system_data", data)
        self.assertIn("approval_status", data)

    def test_latest_sync_time(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/" "latest_sync_time/?asset_uid=formX",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["latest_submission_time"],
            1700000000000,
        )

    def test_latest_sync_time_missing_param(
        self,
    ):
        resp = self.client.get(
            "/api/v1/odk/submissions/" "latest_sync_time/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)

    def test_approve_submission(self):
        resp = self.client.patch(
            "/api/v1/odk/submissions/sub-001/",
            {
                "approval_status": (ApprovalStatus.APPROVED),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(
            self.sub.approval_status,
            ApprovalStatus.APPROVED,
        )

    def test_reject_submission_with_notes(self):
        resp = self.client.patch(
            "/api/v1/odk/submissions/sub-001/",
            {
                "approval_status": (ApprovalStatus.REJECTED),
                "reviewer_notes": ("Boundary is unclear"),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(
            self.sub.approval_status,
            ApprovalStatus.REJECTED,
        )
        self.assertEqual(
            self.sub.reviewer_notes,
            "Boundary is unclear",
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionApprovalClearsFlagsTest(
    TestCase, OdkTestHelperMixin
):
    """Approving or rejecting a submission clears
    the linked plot's flagged_for_review and
    flagged_reason."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formF",
            name="Form F",
        )
        self.sub = Submission.objects.create(
            uuid="sub-flag-001",
            form=self.form,
            kobo_id="300",
            submission_time=1700000000000,
            raw_data={"q1": "a1"},
        )
        self.plot = Plot.objects.create(
            plot_name="Flagged Farmer",
            instance_name="inst-flag",
            polygon_wkt="POLYGON((0 0,1 0,1 1,0 0))",
            min_lat=0.0,
            max_lat=1.0,
            min_lon=0.0,
            max_lon=1.0,
            form=self.form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=self.sub,
            flagged_for_review=True,
            flagged_reason="Polygon overlaps with: X",
        )

    def test_approve_clears_plot_flags(self):
        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-flag-001/",
            {
                "approval_status": (
                    ApprovalStatus.APPROVED
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.plot.refresh_from_db()
        self.assertIs(
            self.plot.flagged_for_review, False
        )
        self.assertIsNone(self.plot.flagged_reason)

    def test_reject_clears_plot_flags(self):
        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-flag-001/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
                "reviewer_notes": "Bad boundary",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.plot.refresh_from_db()
        self.assertIs(
            self.plot.flagged_for_review, False
        )
        self.assertIsNone(self.plot.flagged_reason)

    def test_approve_without_plot_no_error(self):
        """Submission without a linked plot does
        not crash on approval."""
        sub_no_plot = Submission.objects.create(
            uuid="sub-no-plot",
            form=self.form,
            kobo_id="301",
            submission_time=1700000001000,
            raw_data={},
        )
        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-no-plot/",
            {
                "approval_status": (
                    ApprovalStatus.APPROVED
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        sub_no_plot.refresh_from_db()
        self.assertEqual(
            sub_no_plot.approval_status,
            ApprovalStatus.APPROVED,
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionKoboSyncDispatchTest(
    TestCase, OdkTestHelperMixin
):
    """Approving or rejecting a submission dispatches
    an async_task to sync the status to Kobo."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formSync",
            name="Form Sync",
        )
        self.sub = Submission.objects.create(
            uuid="sub-sync-001",
            form=self.form,
            kobo_id="500",
            submission_time=1700000000000,
            raw_data={"q1": "a1"},
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_approve_dispatches_kobo_sync(
        self, mock_async,
    ):
        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-sync-001/",
            {
                "approval_status": (
                    ApprovalStatus.APPROVED
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        mock_async.assert_called_once()
        args = mock_async.call_args[0]
        self.assertEqual(
            args[0],
            "api.v1.v1_odk.tasks"
            ".sync_kobo_validation_status",
        )
        self.assertEqual(
            args[5], [500]
        )
        self.assertEqual(
            args[6],
            ApprovalStatus.APPROVED,
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_reject_dispatches_kobo_sync(
        self, mock_async,
    ):
        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-sync-001/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        mock_async.assert_called_once()
        args = mock_async.call_args[0]
        self.assertEqual(
            args[6],
            ApprovalStatus.REJECTED,
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_no_kobo_credentials_skips_sync(
        self, mock_async,
    ):
        """User without Kobo creds still gets 200
        but async_task is not dispatched."""
        from api.v1.v1_users.models import SystemUser

        user2 = SystemUser.objects.create_superuser(
            email="nocreds@test.local",
            password="Changeme123",
            name="nocreds",
        )
        # No kobo_url, kobo_username, kobo_password
        from rest_framework_simplejwt.tokens import (
            AccessToken,
        )

        token = str(AccessToken.for_user(user2))
        auth2 = {
            "HTTP_AUTHORIZATION": (
                f"Bearer {token}"
            ),
        }

        resp = self.client.patch(
            "/api/v1/odk/submissions/"
            "sub-sync-001/",
            {
                "approval_status": (
                    ApprovalStatus.APPROVED
                ),
            },
            content_type="application/json",
            **auth2,
        )
        self.assertEqual(resp.status_code, 200)
        mock_async.assert_not_called()
