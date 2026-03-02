from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import FormMetadata, Plot, Submission
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin

VALID_POLYGON = (
    "0.0 0.0 0 0; "
    "0.001 0.0 0 0; "
    "0.001 0.001 0 0; "
    "0.0 0.001 0 0; "
    "0.0 0.0 0 0"
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormMetadataViewTest(TestCase, OdkTestHelperMixin):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formA",
            name="Form A",
        )

    def test_list_forms(self):
        resp = self.client.get(
            "/api/v1/odk/forms/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["results"]), 1)

    def test_create_form(self):
        resp = self.client.post(
            "/api/v1/odk/forms/",
            {
                "asset_uid": "formB",
                "name": "Form B",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(FormMetadata.objects.filter(asset_uid="formB").exists())

    def test_retrieve_form(self):
        resp = self.client.get(
            "/api/v1/odk/forms/formA/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["asset_uid"], "formA")
        self.assertEqual(resp.json()["submission_count"], 0)

    def test_delete_form(self):
        resp = self.client.delete(
            "/api/v1/odk/forms/formA/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(
            FormMetadata.objects.filter(asset_uid="formA").exists()
        )

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(
            "/api/v1/odk/forms/",
        )
        self.assertEqual(resp.status_code, 401)

    def test_form_includes_field_mappings(self):
        self.form.polygon_field = "boundary"
        self.form.region_field = "region"
        self.form.save()
        resp = self.client.get(
            "/api/v1/odk/forms/formA/",
            **self.auth,
        )
        data = resp.json()
        self.assertEqual(data["polygon_field"], "boundary")
        self.assertEqual(data["region_field"], "region")
        self.assertIsNone(data["sub_region_field"])
        self.assertIsNone(data["plot_name_field"])

    def test_update_field_mappings(self):
        resp = self.client.patch(
            "/api/v1/odk/forms/formA/",
            {
                "polygon_field": ("boundary_mapping/" "Open_Area_GeoMapping"),
                "plot_name_field": (
                    "First_Name," "Father_s_Name," "Grandfather_s_Name"
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.form.refresh_from_db()
        self.assertEqual(
            self.form.polygon_field,
            "boundary_mapping/" "Open_Area_GeoMapping",
        )
        self.assertIn(
            "First_Name",
            self.form.plot_name_field,
        )

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_form_fields(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.get_asset_detail.return_value = {
            "survey": [
                {
                    "name": "start",
                    "type": "start",
                    "$xpath": "start",
                },
                {
                    "name": "end",
                    "type": "end",
                    "$xpath": "end",
                },
                {
                    "name": "calc1",
                    "type": "calculate",
                    "$xpath": "calc1",
                },
                {
                    "name": "note1",
                    "type": "note",
                    "$xpath": "note1",
                },
                {
                    "name": "grp",
                    "type": "begin_group",
                    "$xpath": "grp",
                },
                {
                    "name": "region",
                    "type": "select_one",
                    "label": ["Region"],
                    "$xpath": "region",
                },
                {
                    "name": "First_Name",
                    "type": "text",
                    "label": ["First name"],
                    "$xpath": ("consent_group/" "consented/" "First_Name"),
                },
                {
                    "name": "boundary",
                    "type": "geoshape",
                    "label": [
                        "Auto Boundary",
                    ],
                    "$xpath": (
                        "consent_group/"
                        "consented/"
                        "boundary_mapping/"
                        "boundary"
                    ),
                },
                {
                    "name": "grp",
                    "type": "end_group",
                    "$xpath": "grp",
                },
            ],
        }
        resp = self.client.get(
            "/api/v1/odk/forms/formA/form_fields/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        fields = resp.json()["fields"]
        names = [f["name"] for f in fields]
        # Skipped types filtered out
        self.assertNotIn("start", names)
        self.assertNotIn("end", names)
        self.assertNotIn("calc1", names)
        self.assertNotIn("note1", names)
        self.assertNotIn("grp", names)
        # Data fields included
        self.assertIn("region", names)
        self.assertIn("First_Name", names)
        self.assertIn("boundary", names)
        self.assertEqual(len(fields), 3)
        # Check structure
        region = fields[0]
        self.assertEqual(region["type"], "select_one")
        self.assertEqual(region["label"], "Region")
        self.assertEqual(region["full_path"], "region")
        boundary = fields[2]
        self.assertIn(
            "boundary_mapping/boundary",
            boundary["full_path"],
        )

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_form_fields_no_credentials(self, mock_client_cls):
        self.user.kobo_url = ""
        self.user.save()
        resp = self.client.get(
            "/api/v1/odk/forms/formA/form_fields/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_sync_action(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.fetch_all_submissions.return_value = [
            {
                "_uuid": "uuid-s1",
                "_id": 1,
                "_submission_time": ("2024-01-15T10:30:00" "+00:00"),
                "_submitted_by": "user1",
                "meta/instanceName": "inst1",
                "_geolocation": [9.0, 38.7],
                "_tags": [],
                "field1": "value1",
            },
        ]
        resp = self.client.post(
            "/api/v1/odk/forms/formA/sync/",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["synced"], 1)
        self.assertEqual(data["created"], 1)
        self.assertTrue(Submission.objects.filter(uuid="uuid-s1").exists())
        self.form.refresh_from_db()
        self.assertGreater(self.form.last_sync_timestamp, 0)
        # Plot always created
        self.assertEqual(data["plots_created"], 1)
        self.assertTrue(
            Plot.objects.filter(submission__uuid="uuid-s1").exists()
        )

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_sync_creates_plot_with_geometry(self, mock_client_cls):
        self.form.polygon_field = "boundary"
        self.form.region_field = "region"
        self.form.sub_region_field = "woreda"
        self.form.plot_name_field = "First_Name,Father_s_Name"
        self.form.save()

        mock_client = mock_client_cls.return_value
        mock_client.fetch_all_submissions.return_value = [
            {
                "_uuid": "uuid-s2",
                "_id": 2,
                "_submission_time": ("2024-01-15T10:30:00" "+00:00"),
                "_submitted_by": "user1",
                "meta/instanceName": "inst2",
                "_geolocation": [9.0, 38.7],
                "_tags": [],
                "boundary": VALID_POLYGON,
                "region": "Oromia",
                "woreda": "Jimma",
                "First_Name": "Abebe",
                "Father_s_Name": "Kebede",
            },
        ]
        resp = self.client.post(
            "/api/v1/odk/forms/formA/sync/",
            content_type="application/json",
            **self.auth,
        )
        data = resp.json()
        self.assertEqual(data["plots_created"], 1)
        plot = Plot.objects.get(submission__uuid="uuid-s2")
        self.assertEqual(plot.plot_name, "Abebe Kebede")
        self.assertEqual(plot.region, "Oromia")
        self.assertEqual(plot.sub_region, "Jimma")
        self.assertIsNotNone(plot.polygon_wkt)
        self.assertIsNotNone(plot.min_lat)

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_sync_creates_plot_null_geom(self, mock_client_cls):
        """Invalid polygon -> plot created
        with null geometry."""
        self.form.polygon_field = "boundary"
        self.form.save()

        mock_client = mock_client_cls.return_value
        mock_client.fetch_all_submissions.return_value = [
            {
                "_uuid": "uuid-s3",
                "_id": 3,
                "_submission_time": ("2024-01-15T10:30:00" "+00:00"),
                "_submitted_by": "user1",
                "meta/instanceName": "inst3",
                "_geolocation": [9.0, 38.7],
                "_tags": [],
                "boundary": "invalid data",
            },
        ]
        resp = self.client.post(
            "/api/v1/odk/forms/formA/sync/",
            content_type="application/json",
            **self.auth,
        )
        data = resp.json()
        self.assertEqual(data["plots_created"], 1)
        plot = Plot.objects.get(submission__uuid="uuid-s3")
        self.assertIsNone(plot.polygon_wkt)
        self.assertIsNone(plot.min_lat)

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_sync_resync_updates_plot(self, mock_client_cls):
        self.form.polygon_field = "boundary"
        self.form.plot_name_field = "farmer_name"
        self.form.save()

        submission_data = {
            "_uuid": "uuid-s4",
            "_id": 4,
            "_submission_time": ("2024-01-15T10:30:00+00:00"),
            "_submitted_by": "user1",
            "meta/instanceName": "inst4",
            "_geolocation": [9.0, 38.7],
            "_tags": [],
            "boundary": VALID_POLYGON,
            "farmer_name": "Abebe",
        }
        mock_client = mock_client_cls.return_value
        mock_client.fetch_all_submissions.return_value = [submission_data]

        # First sync
        self.client.post(
            "/api/v1/odk/forms/formA/sync/",
            content_type="application/json",
            **self.auth,
        )

        # Re-sync with updated name
        submission_data["farmer_name"] = "Updated"
        mock_client.fetch_all_submissions.return_value = [submission_data]
        resp = self.client.post(
            "/api/v1/odk/forms/formA/sync/",
            content_type="application/json",
            **self.auth,
        )
        data = resp.json()
        self.assertEqual(data["plots_updated"], 1)
        self.assertEqual(data["plots_created"], 0)
        self.assertEqual(Plot.objects.count(), 1)
        plot = Plot.objects.first()
        self.assertEqual(plot.plot_name, "Updated")


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormMappingRederiveTest(
    TestCase, OdkTestHelperMixin
):
    """Updating field mappings re-derives
    existing plots."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formRD",
            name="Rederive Form",
            region_field="region",
            sub_region_field="woreda",
            plot_name_field="first_name",
        )
        self.sub = Submission.objects.create(
            uuid="uuid-rd1",
            form=self.form,
            kobo_id="500",
            submission_time=1700000000000,
            submitted_by="user1",
            instance_name="inst-rd1",
            raw_data={
                "boundary": VALID_POLYGON,
                "region": "Oromia",
                "region_specify": "Zone 1",
                "woreda": "Jimma",
                "kebele": "K01",
                "first_name": "Abebe",
                "last_name": "Kebede",
            },
        )
        self.plot = Plot.objects.create(
            form=self.form,
            submission=self.sub,
            plot_name="Abebe",
            region="Oromia",
            sub_region="Jimma",
            created_at=1700000000000,
        )

    def test_update_mapping_rederives_plots(self):
        resp = self.client.patch(
            "/api/v1/odk/forms/formRD/",
            {
                "region_field": (
                    "region,region_specify"
                ),
                "sub_region_field": "woreda,kebele",
                "plot_name_field": (
                    "first_name,last_name"
                ),
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.plot.refresh_from_db()
        self.assertEqual(
            self.plot.region, "Oromia - Zone 1"
        )
        self.assertEqual(
            self.plot.sub_region, "Jimma - K01"
        )
        self.assertEqual(
            self.plot.plot_name, "Abebe Kebede"
        )

    def test_no_change_no_rederive(self):
        """If mappings don't change, plots stay
        the same."""
        self.plot.region = "Custom"
        self.plot.save()
        resp = self.client.patch(
            "/api/v1/odk/forms/formRD/",
            {"name": "Updated Name"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.plot.refresh_from_db()
        # Region was manually set, not rederived
        self.assertEqual(self.plot.region, "Custom")
