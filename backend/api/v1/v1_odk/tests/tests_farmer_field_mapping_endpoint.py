from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    FarmerFieldMapping,
    FormMetadata,
    FormQuestion,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)


def _setup_form():
    form = FormMetadata.objects.create(
        asset_uid="ffm-form",
        name="FFM Test Form",
    )
    FormQuestion.objects.create(
        form=form,
        name="First_Name",
        label="First Name",
        type="text",
    )
    FormQuestion.objects.create(
        form=form,
        name="Age",
        label="Age",
        type="integer",
    )
    return form


def _url(asset_uid):
    return (
        f"/api/v1/odk/forms/{asset_uid}"
        f"/farmer-field-mapping/"
    )


@override_settings(
    USE_TZ=False, TEST_ENV=True
)
class FarmerFieldMappingEndpointTest(
    TestCase, OdkTestHelperMixin
):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = _setup_form()
        self.url = _url(self.form.asset_uid)

    def test_get_empty_mapping(self):
        resp = self.client.get(
            self.url, **self.auth
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data["unique_fields"], []
        )
        self.assertEqual(
            resp.data["values_fields"], []
        )

    def test_put_creates_mapping(self):
        resp = self.client.put(
            self.url,
            {
                "unique_fields": ["First_Name"],
                "values_fields": [
                    "First_Name",
                    "Age",
                ],
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data["unique_fields"],
            ["First_Name"],
        )
        self.assertEqual(
            resp.data["values_fields"],
            ["First_Name", "Age"],
        )
        # Verify DB
        m = FarmerFieldMapping.objects.get(
            form=self.form
        )
        self.assertEqual(
            m.unique_fields, "First_Name"
        )
        self.assertEqual(
            m.values_fields, "First_Name,Age"
        )

    def test_put_updates_existing(self):
        FarmerFieldMapping.objects.create(
            form=self.form,
            unique_fields="First_Name",
            values_fields="First_Name",
        )
        resp = self.client.put(
            self.url,
            {
                "unique_fields": ["First_Name"],
                "values_fields": ["Age"],
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data["values_fields"], ["Age"]
        )
        # Should still be one mapping
        self.assertEqual(
            FarmerFieldMapping.objects.filter(
                form=self.form
            ).count(),
            1,
        )

    def test_put_requires_unique_fields(self):
        resp = self.client.put(
            self.url,
            {
                "unique_fields": [],
                "values_fields": ["Age"],
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)

    def test_put_defaults_values_to_unique(
        self,
    ):
        """When values_fields is empty, it should
        default to unique_fields."""
        resp = self.client.put(
            self.url,
            {
                "unique_fields": ["First_Name"],
                "values_fields": [],
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        m = FarmerFieldMapping.objects.get(
            form=self.form
        )
        self.assertEqual(
            m.values_fields, "First_Name"
        )

    def test_get_after_put(self):
        self.client.put(
            self.url,
            {
                "unique_fields": [
                    "First_Name",
                ],
                "values_fields": [
                    "First_Name",
                    "Age",
                ],
            },
            content_type="application/json",
            **self.auth,
        )
        resp = self.client.get(
            self.url, **self.auth
        )
        self.assertEqual(
            resp.data["unique_fields"],
            ["First_Name"],
        )
        self.assertEqual(
            resp.data["values_fields"],
            ["First_Name", "Age"],
        )

    def test_requires_auth(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 401)
