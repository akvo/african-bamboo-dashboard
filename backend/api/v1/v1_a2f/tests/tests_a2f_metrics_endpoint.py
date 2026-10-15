import os

from django.core.management import call_command
from django.test import TestCase, override_settings

from api.v1.v1_a2f.models import A2FSnapshot
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin

FIXTURE = "api/v1/v1_a2f/tests/fixtures/a2f_dummy.xlsx"
URL = "/api/v1/a2f/metrics/"


@override_settings(A2F_ENABLED=True)
class A2FMetricsEndpointTest(OdkTestHelperMixin, TestCase):
    def setUp(self):
        call_command("import_a2f", FIXTURE, stdout=open(os.devnull, "w"))
        self.create_kobo_user()
        self.header = self.get_auth_header()

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(URL).status_code, 401)

    @override_settings(A2F_ENABLED=False)
    def test_hidden_when_flag_off(self):
        resp = self.client.get(URL, **self.header)
        self.assertEqual(resp.status_code, 404)

    def test_404_without_snapshot(self):
        A2FSnapshot.objects.all().delete()
        resp = self.client.get(URL, **self.header)
        self.assertEqual(resp.status_code, 404)

    def test_returns_metrics_and_options(self):
        resp = self.client.get(URL, **self.header)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["data_as_of"], "2026-09-30")
        self.assertEqual(data["reach"]["borrowers"], 29)
        self.assertEqual(data["filter_options"]["regions"], [
            "Oromia", "Sidama",
        ])

    def test_applies_filters_and_ignores_blanks(self):
        resp = self.client.get(
            URL, {"region": "Oromia", "woreda": ""}, **self.header
        )
        data = resp.json()
        self.assertEqual(data["reach"]["members"], 6)
        self.assertEqual(len(data["filter_options"]["cooperatives"]), 6)
