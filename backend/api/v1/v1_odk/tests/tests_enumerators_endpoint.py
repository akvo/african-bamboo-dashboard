from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    FormMetadata,
    FormOption,
    FormQuestion,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)

ENUMERATORS_URL = "/api/v1/odk/enumerators/"


def _setup_form_with_enumerators(
    uid, name, enumerators
):
    """Create form with enumerator_id question
    and options.

    enumerators: list of (code, label) tuples
    """
    form = FormMetadata.objects.create(
        asset_uid=uid, name=name
    )
    q = FormQuestion.objects.create(
        form=form,
        name="enumerator_id",
        label="Enumerator",
        type="select_one",
    )
    for code, label in enumerators:
        FormOption.objects.create(
            question=q, name=code, label=label
        )
    return form


def _create_submission(form, kobo_id, enum_code):
    """Create a submission with enumerator_id."""
    return Submission.objects.create(
        uuid=f"sub-{form.asset_uid}-{kobo_id}",
        form=form,
        kobo_id=kobo_id,
        submission_time=1700000000000,
        raw_data={
            "enumerator_id": enum_code,
        },
    )


@override_settings(
    USE_TZ=False, TEST_ENV=True
)
class EnumeratorListEndpointTest(
    TestCase, OdkTestHelperMixin
):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()

        self.form1 = (
            _setup_form_with_enumerators(
                "enum-form-a",
                "Form A",
                [
                    ("E001", "Alice Enum"),
                    ("E002", "Bob Enum"),
                ],
            )
        )
        self.form2 = (
            _setup_form_with_enumerators(
                "enum-form-b",
                "Form B",
                [("E003", "Charlie Enum")],
            )
        )

        # Form A: 2 subs for E001, 1 for E002
        _create_submission(
            self.form1, "101", "E001"
        )
        _create_submission(
            self.form1, "102", "E001"
        )
        _create_submission(
            self.form1, "103", "E002"
        )

        # Form B: 1 sub for E003
        _create_submission(
            self.form2, "201", "E003"
        )

    def test_requires_auth(self):
        resp = self.client.get(ENUMERATORS_URL)
        self.assertEqual(resp.status_code, 401)

    def test_list_all_enumerators(self):
        resp = self.client.get(
            ENUMERATORS_URL, **self.auth
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 3)

    def test_filter_by_form_id(self):
        resp = self.client.get(
            f"{ENUMERATORS_URL}"
            f"?form_id=enum-form-a",
            **self.auth,
        )
        self.assertEqual(resp.data["count"], 2)
        codes = [
            r["code"]
            for r in resp.data["results"]
        ]
        self.assertIn("E001", codes)
        self.assertIn("E002", codes)
        self.assertNotIn("E003", codes)

    def test_code_and_name_fields(self):
        """Response should have code (raw value)
        and name (resolved label)."""
        resp = self.client.get(
            f"{ENUMERATORS_URL}"
            f"?form_id=enum-form-a",
            **self.auth,
        )
        e001 = next(
            r
            for r in resp.data["results"]
            if r["code"] == "E001"
        )
        self.assertEqual(
            e001["name"], "Alice Enum"
        )

    def test_submission_count(self):
        resp = self.client.get(
            f"{ENUMERATORS_URL}"
            f"?form_id=enum-form-a",
            **self.auth,
        )
        e001 = next(
            r
            for r in resp.data["results"]
            if r["code"] == "E001"
        )
        self.assertEqual(
            e001["submission_count"], 2
        )
        e002 = next(
            r
            for r in resp.data["results"]
            if r["code"] == "E002"
        )
        self.assertEqual(
            e002["submission_count"], 1
        )

    def test_search_by_name(self):
        resp = self.client.get(
            f"{ENUMERATORS_URL}?search=alice",
            **self.auth,
        )
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(
            resp.data["results"][0]["code"],
            "E001",
        )

    def test_search_case_insensitive(self):
        resp = self.client.get(
            f"{ENUMERATORS_URL}?search=BOB",
            **self.auth,
        )
        self.assertEqual(resp.data["count"], 1)

    def test_pagination(self):
        resp = self.client.get(
            f"{ENUMERATORS_URL}?limit=2&offset=0",
            **self.auth,
        )
        self.assertEqual(
            len(resp.data["results"]), 2
        )
        self.assertEqual(resp.data["count"], 3)

    def test_no_enumerator_field_returns_empty(
        self,
    ):
        """Submissions without enumerator_id
        should not appear."""
        Submission.objects.create(
            uuid="sub-no-enum",
            form=self.form1,
            kobo_id="999",
            submission_time=1700000000000,
            raw_data={"other_field": "value"},
        )
        resp = self.client.get(
            f"{ENUMERATORS_URL}"
            f"?form_id=enum-form-a",
            **self.auth,
        )
        # Should still only have 2 enumerators
        self.assertEqual(resp.data["count"], 2)
