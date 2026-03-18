from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    FormMetadata,
    FormQuestion,
    Plot,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)

VALID_WKT = (
    "POLYGON(("
    "38.47 7.05,"
    "38.48 7.05,"
    "38.48 7.06,"
    "38.47 7.06,"
    "38.47 7.05))"
)


def _setup_form():
    """Create a minimal form for KML tests."""
    form = FormMetadata.objects.create(
        asset_uid="kml-form",
        name="KML Test Form",
        polygon_field="geoshape",
    )
    FormQuestion.objects.create(
        form=form,
        name="First_Name",
        label="First name",
        type="text",
    )
    return form


def _create_plot(form, kobo_id, wkt=VALID_WKT):
    """Create a submission + plot pair."""
    sub = Submission.objects.create(
        uuid=f"uuid-{kobo_id}",
        form=form,
        kobo_id=kobo_id,
        submission_time=1700000000000,
        raw_data={"First_Name": "Test"},
    )
    return Plot.objects.create(
        submission=sub,
        form=form,
        plot_name=f"Plot {kobo_id}",
        polygon_wkt=wkt,
        min_lat=7.05,
        max_lat=7.06,
        min_lon=38.47,
        max_lon=38.48,
        region="Amhara",
        sub_region="Bahir Dar",
        created_at=1700000000000,
    )


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    STORAGE_SECRET="test-secret",
)
class PlotKmlEndpointTest(
    TestCase, OdkTestHelperMixin
):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.form = _setup_form()
        self.plot = _create_plot(
            self.form, "201"
        )

    def test_valid_key_returns_kml(self):
        url = (
            f"/api/v1/odk/plots/"
            f"{self.plot.uuid}/kml/"
            f"?key={settings.STORAGE_SECRET}"
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "google-earth",
            resp["Content-Type"],
        )
        content = resp.content.decode()
        self.assertIn("<kml", content)
        self.assertIn("<coordinates>", content)

    def test_invalid_key_returns_403(self):
        url = (
            f"/api/v1/odk/plots/"
            f"{self.plot.uuid}/kml/"
            f"?key=wrong-key"
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_missing_key_returns_403(self):
        url = (
            f"/api/v1/odk/plots/"
            f"{self.plot.uuid}/kml/"
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_no_polygon_returns_404(self):
        plot = _create_plot(
            self.form, "202", wkt=None
        )
        url = (
            f"/api/v1/odk/plots/"
            f"{plot.uuid}/kml/"
            f"?key={settings.STORAGE_SECRET}"
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)
