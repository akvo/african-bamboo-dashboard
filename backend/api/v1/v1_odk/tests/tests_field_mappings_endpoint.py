from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    FieldMapping,
    FieldSettings,
    FormMetadata,
    FormQuestion,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class FieldMappingsListTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for GET /api/v1/odk/field-mappings/."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formMap",
            name="Mapping Form",
        )
        self.q1 = FormQuestion.objects.create(
            form=self.form,
            name="farmer_name",
            label="Farmer Name",
            type="text",
        )
        self.fs = FieldSettings.objects.create(
            name="farmer"
        )
        FieldMapping.objects.create(
            field=self.fs,
            form=self.form,
            form_question=self.q1,
        )

    def test_list_with_form_id(self):
        """GET with form_id returns mappings."""
        resp = self.client.get(
            "/api/v1/odk/field-mappings/"
            "?form_id=formMap",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(
            data[0]["field_name"], "farmer"
        )
        self.assertEqual(
            data[0]["form_question_name"],
            "farmer_name",
        )

    def test_list_no_form_id_empty(self):
        """GET with no form_id returns all
        mappings (unfiltered)."""
        resp = self.client.get(
            "/api/v1/odk/field-mappings/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)

    def test_list_no_mappings_empty(self):
        """GET returns empty list when no mappings
        exist for the form."""
        FormMetadata.objects.create(
            asset_uid="formEmpty",
            name="Empty Form",
        )
        resp = self.client.get(
            "/api/v1/odk/field-mappings/"
            "?form_id=formEmpty",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])


@override_settings(USE_TZ=False, TEST_ENV=True)
class FieldMappingsBulkUpsertTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for PUT field-mappings/{uid}/."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formUpsert",
            name="Upsert Form",
        )
        self.q1 = FormQuestion.objects.create(
            form=self.form,
            name="farmer_name",
            label="Farmer Name",
            type="text",
        )
        self.q2 = FormQuestion.objects.create(
            form=self.form,
            name="phone",
            label="Phone Number",
            type="text",
        )
        self.fs_farmer = (
            FieldSettings.objects.create(
                name="farmer"
            )
        )
        self.fs_phone = (
            FieldSettings.objects.create(
                name="phone_number"
            )
        )

    def _put(self, asset_uid, data):
        return self.client.put(
            "/api/v1/odk/field-mappings/"
            f"{asset_uid}/",
            data,
            content_type="application/json",
            **self.auth,
        )

    def test_create_new_mappings(self):
        """PUT creates new mappings."""
        resp = self._put(
            "formUpsert",
            {"farmer": self.q1.pk},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(
            data[0]["field_name"], "farmer"
        )

    def test_update_existing_mappings(self):
        """PUT updates existing mapping to new
        question."""
        FieldMapping.objects.create(
            field=self.fs_farmer,
            form=self.form,
            form_question=self.q1,
        )
        resp = self._put(
            "formUpsert",
            {"farmer": self.q2.pk},
        )
        self.assertEqual(resp.status_code, 200)
        mapping = FieldMapping.objects.get(
            field=self.fs_farmer,
            form=self.form,
        )
        self.assertEqual(
            mapping.form_question.pk, self.q2.pk
        )

    def test_delete_mapping_with_null(self):
        """PUT with null deletes the mapping."""
        FieldMapping.objects.create(
            field=self.fs_farmer,
            form=self.form,
            form_question=self.q1,
        )
        resp = self._put(
            "formUpsert",
            {"farmer": None},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            FieldMapping.objects.filter(
                field=self.fs_farmer,
                form=self.form,
            ).exists()
        )

    def test_invalid_question_id_returns_400(self):
        """PUT with invalid question_id returns
        400."""
        resp = self._put(
            "formUpsert",
            {"farmer": 99999},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn(
            "errors", resp.json()
        )

    def test_unknown_field_name_returns_400(self):
        """PUT with unknown field name returns 400."""
        resp = self._put(
            "formUpsert",
            {"nonexistent_field": self.q1.pk},
        )
        self.assertEqual(resp.status_code, 400)
        errors = resp.json()["errors"]
        self.assertIn(
            "nonexistent_field", errors
        )

    def test_unauthenticated_returns_401(self):
        """Unauthenticated request returns 401."""
        resp = self.client.put(
            "/api/v1/odk/field-mappings/"
            "formUpsert/",
            {"farmer": self.q1.pk},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)
