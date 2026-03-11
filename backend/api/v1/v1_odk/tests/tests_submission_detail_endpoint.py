from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    FieldMapping,
    FieldSettings,
    FormMetadata,
    FormOption,
    FormQuestion,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionDetailFieldMappedDataTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for field_mapped_data in
    SubmissionDetailSerializer."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formDetail",
            name="Detail Form",
        )
        self.q_text = FormQuestion.objects.create(
            form=self.form,
            name="farmer_name",
            label="Farmer Name",
            type="text",
        )
        self.q_select = FormQuestion.objects.create(
            form=self.form,
            name="region_code",
            label="Region",
            type="select_one",
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
        self.fs_farmer = (
            FieldSettings.objects.create(
                name="farmer"
            )
        )
        self.fs_region = (
            FieldSettings.objects.create(
                name="region"
            )
        )
        self.sub = Submission.objects.create(
            uuid="detail-001",
            form=self.form,
            kobo_id="100",
            submission_time=1700000000000,
            raw_data={
                "farmer_name": "John",
                "region_code": "R1",
            },
        )

    def test_field_mapped_data_returns_resolved(
        self,
    ):
        """field_mapped_data returns mapped fields
        with correct resolved values and labels."""
        FieldMapping.objects.create(
            field=self.fs_farmer,
            form=self.form,
            form_question=self.q_text,
        )
        FieldMapping.objects.create(
            field=self.fs_region,
            form=self.form,
            form_question=self.q_select,
        )
        resp = self.client.get(
            "/api/v1/odk/submissions/detail-001/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        fmd = resp.json()["field_mapped_data"]
        self.assertIn("farmer", fmd)
        self.assertEqual(
            fmd["farmer"]["value"], "John"
        )
        self.assertEqual(
            fmd["farmer"]["label"], "Farmer Name"
        )

    def test_field_mapped_data_resolves_select(
        self,
    ):
        """field_mapped_data resolves select_one
        options to labels."""
        FieldMapping.objects.create(
            field=self.fs_region,
            form=self.form,
            form_question=self.q_select,
        )
        resp = self.client.get(
            "/api/v1/odk/submissions/detail-001/",
            **self.auth,
        )
        fmd = resp.json()["field_mapped_data"]
        self.assertEqual(
            fmd["region"]["value"], "Region One"
        )
        self.assertEqual(
            fmd["region"]["raw_value"], "R1"
        )

    def test_field_mapped_data_empty_no_mapping(
        self,
    ):
        """field_mapped_data returns empty dict when
        no FieldMapping exists."""
        resp = self.client.get(
            "/api/v1/odk/submissions/detail-001/",
            **self.auth,
        )
        fmd = resp.json()["field_mapped_data"]
        self.assertEqual(fmd, {})


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionDetailAreaHaTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for area_ha in detail endpoint."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formArea",
            name="Area Form",
        )
        self.sub = Submission.objects.create(
            uuid="area-001",
            form=self.form,
            kobo_id="200",
            submission_time=1700000000000,
            raw_data={"q1": "a1"},
        )

    def test_area_ha_from_plot(self):
        """area_ha is read from Plot.area_ha."""
        Plot.objects.create(
            plot_name="Plot A",
            form=self.form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=self.sub,
            area_ha=12.5,
        )
        resp = self.client.get(
            "/api/v1/odk/submissions/area-001/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["area_ha"], 12.5
        )

    def test_area_ha_none_without_plot(self):
        """area_ha is None when no plot exists."""
        resp = self.client.get(
            "/api/v1/odk/submissions/area-001/",
            **self.auth,
        )
        self.assertIsNone(resp.json()["area_ha"])


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionDetailAttachmentsTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for attachments in detail endpoint."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formAtt",
            name="Attach Form",
        )
        FormQuestion.objects.create(
            form=self.form,
            name="Title_Deed_First_Page",
            label="Title Deed (First Page)",
            type="image",
        )

    def test_attachments_list_fields(self):
        """attachments list contains local_url,
        question_xpath, media_file_basename,
        question_label."""
        sub = Submission.objects.create(
            uuid="att-001",
            form=self.form,
            kobo_id="300",
            submission_time=1700000000000,
            raw_data={
                "_attachments": [
                    {
                        "uid": "abc",
                        "question_xpath": (
                            "Title_Deed_First_Page"
                        ),
                        "media_file_basename": (
                            "1234.jpg"
                        ),
                    }
                ],
            },
        )
        resp = self.client.get(
            f"/api/v1/odk/submissions/{sub.uuid}/",
            **self.auth,
        )
        atts = resp.json()["attachments"]
        self.assertEqual(len(atts), 1)
        att = atts[0]
        self.assertIn("local_url", att)
        self.assertEqual(
            att["question_xpath"],
            "Title_Deed_First_Page",
        )
        self.assertEqual(
            att["media_file_basename"], "1234.jpg"
        )
        self.assertIn("question_label", att)

    def test_attachments_resolves_label(self):
        """attachments resolves question_xpath to
        FormQuestion.label for question_label."""
        sub = Submission.objects.create(
            uuid="att-002",
            form=self.form,
            kobo_id="301",
            submission_time=1700000000000,
            raw_data={
                "_attachments": [
                    {
                        "uid": "def",
                        "question_xpath": (
                            "Title_Deed_First_Page"
                        ),
                        "media_file_basename": (
                            "5678.jpg"
                        ),
                    }
                ],
            },
        )
        resp = self.client.get(
            f"/api/v1/odk/submissions/{sub.uuid}/",
            **self.auth,
        )
        att = resp.json()["attachments"][0]
        self.assertEqual(
            att["question_label"],
            "Title Deed (First Page)",
        )

    def test_attachments_empty_no_raw_attachments(
        self,
    ):
        """attachments returns empty list when no
        _attachments in raw_data."""
        sub = Submission.objects.create(
            uuid="att-003",
            form=self.form,
            kobo_id="302",
            submission_time=1700000000000,
            raw_data={"q1": "a1"},
        )
        resp = self.client.get(
            f"/api/v1/odk/submissions/{sub.uuid}/",
            **self.auth,
        )
        self.assertEqual(
            resp.json()["attachments"], []
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionDetailRejectionReasonTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for rejection_reason in detail."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formRej",
            name="Rejection Form",
        )
        self.sub = Submission.objects.create(
            uuid="rej-001",
            form=self.form,
            kobo_id="400",
            submission_time=1700000000000,
            raw_data={"q1": "a1"},
        )
        self.plot = Plot.objects.create(
            plot_name="Rej Plot",
            form=self.form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=self.sub,
        )

    def test_rejection_reason_from_latest_audit(
        self,
    ):
        """rejection_reason returns reason_text from
        latest RejectionAudit."""
        RejectionAudit.objects.create(
            plot=self.plot,
            submission=self.sub,
            validator=self.user,
            reason_category="polygon_error",
            reason_text="Old reason",
        )
        RejectionAudit.objects.create(
            plot=self.plot,
            submission=self.sub,
            validator=self.user,
            reason_category="overlap",
            reason_text="Latest reason",
        )
        resp = self.client.get(
            "/api/v1/odk/submissions/rej-001/",
            **self.auth,
        )
        self.assertEqual(
            resp.json()["rejection_reason"],
            "Latest reason",
        )

    def test_rejection_reason_none_no_audits(self):
        """rejection_reason is None when no audits
        exist."""
        resp = self.client.get(
            "/api/v1/odk/submissions/rej-001/",
            **self.auth,
        )
        self.assertIsNone(
            resp.json()["rejection_reason"]
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionDetailUpdatedByNameTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for updated_by_name in detail."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formUpd",
            name="Update Form",
        )
        self.sub = Submission.objects.create(
            uuid="upd-001",
            form=self.form,
            kobo_id="500",
            submission_time=1700000000000,
            raw_data={"q1": "a1"},
        )

    def test_updated_by_name_after_update(self):
        """updated_by_name returns validator name
        after update."""
        self.sub.updated_by = self.user
        self.sub.save()
        resp = self.client.get(
            "/api/v1/odk/submissions/upd-001/",
            **self.auth,
        )
        self.assertEqual(
            resp.json()["updated_by_name"],
            self.user.name,
        )

    def test_updated_by_name_none_never_reviewed(
        self,
    ):
        """updated_by_name is None for
        never-reviewed submissions."""
        resp = self.client.get(
            "/api/v1/odk/submissions/upd-001/",
            **self.auth,
        )
        self.assertIsNone(
            resp.json()["updated_by_name"]
        )
