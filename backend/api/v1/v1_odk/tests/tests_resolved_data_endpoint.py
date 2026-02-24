from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (FormMetadata, FormOption, FormQuestion,
                                  Submission)
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class ResolvedDataDetailTest(TestCase, OdkTestHelperMixin):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formR",
            name="Resolved Form",
            region_field="region",
            sub_region_field="woreda",
        )
        self.sub = Submission.objects.create(
            uuid="sub-r1",
            form=self.form,
            kobo_id="100",
            submission_time=1700000000000,
            submitted_by="tester",
            instance_name="Test Instance",
            raw_data={
                "region": "ET04",
                "woreda": "W01",
                "enumerator_id": "EN01",
                "full_name": "Abebe",
                "age": 30,
                "crops": "bamboo coffee",
            },
        )
        # Create questions
        self.q_region = FormQuestion.objects.create(
            form=self.form,
            name="region",
            label="Region",
            type="select_one",
        )
        self.q_woreda = FormQuestion.objects.create(
            form=self.form,
            name="woreda",
            label="Woreda",
            type="select_one",
        )
        self.q_enum = FormQuestion.objects.create(
            form=self.form,
            name="enumerator_id",
            label="Enumerator",
            type="select_one",
        )
        self.q_crops = FormQuestion.objects.create(
            form=self.form,
            name="crops",
            label="Crops grown",
            type="select_multiple",
        )
        # Create options
        FormOption.objects.create(
            question=self.q_region,
            name="ET04",
            label="Oromia",
        )
        FormOption.objects.create(
            question=self.q_region,
            name="ET07",
            label="SNNPR",
        )
        FormOption.objects.create(
            question=self.q_woreda,
            name="W01",
            label="Jimma",
        )
        FormOption.objects.create(
            question=self.q_enum,
            name="EN01",
            label="John Doe",
        )
        FormOption.objects.create(
            question=self.q_crops,
            name="bamboo",
            label="Bamboo",
        )
        FormOption.objects.create(
            question=self.q_crops,
            name="coffee",
            label="Coffee",
        )

    def test_detail_includes_resolved_data(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/sub-r1/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("resolved_data", data)

    def test_select_one_resolved(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/sub-r1/",
            **self.auth,
        )
        resolved = resp.json()["resolved_data"]
        self.assertEqual(resolved["region"], "Oromia")
        self.assertEqual(resolved["woreda"], "Jimma")
        self.assertEqual(resolved["enumerator_id"], "John Doe")

    def test_select_multiple_resolved(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/sub-r1/",
            **self.auth,
        )
        resolved = resp.json()["resolved_data"]
        self.assertEqual(resolved["crops"], "Bamboo, Coffee")

    def test_non_select_fields_unchanged(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/sub-r1/",
            **self.auth,
        )
        resolved = resp.json()["resolved_data"]
        self.assertEqual(resolved["full_name"], "Abebe")
        self.assertEqual(resolved["age"], 30)

    def test_unknown_option_kept_raw(self):
        self.sub.raw_data["region"] = "UNKNOWN"
        self.sub.save()
        resp = self.client.get(
            "/api/v1/odk/submissions/sub-r1/",
            **self.auth,
        )
        resolved = resp.json()["resolved_data"]
        self.assertEqual(resolved["region"], "UNKNOWN")

    def test_no_questions_resolved_equals_raw(
        self,
    ):
        FormQuestion.objects.filter(form=self.form).delete()
        resp = self.client.get(
            "/api/v1/odk/submissions/sub-r1/",
            **self.auth,
        )
        data = resp.json()
        self.assertEqual(
            data["resolved_data"],
            data["raw_data"],
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class ResolvedDataListTest(TestCase, OdkTestHelperMixin):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formR2",
            name="Resolved List Form",
            region_field="region",
            sub_region_field="woreda",
        )
        self.sub = Submission.objects.create(
            uuid="sub-r2",
            form=self.form,
            kobo_id="200",
            submission_time=1700000000000,
            submitted_by="tester",
            raw_data={
                "region": "ET04",
                "woreda": "W01",
                "enumerator_id": "EN01",
            },
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
        q_enum = FormQuestion.objects.create(
            form=self.form,
            name="enumerator_id",
            label="Enumerator",
            type="select_one",
        )
        FormOption.objects.create(
            question=q_region,
            name="ET04",
            label="Oromia",
        )
        FormOption.objects.create(
            question=q_woreda,
            name="W01",
            label="Jimma",
        )
        FormOption.objects.create(
            question=q_enum,
            name="EN01",
            label="John Doe",
        )

    def test_list_region_resolved(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/" "?asset_uid=formR2",
            **self.auth,
        )
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["region"], "Oromia")

    def test_list_woreda_resolved(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/" "?asset_uid=formR2",
            **self.auth,
        )
        results = resp.json()["results"]
        self.assertEqual(results[0]["woreda"], "Jimma")

    def test_list_enumerator_resolved(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/" "?asset_uid=formR2",
            **self.auth,
        )
        results = resp.json()["results"]
        self.assertEqual(results[0]["enumerator"], "John Doe")

    def test_list_without_asset_uid_no_resolve(
        self,
    ):
        resp = self.client.get(
            "/api/v1/odk/submissions/",
            **self.auth,
        )
        results = resp.json()["results"]
        # Without asset_uid, no option_lookup
        # region falls back to raw value
        self.assertEqual(results[0]["region"], "ET04")


@override_settings(USE_TZ=False, TEST_ENV=True)
class MultiFieldResolvedTest(
    TestCase, OdkTestHelperMixin
):
    """Test multi-field region/sub_region
    resolution in list endpoint."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formMulti",
            name="Multi Field Form",
            region_field="region,region_specify",
            sub_region_field=(
                "woreda,woreda_specify,kebele"
            ),
        )
        self.sub = Submission.objects.create(
            uuid="sub-multi",
            form=self.form,
            kobo_id="300",
            submission_time=1700000000000,
            submitted_by="tester",
            raw_data={
                "region": "ET04",
                "region_specify": "Zone 1",
                "woreda": "W01",
                "woreda_specify": "",
                "kebele": "K01",
            },
        )
        q_region = FormQuestion.objects.create(
            form=self.form,
            name="region",
            label="Region",
            type="select_one",
        )
        FormQuestion.objects.create(
            form=self.form,
            name="region_specify",
            label="Region (specify)",
            type="text",
        )
        q_woreda = FormQuestion.objects.create(
            form=self.form,
            name="woreda",
            label="Woreda",
            type="select_one",
        )
        FormOption.objects.create(
            question=q_region,
            name="ET04",
            label="Oromia",
        )
        FormOption.objects.create(
            question=q_woreda,
            name="W01",
            label="Jimma",
        )

    def test_multi_region_joined_resolved(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/"
            "?asset_uid=formMulti",
            **self.auth,
        )
        results = resp.json()["results"]
        self.assertEqual(
            results[0]["region"],
            "Oromia - Zone 1",
        )

    def test_multi_sub_region_skips_empty(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/"
            "?asset_uid=formMulti",
            **self.auth,
        )
        results = resp.json()["results"]
        # woreda_specify is empty, skipped
        self.assertEqual(
            results[0]["woreda"],
            "Jimma - K01",
        )
