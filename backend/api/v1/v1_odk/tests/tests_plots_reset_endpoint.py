from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import FormMetadata, Plot, Submission
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin

VALID_GEOSHAPE = (
    "7.05 38.47 0 0;"
    "7.06 38.47 0 0;"
    "7.06 38.48 0 0;"
    "7.05 38.48 0 0;"
    "7.05 38.47 0 0"
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class PlotResetPolygonTest(TestCase, OdkTestHelperMixin):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="form1",
            name="Form 1",
            polygon_field="geoshape",
            plot_name_field="farmer_name",
        )

    def _create_submission_with_geo(self):
        return Submission.objects.create(
            uuid="sub-reset-001",
            form=self.form,
            kobo_id="200",
            submission_time=1700000000000,
            raw_data={
                "geoshape": VALID_GEOSHAPE,
                "farmer_name": "Farmer B",
            },
        )

    def _create_plot_with_edited_geo(self):
        sub = self._create_submission_with_geo()
        return Plot.objects.create(
            submission=sub,
            form=self.form,
            plot_name="Farmer B",
            instance_name="inst-2",
            polygon_wkt="POLYGON((0 0,1 0,1 1,0 0))",
            min_lat=0.0,
            max_lat=1.0,
            min_lon=0.0,
            max_lon=1.0,
            region="",
            sub_region="",
            created_at=1700000000000,
        )

    def test_reset_restores_original_polygon(self):
        plot = self._create_plot_with_edited_geo()
        self.assertEqual(
            plot.polygon_wkt,
            "POLYGON((0 0,1 0,1 1,0 0))",
        )

        resp = self.client.post(
            f"/api/v1/odk/plots/{plot.uuid}" "/reset_polygon/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)

        plot.refresh_from_db()
        self.assertIn("38.47", plot.polygon_wkt)
        self.assertIsNotNone(plot.min_lat)
        self.assertIsNotNone(plot.max_lat)
        self.assertIsNotNone(plot.min_lon)
        self.assertIsNotNone(plot.max_lon)

    def test_reset_no_linked_submission(self):
        plot = Plot.objects.create(
            submission=None,
            form=self.form,
            plot_name="Orphan",
            instance_name="inst-3",
            polygon_wkt="POLYGON((0 0,1 0,1 1,0 0))",
            min_lat=0.0,
            max_lat=1.0,
            min_lon=0.0,
            max_lon=1.0,
            region="",
            sub_region="",
            created_at=1700000000000,
        )
        resp = self.client.post(
            f"/api/v1/odk/plots/{plot.uuid}" "/reset_polygon/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertEqual(data["message"], "No linked submission")

    def test_reset_submission_no_polygon_data(self):
        sub = Submission.objects.create(
            uuid="sub-reset-nopoly",
            form=self.form,
            kobo_id="201",
            submission_time=1700000000000,
            raw_data={"farmer_name": "No Geo"},
        )
        plot = Plot.objects.create(
            submission=sub,
            form=self.form,
            plot_name="No Geo",
            instance_name="inst-4",
            polygon_wkt="POLYGON((0 0,1 0,1 1,0 0))",
            min_lat=0.0,
            max_lat=1.0,
            min_lon=0.0,
            max_lon=1.0,
            region="",
            sub_region="",
            created_at=1700000000000,
        )
        resp = self.client.post(
            f"/api/v1/odk/plots/{plot.uuid}" "/reset_polygon/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)

        plot.refresh_from_db()
        self.assertIsNone(plot.polygon_wkt)
        self.assertIsNone(plot.min_lat)

    def test_reset_requires_authentication(self):
        plot = self._create_plot_with_edited_geo()
        resp = self.client.post(
            f"/api/v1/odk/plots/{plot.uuid}" "/reset_polygon/",
        )
        self.assertEqual(resp.status_code, 401)
