from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import FormMetadata, Submission
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin


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
        self.assertTrue(
            FormMetadata.objects.filter(
                asset_uid="formB"
            ).exists()
        )

    def test_retrieve_form(self):
        resp = self.client.get(
            "/api/v1/odk/forms/formA/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["asset_uid"], "formA"
        )
        self.assertEqual(
            resp.json()["submission_count"], 0
        )

    def test_delete_form(self):
        resp = self.client.delete(
            "/api/v1/odk/forms/formA/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(
            FormMetadata.objects.filter(
                asset_uid="formA"
            ).exists()
        )

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(
            "/api/v1/odk/forms/",
        )
        self.assertEqual(resp.status_code, 401)

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_sync_action(self, mock_client_cls):
        mock_client_cls.return_value\
            .fetch_all_submissions.return_value = [
                {
                    "_uuid": "uuid-s1",
                    "_id": 1,
                    "_submission_time": (
                        "2024-01-15T10:30:00+00:00"
                    ),
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
        self.assertTrue(
            Submission.objects.filter(
                uuid="uuid-s1"
            ).exists()
        )
        self.form.refresh_from_db()
        self.assertGreater(
            self.form.last_sync_timestamp, 0
        )
