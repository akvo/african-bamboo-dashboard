from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import FormMetadata, Plot
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class PlotViewTest(TestCase, OdkTestHelperMixin):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="form1", name="Form 1",
        )
        self.plot_data = {
            "plot_name": "Farmer A",
            "instance_name": "inst-1",
            "polygon_wkt": (
                "POLYGON((0 0,1 0,1 1,0 0))"
            ),
            "min_lat": 0.0,
            "max_lat": 1.0,
            "min_lon": 0.0,
            "max_lon": 1.0,
            "form_id": "form1",
            "region": "Region A",
            "sub_region": "Sub A",
            "created_at": 1700000000000,
        }

    def _create_plot(self, **overrides):
        """Create a Plot via ORM using FK reference."""
        data = {**self.plot_data}
        data.pop("form_id")
        data["form"] = self.form
        data.update(overrides)
        return Plot.objects.create(**data)

    def test_create_plot(self):
        resp = self.client.post(
            "/api/v1/odk/plots/",
            self.plot_data,
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            resp.json()["plot_name"], "Farmer A"
        )

    def test_list_plots(self):
        self._create_plot()
        resp = self.client.get(
            "/api/v1/odk/plots/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            len(resp.json()["results"]), 1
        )

    def test_filter_by_form_id(self):
        self._create_plot()
        resp = self.client.get(
            "/api/v1/odk/plots/?form_id=form1",
            **self.auth,
        )
        self.assertEqual(
            len(resp.json()["results"]), 1
        )
        resp2 = self.client.get(
            "/api/v1/odk/plots/?form_id=other",
            **self.auth,
        )
        self.assertEqual(
            len(resp2.json()["results"]), 0
        )

    def test_filter_by_is_draft(self):
        self._create_plot()
        resp = self.client.get(
            "/api/v1/odk/plots/?is_draft=true",
            **self.auth,
        )
        self.assertEqual(
            len(resp.json()["results"]), 1
        )
        resp2 = self.client.get(
            "/api/v1/odk/plots/?is_draft=false",
            **self.auth,
        )
        self.assertEqual(
            len(resp2.json()["results"]), 0
        )

    def test_overlap_candidates(self):
        self._create_plot()
        resp = self.client.post(
            "/api/v1/odk/plots/"
            "overlap_candidates/",
            {
                "min_lat": 0.5,
                "max_lat": 1.5,
                "min_lon": 0.5,
                "max_lon": 1.5,
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_overlap_no_match(self):
        self._create_plot()
        resp = self.client.post(
            "/api/v1/odk/plots/"
            "overlap_candidates/",
            {
                "min_lat": 10.0,
                "max_lat": 11.0,
                "min_lon": 10.0,
                "max_lon": 11.0,
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 0)

    def test_overlap_exclude_uuid(self):
        plot = self._create_plot()
        resp = self.client.post(
            "/api/v1/odk/plots/"
            "overlap_candidates/",
            {
                "min_lat": 0.5,
                "max_lat": 1.5,
                "min_lon": 0.5,
                "max_lon": 1.5,
                "exclude_uuid": str(plot.uuid),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 0)
