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


# Valid polygon: ~111m x 111m square near Addis
VALID_WKT = (
    "POLYGON(("
    "38.7 9.0, 38.701 9.0, "
    "38.701 9.001, 38.7 9.001, "
    "38.7 9.0))"
)

# Overlapping polygon: shares area with VALID_WKT
OVERLAP_WKT = (
    "POLYGON(("
    "38.7005 9.0, 38.7015 9.0, "
    "38.7015 9.001, 38.7005 9.001, "
    "38.7005 9.0))"
)

# Too-small polygon (< 10 sq meters)
TINY_WKT = (
    "POLYGON(("
    "38.7 9.0, 38.70001 9.0, "
    "38.70001 9.00001, 38.7 9.00001, "
    "38.7 9.0))"
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class RevertToPendingRechecksPlotTest(
    TestCase, OdkTestHelperMixin
):
    """Reverting a submission to pending re-runs
    polygon validation and overlap detection on
    the linked plot."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formRevert",
            name="Form Revert",
        )

    def _create_sub_and_plot(
        self, uuid, kobo_id, wkt, **kwargs
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
            "polygon_wkt": wkt,
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

    def _revert(self, uuid):
        return self.client.patch(
            f"/api/v1/odk/submissions/{uuid}/",
            {"approval_status": None},
            content_type="application/json",
            **self.auth,
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_revert_redetects_overlap(
        self, mock_async
    ):
        """Two overlapping plots: approve both
        (flags cleared), revert one -> overlap
        re-flagged on both."""
        sub_a, plot_a = self._create_sub_and_plot(
            "rev-001", "700", VALID_WKT,
        )
        sub_b, plot_b = self._create_sub_and_plot(
            "rev-002",
            "701",
            OVERLAP_WKT,
            min_lon=38.7005,
            max_lon=38.7015,
        )
        # Approve both -> flags cleared
        self._approve("rev-001")
        self._approve("rev-002")
        plot_a.refresh_from_db()
        plot_b.refresh_from_db()
        self.assertFalse(plot_a.flagged_for_review)
        self.assertFalse(plot_b.flagged_for_review)

        # Revert plot_a -> overlap re-detected
        resp = self._revert("rev-001")
        self.assertEqual(resp.status_code, 200)

        plot_a.refresh_from_db()
        plot_b.refresh_from_db()
        self.assertTrue(plot_a.flagged_for_review)
        self.assertIn(
            "overlaps", plot_a.flagged_reason
        )
        # The overlapping plot_b also gets flagged
        self.assertTrue(plot_b.flagged_for_review)

    @patch("api.v1.v1_odk.views.async_task")
    def test_revert_clean_polygon_not_flagged(
        self, mock_async
    ):
        """A valid non-overlapping plot reverted
        to pending -> flagged_for_review=False."""
        sub, plot = self._create_sub_and_plot(
            "rev-003", "702", VALID_WKT,
        )
        self._approve("rev-003")
        plot.refresh_from_db()
        self.assertFalse(plot.flagged_for_review)

        resp = self._revert("rev-003")
        self.assertEqual(resp.status_code, 200)

        plot.refresh_from_db()
        self.assertFalse(plot.flagged_for_review)
        self.assertIsNone(plot.flagged_reason)

    @patch("api.v1.v1_odk.views.async_task")
    def test_revert_invalid_polygon_flags_plot(
        self, mock_async
    ):
        """A plot with too-small polygon reverted
        to pending -> re-flagged for review."""
        sub, plot = self._create_sub_and_plot(
            "rev-004",
            "703",
            TINY_WKT,
        )
        # Force-approve (flags cleared by
        # serializer)
        self._approve("rev-004")
        plot.refresh_from_db()
        self.assertFalse(plot.flagged_for_review)

        resp = self._revert("rev-004")
        self.assertEqual(resp.status_code, 200)

        plot.refresh_from_db()
        self.assertTrue(plot.flagged_for_review)
        self.assertIn(
            "too small", plot.flagged_reason
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_revert_no_polygon_flags_plot(
        self, mock_async
    ):
        """A plot with no polygon_wkt reverted
        to pending -> flagged for review."""
        sub, plot = self._create_sub_and_plot(
            "rev-005",
            "704",
            None,
            min_lat=None,
            max_lat=None,
            min_lon=None,
            max_lon=None,
        )
        self._approve("rev-005")
        plot.refresh_from_db()
        self.assertFalse(plot.flagged_for_review)

        resp = self._revert("rev-005")
        self.assertEqual(resp.status_code, 200)

        plot.refresh_from_db()
        self.assertTrue(plot.flagged_for_review)
        self.assertIn(
            "No polygon data",
            plot.flagged_reason,
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_revert_without_plot_no_error(
        self, mock_async
    ):
        """Submission without a linked plot reverted
        to pending -> no crash."""
        sub = Submission.objects.create(
            uuid="rev-006",
            form=self.form,
            kobo_id="705",
            submission_time=1700000000000,
            raw_data={},
            approval_status=ApprovalStatus.APPROVED,
        )
        resp = self._revert("rev-006")
        self.assertEqual(resp.status_code, 200)
        sub.refresh_from_db()
        self.assertIsNone(sub.approval_status)

    @patch("api.v1.v1_odk.views.async_task")
    def test_revert_dispatches_kobo_sync(
        self, mock_async
    ):
        """Reverting to pending dispatches Kobo
        sync with PENDING status."""
        sub, plot = self._create_sub_and_plot(
            "rev-007",
            "706",
            VALID_WKT,
        )
        sub.approval_status = (
            ApprovalStatus.APPROVED
        )
        sub.save()

        resp = self._revert("rev-007")
        self.assertEqual(resp.status_code, 200)

        mock_async.assert_called()
        args = mock_async.call_args[0]
        self.assertEqual(
            args[0],
            "api.v1.v1_odk.tasks"
            ".sync_kobo_validation_status",
        )
        # approval_status=None maps to PENDING=0
        self.assertEqual(args[6], 0)
