from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import FormMetadata, Submission
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin


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
        # List should NOT include raw_data
        self.assertNotIn("raw_data", results[0])

    def test_filter_by_asset_uid(self):
        form_y = FormMetadata.objects.create(
            asset_uid="formY", name="Form Y"
        )
        Submission.objects.create(
            uuid="sub-002",
            form=form_y,
            kobo_id="200",
            submission_time=1700000001000,
            raw_data={},
        )
        resp = self.client.get(
            "/api/v1/odk/submissions/"
            "?asset_uid=formX",
            **self.auth,
        )
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["uuid"], "sub-001"
        )

    def test_retrieve_submission_detail(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/sub-001/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("raw_data", data)
        self.assertIn("system_data", data)

    def test_latest_sync_time(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/"
            "latest_sync_time/?asset_uid=formX",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["latest_submission_time"],
            1700000000000,
        )

    def test_latest_sync_time_missing_param(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/"
            "latest_sync_time/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)
