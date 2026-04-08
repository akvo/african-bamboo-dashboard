from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    ApprovalStatus,
    FormMetadata,
    MainPlot,
    MainPlotSubmission,
    Plot,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)


VALID_WKT = (
    "POLYGON(("
    "38.7 9.0, 38.701 9.0, "
    "38.701 9.001, 38.7 9.001, "
    "38.7 9.0))"
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class PlotIdGenerationTest(
    TestCase, OdkTestHelperMixin
):
    """Test Plot ID (MainPlot) generation on
    submission approval."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formPlotId",
            name="Form Plot ID",
        )

    def _create_sub_and_plot(
        self, uuid, kobo_id, **kwargs
    ):
        sub = Submission.objects.create(
            uuid=uuid,
            form=self.form,
            kobo_id=kobo_id,
            submission_time=1700000000000,
            submitted_by="tester",
            instance_name=f"Instance {uuid}",
            raw_data={"q1": "a1"},
        )
        plot_defaults = {
            "plot_name": f"Plot {uuid}",
            "polygon_wkt": VALID_WKT,
            "min_lat": 9.0,
            "max_lat": 9.001,
            "min_lon": 38.7,
            "max_lon": 38.701,
            "form": self.form,
            "region": "R",
            "sub_region": "S",
            "created_at": 1700000000000,
            "submission": sub,
            "flagged_for_review": False,
            "flagged_reason": None,
        }
        plot_defaults.update(kwargs)
        plot = Plot.objects.create(**plot_defaults)
        return sub, plot

    def _approve(self, uuid):
        return self.client.patch(
            f"/api/v1/odk/submissions/{uuid}/",
            {
                "approval_status": (
                    ApprovalStatus.APPROVED
                ),
            },
            content_type="application/json",
            **self.auth,
        )

    def _reject(self, uuid):
        return self.client.patch(
            f"/api/v1/odk/submissions/{uuid}/",
            {
                "approval_status": (
                    ApprovalStatus.REJECTED
                ),
                "reason_category": "other",
                "reason_text": "test rejection",
            },
            content_type="application/json",
            **self.auth,
        )

    def _revert(self, uuid):
        return self.client.patch(
            f"/api/v1/odk/submissions/{uuid}/",
            {"approval_status": None},
            content_type="application/json",
            **self.auth,
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_approve_creates_main_plot(
        self, mock_async
    ):
        """Approving a submission creates a MainPlot
        with PLT00001 format."""
        sub, plot = self._create_sub_and_plot(
            "pid-001", "100",
        )
        resp = self._approve("pid-001")
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(MainPlot.objects.count(), 1)
        main_plot = MainPlot.objects.first()
        self.assertEqual(main_plot.uid, "PLT00001")
        self.assertEqual(main_plot.form, self.form)

        mps = MainPlotSubmission.objects.first()
        self.assertEqual(
            mps.main_plot, main_plot,
        )
        self.assertEqual(mps.submission, sub)

    @patch("api.v1.v1_odk.views.async_task")
    def test_approve_respects_uid_start(
        self, mock_async
    ):
        """With plot_uid_start=351, first plot is
        PLT00351."""
        self.form.plot_uid_start = 351
        self.form.save()

        sub, plot = self._create_sub_and_plot(
            "pid-002", "101",
        )
        self._approve("pid-002")

        main_plot = MainPlot.objects.first()
        self.assertEqual(main_plot.uid, "PLT00351")

    @patch("api.v1.v1_odk.views.async_task")
    def test_approve_sequential(self, mock_async):
        """Second approval gets PLT00002."""
        sub1, _ = self._create_sub_and_plot(
            "pid-003", "102",
        )
        sub2, _ = self._create_sub_and_plot(
            "pid-004", "103",
        )

        self._approve("pid-003")
        self._approve("pid-004")

        uids = list(
            MainPlot.objects.order_by("uid")
            .values_list("uid", flat=True)
        )
        self.assertEqual(uids, [
            "PLT00001", "PLT00002",
        ])

    @patch("api.v1.v1_odk.views.async_task")
    def test_approve_idempotent(self, mock_async):
        """Approving same submission twice doesn't
        create duplicate."""
        sub, _ = self._create_sub_and_plot(
            "pid-005", "104",
        )
        self._approve("pid-005")
        self._approve("pid-005")

        self.assertEqual(MainPlot.objects.count(), 1)
        self.assertEqual(
            MainPlotSubmission.objects.count(), 1,
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_revert_keeps_plot_id(
        self, mock_async
    ):
        """Reverting to pending keeps
        MainPlotSubmission and MainPlot."""
        sub, _ = self._create_sub_and_plot(
            "pid-006", "105",
        )
        self._approve("pid-006")
        self.assertEqual(
            MainPlotSubmission.objects.count(), 1,
        )

        self._revert("pid-006")
        self.assertEqual(
            MainPlotSubmission.objects.count(), 1,
        )
        self.assertEqual(MainPlot.objects.count(), 1)

    @patch("api.v1.v1_odk.views.async_task")
    def test_reject_no_main_plot(self, mock_async):
        """Rejecting does not create a MainPlot."""
        sub, _ = self._create_sub_and_plot(
            "pid-007", "106",
        )
        self._reject("pid-007")

        self.assertEqual(MainPlot.objects.count(), 0)

    @patch("api.v1.v1_odk.views.async_task")
    def test_reject_after_approve_keeps_plot_id(
        self, mock_async
    ):
        """Approving then rejecting keeps the
        MainPlotSubmission link."""
        sub, _ = self._create_sub_and_plot(
            "pid-008", "107",
        )
        self._approve("pid-008")
        self.assertEqual(
            MainPlotSubmission.objects.count(), 1,
        )

        self._reject("pid-008")
        self.assertEqual(
            MainPlotSubmission.objects.count(), 1,
        )
        self.assertEqual(MainPlot.objects.count(), 1)

    @patch("api.v1.v1_odk.views.async_task")
    def test_approve_without_plot_no_error(
        self, mock_async
    ):
        """Submission without a linked plot approved
        -> no crash, no MainPlot created."""
        Submission.objects.create(
            uuid="pid-009",
            form=self.form,
            kobo_id="108",
            submission_time=1700000000000,
            raw_data={},
        )
        resp = self._approve("pid-009")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(MainPlot.objects.count(), 0)

    @patch("api.v1.v1_odk.views.async_task")
    def test_search_by_plot_id(self, mock_async):
        """Search param matches MainPlot.uid."""
        sub, _ = self._create_sub_and_plot(
            "pid-010", "109",
        )
        self._approve("pid-010")

        resp = self.client.get(
            "/api/v1/odk/submissions/",
            {
                "asset_uid": "formPlotId",
                "search": "PLT00001",
            },
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["uuid"], "pid-010",
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_plot_serializer_includes_main_plot_uid(
        self, mock_async
    ):
        """PlotSerializer returns main_plot_uid."""
        sub, plot = self._create_sub_and_plot(
            "pid-011", "110",
        )
        self._approve("pid-011")

        resp = self.client.get(
            "/api/v1/odk/plots/",
            {"form_id": "formPlotId"},
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["main_plot_uid"], "PLT00001",
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_submission_list_includes_main_plot_uid(
        self, mock_async
    ):
        """SubmissionListSerializer returns
        main_plot_uid."""
        sub, _ = self._create_sub_and_plot(
            "pid-012", "111",
        )
        self._approve("pid-012")

        resp = self.client.get(
            "/api/v1/odk/submissions/",
            {"asset_uid": "formPlotId"},
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["main_plot_uid"], "PLT00001",
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_pending_submission_main_plot_uid_null(
        self, mock_async
    ):
        """Pending submission has null
        main_plot_uid."""
        sub, _ = self._create_sub_and_plot(
            "pid-013", "112",
        )
        resp = self.client.get(
            "/api/v1/odk/submissions/",
            {"asset_uid": "formPlotId"},
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0]["main_plot_uid"])
