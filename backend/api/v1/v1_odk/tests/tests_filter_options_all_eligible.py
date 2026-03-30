from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import FormMetadata, FormOption, FormQuestion
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin

URL = "/api/v1/odk/plots/filter_options/"


@override_settings(USE_TZ=False, TEST_ENV=True)
class FilterOptionsAllEligibleTest(TestCase, OdkTestHelperMixin):
    """Tests for GET filter_options with
    all_eligible=true."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formAE",
            name="All Eligible Form",
            region_field="region",
            sub_region_field="woreda",
            filter_fields=["species"],
        )
        FormQuestion.objects.create(
            form=self.form,
            name="region",
            label="Region",
            type="select_one",
        )
        FormQuestion.objects.create(
            form=self.form,
            name="woreda",
            label="Woreda",
            type="select_one",
        )
        q_species = FormQuestion.objects.create(
            form=self.form,
            name="species",
            label="Species",
            type="select_one",
        )
        q_variety = FormQuestion.objects.create(
            form=self.form,
            name="variety",
            label="Variety",
            type="select_one",
        )
        FormQuestion.objects.create(
            form=self.form,
            name="notes",
            label="Notes",
            type="text",
        )
        FormOption.objects.create(
            question=q_species,
            name="eucalyptus",
            label="Eucalyptus",
        )
        FormOption.objects.create(
            question=q_species,
            name="bamboo",
            label="Bamboo",
        )
        FormOption.objects.create(
            question=q_variety,
            name="lowland",
            label="Lowland",
        )
        FormOption.objects.create(
            question=q_variety,
            name="highland",
            label="Highland",
        )

    def test_all_eligible_returns_extra_fields(self):
        """all_eligible=true returns select fields
        not in filter_fields."""
        res = self.client.get(
            URL,
            {"form_id": "formAE", "all_eligible": "true"},
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        names = [f["name"] for f in data["available_filters"]]
        self.assertIn("variety", names)
        self.assertIn("species", names)
        self.assertNotIn("notes", names)
        self.assertNotIn("region", names)
        self.assertNotIn("woreda", names)

    def test_all_eligible_false_no_available(self):
        """Without all_eligible, no available_filters
        key is returned."""
        res = self.client.get(
            URL,
            {"form_id": "formAE"},
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertNotIn("available_filters", data)

    def test_dynamic_filter_options_sorted_alpha(self):
        """Options within dynamic_filters are sorted
        alphabetically by label."""
        res = self.client.get(
            URL,
            {"form_id": "formAE"},
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        species = next(
            f for f in res.json()["dynamic_filters"] if f["name"] == "species"
        )
        labels = [o["label"] for o in species["options"]]
        self.assertEqual(labels, ["Bamboo", "Eucalyptus"])

    def test_available_filters_sorted_alpha(self):
        """available_filters are sorted
        alphabetically by label."""
        res = self.client.get(
            URL,
            {
                "form_id": "formAE",
                "all_eligible": "true",
            },
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        labels = [f["label"] for f in res.json()["available_filters"]]
        self.assertEqual(labels, sorted(labels))
