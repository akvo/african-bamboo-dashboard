from django.core.management import call_command
from django.test import TestCase

from api.v1.v1_odk.models import FieldSettings


class SeedFieldSettingsCommandTest(TestCase):
    """Tests for seed_field_settings management
    command."""

    def test_creates_all_expected_entries(self):
        """Command creates all 4 expected
        FieldSettings entries."""
        call_command("seed_field_settings")
        self.assertEqual(
            FieldSettings.objects.count(), 4
        )
        expected = [
            "enumerator",
            "farmer",
            "age_of_farmer",
            "phone_number",
        ]
        for name in expected:
            self.assertTrue(
                FieldSettings.objects.filter(
                    name=name
                ).exists(),
                f"Missing: {name}",
            )

    def test_idempotent_no_duplicates(self):
        """Running twice does not create
        duplicates."""
        call_command("seed_field_settings")
        call_command("seed_field_settings")
        self.assertEqual(
            FieldSettings.objects.count(), 4
        )
