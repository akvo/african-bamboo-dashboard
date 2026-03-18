from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    Farmer,
    FarmerFieldMapping,
    FormMetadata,
    FormQuestion,
    Plot,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)

FARMERS_URL = "/api/v1/odk/farmers/"


def _setup_form(uid, name, field_names):
    """Create form with questions and farmer
    field mapping."""
    form = FormMetadata.objects.create(
        asset_uid=uid, name=name
    )
    for fn in field_names:
        FormQuestion.objects.create(
            form=form,
            name=fn,
            label=fn.replace("_", " ").title(),
            type="text",
        )
    return form


def _create_farmer_with_plot(
    form, uid, lookup_key, values
):
    """Create a farmer linked to a plot."""
    farmer = Farmer.objects.create(
        uid=uid,
        lookup_key=lookup_key,
        values=values,
    )
    sub = Submission.objects.create(
        uuid=f"sub-{uid}",
        form=form,
        kobo_id=uid,
        submission_time=1700000000000,
        raw_data={},
    )
    Plot.objects.create(
        submission=sub,
        form=form,
        plot_name=f"Plot {uid}",
        polygon_wkt=None,
        min_lat=0,
        max_lat=0,
        min_lon=0,
        max_lon=0,
        region="R",
        sub_region="SR",
        created_at=1700000000000,
        farmer=farmer,
    )
    return farmer


@override_settings(
    USE_TZ=False, TEST_ENV=True
)
class FarmerListEndpointTest(
    TestCase, OdkTestHelperMixin
):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()

        self.form1 = _setup_form(
            "form-a",
            "Form A",
            ["First_Name", "Age"],
        )
        self.form2 = _setup_form(
            "form-b",
            "Form B",
            ["Full_Name", "Phone"],
        )

        FarmerFieldMapping.objects.create(
            form=self.form1,
            unique_fields="First_Name",
            values_fields="First_Name,Age",
        )
        FarmerFieldMapping.objects.create(
            form=self.form2,
            unique_fields="Full_Name",
            values_fields="Full_Name,Phone",
        )

        self.f1 = _create_farmer_with_plot(
            self.form1,
            "00001",
            "Alice",
            {
                "First_Name": "Alice",
                "Age": "30",
            },
        )
        self.f2 = _create_farmer_with_plot(
            self.form1,
            "00002",
            "Bob",
            {
                "First_Name": "Bob",
                "Age": "25",
            },
        )
        self.f3 = _create_farmer_with_plot(
            self.form2,
            "00003",
            "Charlie",
            {
                "Full_Name": "Charlie",
                "Phone": "555",
            },
        )

    def test_requires_auth(self):
        resp = self.client.get(FARMERS_URL)
        self.assertEqual(resp.status_code, 401)

    def test_list_all_farmers(self):
        resp = self.client.get(
            FARMERS_URL, **self.auth
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 3)

    def test_filter_by_form_id(self):
        resp = self.client.get(
            f"{FARMERS_URL}?form_id=form-a",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 2)
        uids = [
            r["uid"] for r in resp.data["results"]
        ]
        self.assertIn("00001", uids)
        self.assertIn("00002", uids)
        self.assertNotIn("00003", uids)

    def test_filter_by_form_b(self):
        resp = self.client.get(
            f"{FARMERS_URL}?form_id=form-b",
            **self.auth,
        )
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(
            resp.data["results"][0]["uid"],
            "00003",
        )

    def test_search_by_name(self):
        resp = self.client.get(
            f"{FARMERS_URL}?search=alice",
            **self.auth,
        )
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(
            resp.data["results"][0]["uid"],
            "00001",
        )

    def test_farmer_id_has_prefix(self):
        resp = self.client.get(
            f"{FARMERS_URL}?form_id=form-a",
            **self.auth,
        )
        ids = [
            r["farmer_id"]
            for r in resp.data["results"]
        ]
        self.assertIn("AB00001", ids)

    def test_plot_count(self):
        resp = self.client.get(
            f"{FARMERS_URL}?form_id=form-a",
            **self.auth,
        )
        for r in resp.data["results"]:
            self.assertEqual(r["plot_count"], 1)

    def test_values_filtered_by_form_mapping(
        self,
    ):
        """Values should only contain fields
        from the form's FarmerFieldMapping,
        with labels as keys."""
        resp = self.client.get(
            f"{FARMERS_URL}?form_id=form-a",
            **self.auth,
        )
        for r in resp.data["results"]:
            keys = list(r["values"].keys())
            # Should have label keys
            self.assertIn("First Name", keys)
            self.assertIn("Age", keys)
            # Should NOT have form-b fields
            self.assertNotIn("Full_Name", keys)
            self.assertNotIn("Phone", keys)

    def test_values_filtered_by_form_b(self):
        resp = self.client.get(
            f"{FARMERS_URL}?form_id=form-b",
            **self.auth,
        )
        r = resp.data["results"][0]
        keys = list(r["values"].keys())
        self.assertIn("Full Name", keys)
        self.assertIn("Phone", keys)
        self.assertNotIn("First_Name", keys)

    def test_leaf_name_matching(self):
        """Values stored with group prefix should
        match mapping fields by leaf name."""
        form = _setup_form(
            "form-c",
            "Form C",
            [
                "group/First_Name",
                "group/Age",
            ],
        )
        FarmerFieldMapping.objects.create(
            form=form,
            unique_fields="group/First_Name",
            values_fields=(
                "group/First_Name,group/Age"
            ),
        )
        # Farmer stored with short keys
        _create_farmer_with_plot(
            form,
            "00004",
            "Dana",
            {"First_Name": "Dana", "Age": "40"},
        )
        resp = self.client.get(
            f"{FARMERS_URL}?form_id=form-c",
            **self.auth,
        )
        r = resp.data["results"][0]
        # Should resolve via leaf name matching
        self.assertEqual(
            r["values"]["Group/First Name"],
            "Dana",
        )

    def test_pagination(self):
        resp = self.client.get(
            f"{FARMERS_URL}?limit=2&offset=0",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            len(resp.data["results"]), 2
        )
        self.assertEqual(resp.data["count"], 3)

    def test_pagination_offset(self):
        resp = self.client.get(
            f"{FARMERS_URL}?limit=2&offset=2",
            **self.auth,
        )
        self.assertEqual(
            len(resp.data["results"]), 1
        )
