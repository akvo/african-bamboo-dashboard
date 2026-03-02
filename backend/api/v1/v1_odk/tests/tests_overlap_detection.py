from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    FormMetadata,
    Plot,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)
from utils.polygon import (
    _polygons_overlap,
    append_overlap_reason,
    build_overlap_reason,
    find_overlapping_plots,
)

# Two overlapping squares
WKT_SQUARE_A = (
    "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
)
WKT_SQUARE_B = (
    "POLYGON(("
    "0.5 0.5, 1.5 0.5, "
    "1.5 1.5, 0.5 1.5, "
    "0.5 0.5))"
)
# Non-overlapping square
WKT_SQUARE_FAR = (
    "POLYGON((10 10, 11 10, 11 11, 10 11, 10 10))"
)
# Edge-touching only (shares edge at x=1)
WKT_EDGE_TOUCH = (
    "POLYGON((1 0, 2 0, 2 1, 1 1, 1 0))"
)
# Corner-touching only (shares corner at 1,1)
WKT_CORNER_TOUCH = (
    "POLYGON((1 1, 2 1, 2 2, 1 2, 1 1))"
)
# Contained polygon (inside square A)
WKT_CONTAINED = (
    "POLYGON(("
    "0.2 0.2, 0.8 0.2, "
    "0.8 0.8, 0.2 0.8, "
    "0.2 0.2))"
)

# Valid ODK geoshape for sync tests
GEOSHAPE_A = (
    "0.0 0.0 0 0; "
    "0.001 0.0 0 0; "
    "0.001 0.001 0 0; "
    "0.0 0.001 0 0; "
    "0.0 0.0 0 0"
)
# Overlapping geoshape (shifted but overlaps)
GEOSHAPE_B = (
    "0.0005 0.0005 0 0; "
    "0.0015 0.0005 0 0; "
    "0.0015 0.0015 0 0; "
    "0.0005 0.0015 0 0; "
    "0.0005 0.0005 0 0"
)
# Non-overlapping geoshape (far away)
GEOSHAPE_FAR = (
    "10.0 10.0 0 0; "
    "10.001 10.0 0 0; "
    "10.001 10.001 0 0; "
    "10.0 10.001 0 0; "
    "10.0 10.0 0 0"
)


class PolygonsOverlapTest(TestCase):
    """Unit tests for _polygons_overlap."""

    def test_overlapping_squares(self):
        self.assertTrue(
            _polygons_overlap(
                WKT_SQUARE_A, WKT_SQUARE_B
            )
        )

    def test_non_overlapping_squares(self):
        self.assertFalse(
            _polygons_overlap(
                WKT_SQUARE_A, WKT_SQUARE_FAR
            )
        )

    def test_edge_touching_only(self):
        self.assertFalse(
            _polygons_overlap(
                WKT_SQUARE_A, WKT_EDGE_TOUCH
            )
        )

    def test_corner_touching_only(self):
        self.assertFalse(
            _polygons_overlap(
                WKT_SQUARE_A, WKT_CORNER_TOUCH
            )
        )

    def test_contained_polygon(self):
        self.assertTrue(
            _polygons_overlap(
                WKT_SQUARE_A, WKT_CONTAINED
            )
        )

    def test_invalid_wkt(self):
        self.assertFalse(
            _polygons_overlap(
                "not valid", WKT_SQUARE_A
            )
        )

    def test_empty_string(self):
        self.assertFalse(
            _polygons_overlap("", WKT_SQUARE_A)
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class FindOverlappingPlotsTest(TestCase):
    """Unit tests for find_overlapping_plots."""

    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="overlap-form",
            name="Overlap Form",
        )
        self.other_form = FormMetadata.objects.create(
            asset_uid="other-form",
            name="Other Form",
        )
        self.sub = Submission.objects.create(
            uuid="sub-overlap-1",
            form=self.form,
            kobo_id="200",
            submission_time=1700000000000,
            raw_data={},
        )
        self.plot = Plot.objects.create(
            form=self.form,
            submission=self.sub,
            plot_name="Existing Plot",
            polygon_wkt=WKT_SQUARE_A,
            min_lat=0.0,
            max_lat=1.0,
            min_lon=0.0,
            max_lon=1.0,
            region="R",
            sub_region="SR",
            created_at=1700000000000,
        )

    def test_finds_overlapping_plot(self):
        bbox = {
            "min_lat": 0.5,
            "max_lat": 1.5,
            "min_lon": 0.5,
            "max_lon": 1.5,
        }
        result = find_overlapping_plots(
            WKT_SQUARE_B,
            bbox,
            self.form.pk,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0].pk, self.plot.pk
        )

    def test_excludes_self(self):
        bbox = {
            "min_lat": 0.0,
            "max_lat": 1.0,
            "min_lon": 0.0,
            "max_lon": 1.0,
        }
        result = find_overlapping_plots(
            WKT_SQUARE_A,
            bbox,
            self.form.pk,
            exclude_pk=self.plot.pk,
        )
        self.assertEqual(len(result), 0)

    def test_different_form_not_matched(self):
        bbox = {
            "min_lat": 0.5,
            "max_lat": 1.5,
            "min_lon": 0.5,
            "max_lon": 1.5,
        }
        result = find_overlapping_plots(
            WKT_SQUARE_B,
            bbox,
            self.other_form.pk,
        )
        self.assertEqual(len(result), 0)

    def test_bbox_match_no_shapely_overlap(self):
        """Edge-touching: bbox overlaps but
        Shapely says no real overlap."""
        bbox = {
            "min_lat": 0.0,
            "max_lat": 1.0,
            "min_lon": 1.0,
            "max_lon": 2.0,
        }
        result = find_overlapping_plots(
            WKT_EDGE_TOUCH,
            bbox,
            self.form.pk,
        )
        self.assertEqual(len(result), 0)

    def test_plot_without_geometry_excluded(self):
        sub2 = Submission.objects.create(
            uuid="sub-overlap-2",
            form=self.form,
            kobo_id="201",
            submission_time=1700000000000,
            raw_data={},
        )
        Plot.objects.create(
            form=self.form,
            submission=sub2,
            plot_name="No Geom",
            polygon_wkt=None,
            region="R",
            sub_region="SR",
            created_at=1700000000000,
        )
        bbox = {
            "min_lat": -90.0,
            "max_lat": 90.0,
            "min_lon": -180.0,
            "max_lon": 180.0,
        }
        result = find_overlapping_plots(
            WKT_SQUARE_B,
            bbox,
            self.form.pk,
        )
        # Only the original plot with geometry
        self.assertEqual(len(result), 1)


@override_settings(USE_TZ=False, TEST_ENV=True)
class BuildOverlapReasonTest(TestCase):
    """Unit tests for build_overlap_reason."""

    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="reason-form",
            name="Reason Form",
        )

    def _make_plot(self, name, instance):
        sub = Submission.objects.create(
            uuid=f"sub-{instance}",
            form=self.form,
            kobo_id="1",
            submission_time=1700000000000,
            instance_name=instance,
            raw_data={},
        )
        p = Plot(
            plot_name=name,
            submission=sub,
        )
        return p

    def test_single_overlap(self):
        plots = [self._make_plot("Abebe", "inst1")]
        reason = build_overlap_reason(plots)
        self.assertEqual(
            reason,
            "Polygon overlaps with: "
            "Abebe (inst1)",
        )

    def test_multiple_overlaps(self):
        plots = [
            self._make_plot("Abebe", "inst1"),
            self._make_plot("Kebede", "inst2"),
        ]
        reason = build_overlap_reason(plots)
        self.assertIn("Abebe (inst1)", reason)
        self.assertIn("Kebede (inst2)", reason)

    def test_truncation(self):
        plots = [
            self._make_plot(
                "X" * 100, f"i{i}"
            )
            for i in range(10)
        ]
        reason = build_overlap_reason(plots)
        self.assertLessEqual(len(reason), 500)
        self.assertTrue(reason.endswith("..."))


class AppendOverlapReasonTest(TestCase):
    """Unit tests for append_overlap_reason."""

    def test_append_to_none(self):
        result = append_overlap_reason(
            None, "Abebe", "inst1"
        )
        self.assertEqual(
            result,
            "Polygon overlaps with: "
            "Abebe (inst1)",
        )

    def test_append_to_existing(self):
        existing = "No polygon data found."
        result = append_overlap_reason(
            existing, "Abebe", "inst1"
        )
        self.assertIn(
            "No polygon data found.", result
        )
        self.assertIn("Abebe (inst1)", result)
        self.assertIn("; ", result)

    def test_duplicate_prevention(self):
        existing = (
            "Polygon overlaps with: "
            "Abebe (inst1)"
        )
        result = append_overlap_reason(
            existing, "Abebe", "inst1"
        )
        self.assertEqual(result, existing)

    def test_truncation_on_append(self):
        existing = "X" * 490
        result = append_overlap_reason(
            existing, "Abebe", "inst1"
        )
        self.assertLessEqual(len(result), 500)
        self.assertTrue(result.endswith("..."))


@override_settings(USE_TZ=False, TEST_ENV=True)
class SyncOverlapDetectionTest(
    TestCase, OdkTestHelperMixin
):
    """Integration tests for overlap detection
    during sync."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="overlap-sync",
            name="Overlap Sync Form",
            polygon_field="boundary",
            plot_name_field="farmer_name",
        )

    def _make_submission(
        self, uuid, kobo_id, name, geoshape
    ):
        return {
            "_uuid": uuid,
            "_id": kobo_id,
            "_submission_time": (
                "2024-01-15T10:30:00+00:00"
            ),
            "_submitted_by": "user1",
            "meta/instanceName": f"inst-{uuid}",
            "_geolocation": [9.0, 38.7],
            "_tags": [],
            "boundary": geoshape,
            "farmer_name": name,
        }

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_sync_flags_both_on_overlap(
        self, mock_cls
    ):
        mock = mock_cls.return_value
        sub_a = self._make_submission(
            "uuid-a", 1, "Abebe", GEOSHAPE_A
        )
        sub_b = self._make_submission(
            "uuid-b", 2, "Kebede", GEOSHAPE_B
        )
        mock.fetch_all_submissions.return_value = [
            sub_a,
            sub_b,
        ]

        resp = self.client.post(
            "/api/v1/odk/forms/"
            "overlap-sync/sync/",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["plots_created"], 2)

        plot_a = Plot.objects.get(
            submission__uuid="uuid-a"
        )
        plot_b = Plot.objects.get(
            submission__uuid="uuid-b"
        )
        # Plot B is flagged for overlapping A
        self.assertTrue(plot_b.flagged_for_review)
        self.assertIn(
            "Abebe", plot_b.flagged_reason
        )
        # Plot A is flagged as overlapping too
        self.assertTrue(plot_a.flagged_for_review)
        self.assertIn(
            "Kebede", plot_a.flagged_reason
        )

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_sync_no_flag_no_overlap(
        self, mock_cls
    ):
        mock = mock_cls.return_value
        sub_a = self._make_submission(
            "uuid-a", 1, "Abebe", GEOSHAPE_A
        )
        sub_far = self._make_submission(
            "uuid-far", 2, "Faraway", GEOSHAPE_FAR
        )
        mock.fetch_all_submissions.return_value = [
            sub_a,
            sub_far,
        ]

        resp = self.client.post(
            "/api/v1/odk/forms/"
            "overlap-sync/sync/",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["plots_flagged"], 0)

        plot_a = Plot.objects.get(
            submission__uuid="uuid-a"
        )
        plot_far = Plot.objects.get(
            submission__uuid="uuid-far"
        )
        # Checked clean -> False
        self.assertIs(
            plot_a.flagged_for_review, False
        )
        self.assertIs(
            plot_far.flagged_for_review, False
        )

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_invalid_geom_not_checked(
        self, mock_cls
    ):
        """A plot with invalid geometry is not
        checked for overlap."""
        mock = mock_cls.return_value
        sub_a = self._make_submission(
            "uuid-a", 1, "Abebe", GEOSHAPE_A
        )
        sub_bad = self._make_submission(
            "uuid-bad", 2, "BadGeom", "invalid"
        )
        mock.fetch_all_submissions.return_value = [
            sub_a,
            sub_bad,
        ]

        resp = self.client.post(
            "/api/v1/odk/forms/"
            "overlap-sync/sync/",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)

        plot_a = Plot.objects.get(
            submission__uuid="uuid-a"
        )
        plot_bad = Plot.objects.get(
            submission__uuid="uuid-bad"
        )
        # Bad geom is flagged for geom issues
        self.assertTrue(
            plot_bad.flagged_for_review
        )
        # Good geom checked clean -> False
        self.assertIs(
            plot_a.flagged_for_review, False
        )

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_resync_no_self_overlap(
        self, mock_cls
    ):
        """Re-syncing the same submission does
        not cause self-overlap."""
        mock = mock_cls.return_value
        sub_a = self._make_submission(
            "uuid-a", 1, "Abebe", GEOSHAPE_A
        )
        mock.fetch_all_submissions.return_value = [
            sub_a,
        ]

        # First sync
        self.client.post(
            "/api/v1/odk/forms/"
            "overlap-sync/sync/",
            content_type="application/json",
            **self.auth,
        )

        # Re-sync same
        mock.fetch_all_submissions.return_value = [
            sub_a,
        ]
        resp = self.client.post(
            "/api/v1/odk/forms/"
            "overlap-sync/sync/",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)

        plot_a = Plot.objects.get(
            submission__uuid="uuid-a"
        )
        # Re-checked clean -> False
        self.assertIs(
            plot_a.flagged_for_review, False
        )
