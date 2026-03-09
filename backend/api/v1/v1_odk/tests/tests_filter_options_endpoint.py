from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    FormMetadata,
    FormOption,
    FormQuestion,
    Plot,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)

URL = "/api/v1/odk/plots/filter_options/"


@override_settings(USE_TZ=False, TEST_ENV=True)
class FilterOptionsEndpointTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for GET /v1/odk/plots/filter_options/."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formFO",
            name="Filter Options Form",
            region_field="region",
            sub_region_field="woreda",
            filter_fields=["species"],
        )
        q_region = FormQuestion.objects.create(
            form=self.form,
            name="region",
            label="Region",
            type="select_one",
        )
        q_woreda = FormQuestion.objects.create(
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
        FormOption.objects.create(
            question=q_region,
            name="ET04",
            label="Oromia",
        )
        FormOption.objects.create(
            question=q_region,
            name="ET07",
            label="Amhara",
        )
        FormOption.objects.create(
            question=q_woreda,
            name="W01",
            label="Jimma",
        )
        FormOption.objects.create(
            question=q_woreda,
            name="W02",
            label="Gondar",
        )
        FormOption.objects.create(
            question=q_species,
            name="bamboo",
            label="Bamboo",
        )
        FormOption.objects.create(
            question=q_species,
            name="eucalyptus",
            label="Eucalyptus",
        )

        # Create submissions and plots
        sub1 = Submission.objects.create(
            uuid="sub-fo1",
            form=self.form,
            kobo_id="1",
            submission_time=1700000000000,
            raw_data={
                "region": "ET04",
                "woreda": "W01",
            },
        )
        Plot.objects.create(
            submission=sub1,
            form=self.form,
            region="ET04",
            sub_region="W01",
            created_at=1700000000000,
        )
        sub2 = Submission.objects.create(
            uuid="sub-fo2",
            form=self.form,
            kobo_id="2",
            submission_time=1700000000000,
            raw_data={
                "region": "ET07",
                "woreda": "W02",
            },
        )
        Plot.objects.create(
            submission=sub2,
            form=self.form,
            region="ET07",
            sub_region="W02",
            created_at=1700000000000,
        )
        # Second plot in ET04 with different woreda
        sub3 = Submission.objects.create(
            uuid="sub-fo3",
            form=self.form,
            kobo_id="3",
            submission_time=1700000000000,
            raw_data={
                "region": "ET04",
                "woreda": "W02",
            },
        )
        Plot.objects.create(
            submission=sub3,
            form=self.form,
            region="ET04",
            sub_region="W02",
            created_at=1700000000000,
        )

    def test_requires_form_id(self):
        resp = self.client.get(URL, **self.auth)
        self.assertEqual(resp.status_code, 400)

    def test_form_not_found(self):
        resp = self.client.get(
            URL, {"form_id": "nope"}, **self.auth
        )
        self.assertEqual(resp.status_code, 404)

    def test_response_shape(self):
        resp = self.client.get(
            URL, {"form_id": "formFO"}, **self.auth
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("regions", data)
        self.assertIn("sub_regions", data)
        self.assertIn("dynamic_filters", data)

    def test_regions_have_value_and_label(self):
        resp = self.client.get(
            URL, {"form_id": "formFO"}, **self.auth
        )
        regions = resp.json()["regions"]
        self.assertTrue(len(regions) >= 2)
        for r in regions:
            self.assertIn("value", r)
            self.assertIn("label", r)

    def test_region_labels_resolved(self):
        resp = self.client.get(
            URL, {"form_id": "formFO"}, **self.auth
        )
        regions = resp.json()["regions"]
        by_value = {r["value"]: r for r in regions}
        self.assertEqual(
            by_value["ET04"]["label"], "Oromia"
        )
        self.assertEqual(
            by_value["ET07"]["label"], "Amhara"
        )

    def test_sub_regions_labels_resolved(self):
        resp = self.client.get(
            URL, {"form_id": "formFO"}, **self.auth
        )
        subs = resp.json()["sub_regions"]
        by_value = {s["value"]: s for s in subs}
        self.assertEqual(
            by_value["W01"]["label"], "Jimma"
        )
        self.assertEqual(
            by_value["W02"]["label"], "Gondar"
        )

    def test_sub_regions_cascade_by_region(self):
        resp = self.client.get(
            URL,
            {"form_id": "formFO", "region": "ET07"},
            **self.auth,
        )
        subs = resp.json()["sub_regions"]
        values = {s["value"] for s in subs}
        # ET07 only has W02
        self.assertEqual(values, {"W02"})

    def test_sub_regions_cascade_multiple(self):
        """ET04 has both W01 and W02."""
        resp = self.client.get(
            URL,
            {"form_id": "formFO", "region": "ET04"},
            **self.auth,
        )
        subs = resp.json()["sub_regions"]
        values = {s["value"] for s in subs}
        self.assertEqual(values, {"W01", "W02"})

    def test_dynamic_filters_returned(self):
        resp = self.client.get(
            URL, {"form_id": "formFO"}, **self.auth
        )
        dynamic = resp.json()["dynamic_filters"]
        self.assertEqual(len(dynamic), 1)
        f = dynamic[0]
        self.assertEqual(f["name"], "species")
        self.assertEqual(f["label"], "Species")
        options = {o["name"] for o in f["options"]}
        self.assertEqual(
            options, {"bamboo", "eucalyptus"}
        )

    def test_no_dynamic_filters_when_empty(self):
        self.form.filter_fields = []
        self.form.save()
        resp = self.client.get(
            URL, {"form_id": "formFO"}, **self.auth
        )
        self.assertEqual(
            resp.json()["dynamic_filters"], []
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class DynamicFilterParamTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for filter__* query params on
    submissions and plots endpoints."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formDF",
            name="Dynamic Filter Form",
            filter_fields=["species"],
        )
        FormQuestion.objects.create(
            form=self.form,
            name="species",
            label="Species",
            type="select_one",
        )
        sub1 = Submission.objects.create(
            uuid="sub-df1",
            form=self.form,
            kobo_id="1",
            submission_time=1700000000000,
            raw_data={"species": "bamboo"},
        )
        sub2 = Submission.objects.create(
            uuid="sub-df2",
            form=self.form,
            kobo_id="2",
            submission_time=1700000000000,
            raw_data={"species": "eucalyptus"},
        )
        Plot.objects.create(
            submission=sub1,
            form=self.form,
            created_at=1700000000000,
        )
        Plot.objects.create(
            submission=sub2,
            form=self.form,
            created_at=1700000000000,
        )

    # -- Submissions endpoint --

    def test_submissions_filter_allowed_field(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/",
            {
                "asset_uid": "formDF",
                "filter__species": "bamboo",
            },
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["uuid"], "sub-df1"
        )

    def test_submissions_filter_disallowed_ignored(
        self,
    ):
        """filter__* keys not in form.filter_fields
        should be silently ignored."""
        resp = self.client.get(
            "/api/v1/odk/submissions/",
            {
                "asset_uid": "formDF",
                "filter__unknown_field": "x",
            },
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        # Both submissions still returned
        self.assertEqual(
            resp.json()["count"], 2
        )

    # -- Plots endpoint --

    def test_plots_filter_allowed_field(self):
        resp = self.client.get(
            "/api/v1/odk/plots/",
            {
                "form_id": "formDF",
                "filter__species": "eucalyptus",
            },
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)

    def test_plots_filter_disallowed_ignored(self):
        resp = self.client.get(
            "/api/v1/odk/plots/",
            {
                "form_id": "formDF",
                "filter__not_allowed": "y",
            },
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["count"], 2
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class DateFilterValidationTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for defensive date param parsing."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formDT",
            name="Date Filter Form",
        )
        sub = Submission.objects.create(
            uuid="sub-dt1",
            form=self.form,
            kobo_id="1",
            submission_time=1700000000000,
            raw_data={},
        )
        Plot.objects.create(
            submission=sub,
            form=self.form,
            created_at=1700000000000,
        )

    # -- Submissions --

    def test_submissions_invalid_start_date(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/",
            {
                "asset_uid": "formDT",
                "start_date": "abc",
            },
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)

    def test_submissions_invalid_end_date(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/",
            {
                "asset_uid": "formDT",
                "end_date": "not-a-number",
            },
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)

    def test_submissions_start_after_end(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/",
            {
                "asset_uid": "formDT",
                "start_date": "2000000000000",
                "end_date": "1000000000000",
            },
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)

    def test_submissions_valid_date_range(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/",
            {
                "asset_uid": "formDT",
                "start_date": "1699999999999",
                "end_date": "1700000000001",
            },
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    # -- Plots --

    def test_plots_invalid_start_date(self):
        resp = self.client.get(
            "/api/v1/odk/plots/",
            {
                "form_id": "formDT",
                "start_date": "xyz",
            },
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)

    def test_plots_start_after_end(self):
        resp = self.client.get(
            "/api/v1/odk/plots/",
            {
                "form_id": "formDT",
                "start_date": "9999999999999",
                "end_date": "1000000000000",
            },
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)

    def test_plots_valid_date_range(self):
        resp = self.client.get(
            "/api/v1/odk/plots/",
            {
                "form_id": "formDT",
                "start_date": "1699999999999",
                "end_date": "1700000000001",
            },
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)
