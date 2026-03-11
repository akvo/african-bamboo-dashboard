from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class FieldSettingsEndpointTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for GET /api/v1/odk/field-settings/."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        call_command("seed_field_settings")

    def test_returns_all_seeded_settings(self):
        """GET returns all seeded field settings."""
        resp = self.client.get(
            "/api/v1/odk/field-settings/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        names = [item["name"] for item in data]
        self.assertIn("enumerator", names)
        self.assertIn("farmer", names)
        self.assertIn("age_of_farmer", names)
        self.assertIn("phone_number", names)
        self.assertEqual(len(data), 4)

    def test_list_is_read_only(self):
        """POST returns 405 Method Not Allowed."""
        resp = self.client.post(
            "/api/v1/odk/field-settings/",
            {"name": "new_field"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 405)

    def test_unauthenticated_returns_401(self):
        """Unauthenticated request returns 401."""
        resp = self.client.get(
            "/api/v1/odk/field-settings/",
        )
        self.assertEqual(resp.status_code, 401)
