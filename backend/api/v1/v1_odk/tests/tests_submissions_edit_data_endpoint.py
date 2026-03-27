from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    FarmerFieldMapping,
    FieldMapping,
    FieldSettings,
    FormMetadata,
    FormOption,
    FormQuestion,
    Plot,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionEditDataTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for PATCH
    /v1/odk/submissions/{uuid}/edit_data/"""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="editForm",
            name="Edit Form",
            region_field="region_code",
            sub_region_field="sub_region_code",
            plot_name_field="farmer_name",
        )
        self.q_text = FormQuestion.objects.create(
            form=self.form,
            name="farmer_name",
            label="Farmer Name",
            type="text",
        )
        self.q_select = (
            FormQuestion.objects.create(
                form=self.form,
                name="region_code",
                label="Region",
                type="select_one",
            )
        )
        FormOption.objects.create(
            question=self.q_select,
            name="R1",
            label="Region One",
        )
        FormOption.objects.create(
            question=self.q_select,
            name="R2",
            label="Region Two",
        )
        self.q_sub_region = (
            FormQuestion.objects.create(
                form=self.form,
                name="sub_region_code",
                label="Sub Region",
                type="text",
            )
        )
        self.sub = Submission.objects.create(
            uuid="edit-001",
            form=self.form,
            kobo_id="100",
            submission_time=1700000000000,
            raw_data={
                "farmer_name": "John",
                "region_code": "R1",
                "sub_region_code": "Woreda A",
            },
        )
        self.plot = Plot.objects.create(
            uuid="plot-edit-001",
            form=self.form,
            submission=self.sub,
            region="Region One",
            sub_region="Woreda A",
            plot_name="John",
            created_at=1700000000000,
        )
        self.url = (
            "/api/v1/odk/submissions/"
            "edit-001/edit_data/"
        )

    def test_edit_text_field(self):
        """PATCH with text field updates
        raw_data."""
        resp = self.client.patch(
            self.url,
            {"fields": {"farmer_name": "Abebe"}},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(
            self.sub.raw_data["farmer_name"],
            "Abebe",
        )

    def test_edit_select_one_valid(self):
        """PATCH with valid option name updates
        raw_data."""
        resp = self.client.patch(
            self.url,
            {"fields": {"region_code": "R2"}},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(
            self.sub.raw_data["region_code"],
            "R2",
        )

    def test_edit_select_one_invalid(self):
        """PATCH with invalid option name returns
        400."""
        resp = self.client.patch(
            self.url,
            {"fields": {"region_code": "INVALID"}},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)

    def test_edit_unknown_field(self):
        """PATCH with non-existent question name
        returns 400."""
        resp = self.client.patch(
            self.url,
            {"fields": {"nonexistent": "val"}},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 400)

    def test_edit_updates_plot_region(self):
        """Editing region field updates
        Plot.region."""
        resp = self.client.patch(
            self.url,
            {"fields": {"region_code": "R2"}},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.plot.refresh_from_db()
        self.assertEqual(
            self.plot.region, "R2"
        )

    def test_edit_updates_plot_sub_region(self):
        """Editing sub_region field updates
        Plot.sub_region."""
        resp = self.client.patch(
            self.url,
            {
                "fields": {
                    "sub_region_code": "Woreda B"
                }
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.plot.refresh_from_db()
        self.assertEqual(
            self.plot.sub_region, "Woreda B"
        )

    def test_edit_updates_plot_name(self):
        """Editing plot_name field updates
        Plot.plot_name."""
        resp = self.client.patch(
            self.url,
            {"fields": {"farmer_name": "Tadesse"}},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.plot.refresh_from_db()
        self.assertEqual(
            self.plot.plot_name, "Tadesse"
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_edit_syncs_to_kobo(
        self, mock_async
    ):
        """Editing queues async task with
        correct args."""
        resp = self.client.patch(
            self.url,
            {"fields": {"farmer_name": "Abebe"}},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        mock_async.assert_called_once()
        args = mock_async.call_args[0]
        self.assertEqual(
            args[0],
            "api.v1.v1_odk.tasks"
            ".sync_kobo_submission_data",
        )
        self.assertEqual(args[4], "editForm")
        self.assertEqual(args[5], "100")
        self.assertEqual(
            args[6], {"farmer_name": "Abebe"}
        )

    def test_edit_requires_auth(self):
        """Unauthenticated request returns 401."""
        resp = self.client.patch(
            self.url,
            {"fields": {"farmer_name": "Abebe"}},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_edit_sets_updated_by(self):
        """updated_by and updated_at are set
        after edit."""
        self.client.patch(
            self.url,
            {"fields": {"farmer_name": "Abebe"}},
            content_type="application/json",
            **self.auth,
        )
        self.sub.refresh_from_db()
        self.assertEqual(
            self.sub.updated_by, self.user
        )
        self.assertIsNotNone(self.sub.updated_at)

    def test_edit_returns_updated_detail(self):
        """Response includes updated
        resolved_data."""
        resp = self.client.patch(
            self.url,
            {"fields": {"farmer_name": "Abebe"}},
            content_type="application/json",
            **self.auth,
        )
        data = resp.json()
        self.assertIn("resolved_data", data)
        self.assertEqual(
            data["resolved_data"]["farmer_name"],
            "Abebe",
        )

    def test_edit_empty_fields_dict(self):
        """Empty fields dict is a no-op,
        returns 200."""
        resp = self.client.patch(
            self.url,
            {"fields": {}},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)

    def test_edit_blank_value(self):
        """Setting value to empty string updates
        raw_data."""
        resp = self.client.patch(
            self.url,
            {"fields": {"farmer_name": ""}},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(
            self.sub.raw_data["farmer_name"], ""
        )

    @patch(
        "api.v1.v1_odk.views"
        ".async_task"
    )
    def test_edit_resyncs_farmer(
        self, mock_async
    ):
        """Editing farmer-mapped field triggers
        targeted farmer update (not full sync).

        The farmer's lookup_key and values should
        be updated in place — no new farmer ID
        should be generated."""
        fs = FieldSettings.objects.create(
            name="farmer"
        )
        FieldMapping.objects.create(
            field=fs,
            form=self.form,
            form_question=self.q_text,
        )
        FarmerFieldMapping.objects.create(
            form=self.form,
            unique_fields="farmer_name",
            values_fields="farmer_name",
        )
        # Create initial farmer linked to plot
        from api.v1.v1_odk.models import Farmer
        farmer = Farmer.objects.create(
            uid="00001",
            lookup_key="John",
            values={"farmer_name": "John"},
        )
        self.plot.farmer = farmer
        self.plot.save(update_fields=["farmer"])

        self.client.patch(
            self.url,
            {"fields": {"farmer_name": "Abebe"}},
            content_type="application/json",
            **self.auth,
        )
        # Farmer should be updated in place,
        # NOT via async_task
        farmer_sync_calls = [
            c for c in mock_async.call_args_list
            if c[0][0] == (
                "api.v1.v1_odk.utils.farmer_sync"
                ".sync_farmers_for_form"
            )
        ]
        self.assertEqual(
            len(farmer_sync_calls), 0,
            "Should not call full "
            "sync_farmers_for_form on edit",
        )
        # Farmer UID should be preserved
        farmer.refresh_from_db()
        self.assertEqual(farmer.uid, "00001")
        self.assertEqual(
            farmer.lookup_key, "Abebe"
        )
        self.assertEqual(
            farmer.values["farmer_name"],
            "Abebe",
        )
        # Plot should still reference same farmer
        self.plot.refresh_from_db()
        self.assertEqual(
            self.plot.farmer_id, farmer.pk
        )
