from django.db import IntegrityError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    ApprovalStatus,
    FieldMapping,
    FieldSettings,
    FormMetadata,
    FormOption,
    FormQuestion,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormMetadataModelTest(TestCase):
    def test_create_form_metadata(self):
        form = FormMetadata.objects.create(
            asset_uid="aXyz123",
            name="Test Form",
        )
        self.assertEqual(form.asset_uid, "aXyz123")
        self.assertEqual(form.name, "Test Form")
        self.assertEqual(form.last_sync_timestamp, 0)

    def test_form_str(self):
        form = FormMetadata(asset_uid="abc")
        self.assertEqual(str(form), "Form abc")


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionModelTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="form1",
            name="Test Form",
        )

    def test_create_submission(self):
        sub = Submission.objects.create(
            uuid="uuid-001",
            form=self.form,
            kobo_id="12345",
            submission_time=1700000000000,
            submitted_by="tester",
            instance_name="Test Instance",
            raw_data={"field": "value"},
        )
        self.assertEqual(sub.uuid, "uuid-001")
        self.assertEqual(sub.form, self.form)
        self.assertIsNone(sub.system_data)
        self.assertIsNone(sub.approval_status)

    def test_approval_status_choices(self):
        sub = Submission.objects.create(
            uuid="uuid-appr",
            form=self.form,
            kobo_id="99",
            submission_time=1700000000000,
            raw_data={},
            approval_status=(ApprovalStatus.APPROVED),
        )
        self.assertEqual(
            sub.approval_status,
            ApprovalStatus.APPROVED,
        )
        self.assertEqual(
            sub.get_approval_status_display(),
            "Approved",
        )

    def test_rejection_status(self):
        sub = Submission.objects.create(
            uuid="uuid-rej",
            form=self.form,
            kobo_id="98",
            submission_time=1700000000000,
            raw_data={},
            approval_status=(ApprovalStatus.REJECTED),
        )
        self.assertEqual(
            sub.approval_status,
            ApprovalStatus.REJECTED,
        )
        self.assertEqual(
            sub.get_approval_status_display(),
            "Not approved",
        )

    def test_submission_str_with_instance_name(
        self,
    ):
        sub = Submission(
            uuid="u1",
            instance_name="My Instance",
        )
        self.assertEqual(str(sub), "My Instance")

    def test_submission_str_without_instance_name(
        self,
    ):
        sub = Submission(uuid="u1")
        self.assertEqual(str(sub), "u1")

    def test_cascade_delete(self):
        Submission.objects.create(
            uuid="uuid-del",
            form=self.form,
            kobo_id="99",
            submission_time=1700000000000,
            raw_data={},
        )
        self.form.delete()
        self.assertFalse(Submission.objects.filter(uuid="uuid-del").exists())

    def test_ordering(self):
        Submission.objects.create(
            uuid="u-old",
            form=self.form,
            kobo_id="1",
            submission_time=1000,
            raw_data={},
        )
        Submission.objects.create(
            uuid="u-new",
            form=self.form,
            kobo_id="2",
            submission_time=2000,
            raw_data={},
        )
        subs = list(Submission.objects.values_list("uuid", flat=True))
        self.assertEqual(subs, ["u-new", "u-old"])


@override_settings(USE_TZ=False, TEST_ENV=True)
class PlotModelTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="form1",
            name="Test Form",
        )
        self.submission = Submission.objects.create(
            uuid="sub-001",
            form=self.form,
            kobo_id="100",
            submission_time=1700000000000,
            raw_data={"q": "a"},
        )

    def test_create_plot(self):
        plot = Plot.objects.create(
            plot_name="Farmer A",
            polygon_wkt=("POLYGON((0 0,1 0,1 1,0 0))"),
            min_lat=0.0,
            max_lat=1.0,
            min_lon=0.0,
            max_lon=1.0,
            form=self.form,
            region="Region A",
            sub_region="Sub A",
            created_at=1700000000000,
            submission=self.submission,
        )
        self.assertEqual(plot.plot_name, "Farmer A")

    def test_create_plot_null_geometry(self):
        plot = Plot.objects.create(
            plot_name="Farmer B",
            form=self.form,
            region="Region A",
            sub_region="Sub A",
            created_at=1700000000000,
        )
        self.assertIsNone(plot.polygon_wkt)
        self.assertIsNone(plot.min_lat)

    def test_plot_str_with_name(self):
        plot = Plot(plot_name="Farmer B")
        self.assertEqual(str(plot), "Farmer B")

    def test_plot_str_without_name(self):
        plot = Plot(uuid="test-uuid")
        self.assertEqual(str(plot), "test-uuid")

    def test_submission_set_null_on_delete(self):
        plot = Plot.objects.create(
            plot_name="Farmer C",
            polygon_wkt=("POLYGON((0 0,1 0,1 1,0 0))"),
            min_lat=0.0,
            max_lat=1.0,
            min_lon=0.0,
            max_lon=1.0,
            form=self.form,
            region="R",
            sub_region="SR",
            created_at=1700000000000,
            submission=self.submission,
        )
        self.submission.delete()
        plot.refresh_from_db()
        self.assertIsNone(plot.submission)

    def test_default_flag_values(self):
        plot = Plot.objects.create(
            plot_name="Farmer Flag",
            form=self.form,
            region="R",
            sub_region="SR",
            created_at=1700000000000,
        )
        self.assertIsNone(plot.flagged_for_review)
        self.assertIsNone(plot.flagged_reason)

    def test_explicitly_flagged_plot(self):
        plot = Plot.objects.create(
            plot_name="Farmer Flagged",
            form=self.form,
            region="R",
            sub_region="SR",
            created_at=1700000000000,
            flagged_for_review=True,
            flagged_reason=(
                "No polygon data found "
                "in submission."
            ),
        )
        self.assertTrue(plot.flagged_for_review)
        self.assertEqual(
            plot.flagged_reason,
            "No polygon data found in submission.",
        )

    def test_one_to_one_constraint(self):
        Plot.objects.create(
            uuid="plot-1",
            plot_name="Farmer D",
            polygon_wkt=("POLYGON((0 0,1 0,1 1,0 0))"),
            min_lat=0.0,
            max_lat=1.0,
            min_lon=0.0,
            max_lon=1.0,
            form=self.form,
            region="R",
            sub_region="SR",
            created_at=1700000000000,
            submission=self.submission,
        )
        with self.assertRaises(IntegrityError):
            Plot.objects.create(
                uuid="plot-2",
                plot_name="Farmer E",
                polygon_wkt=("POLYGON((0 0,1 0,1 1,0 0))"),
                min_lat=0.0,
                max_lat=1.0,
                min_lon=0.0,
                max_lon=1.0,
                form=self.form,
                region="R",
                sub_region="SR",
                created_at=1700000000000,
                submission=self.submission,
            )


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormQuestionModelTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="form1",
            name="Test Form",
        )

    def test_create_question(self):
        q = FormQuestion.objects.create(
            form=self.form,
            name="region",
            label="Region",
            type="select_one",
        )
        self.assertEqual(q.name, "region")
        self.assertEqual(q.label, "Region")
        self.assertEqual(q.type, "select_one")

    def test_str(self):
        q = FormQuestion(
            form=self.form,
            name="region",
            label="Region",
            type="select_one",
        )
        self.assertEqual(str(q), "form1 - region")

    def test_unique_together(self):
        FormQuestion.objects.create(
            form=self.form,
            name="region",
            label="Region",
            type="select_one",
        )
        with self.assertRaises(IntegrityError):
            FormQuestion.objects.create(
                form=self.form,
                name="region",
                label="Other",
                type="text",
            )

    def test_cascade_delete(self):
        FormQuestion.objects.create(
            form=self.form,
            name="region",
            label="Region",
            type="select_one",
        )
        self.form.delete()
        self.assertFalse(FormQuestion.objects.filter(name="region").exists())


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormOptionModelTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="form1",
            name="Test Form",
        )
        self.question = FormQuestion.objects.create(
            form=self.form,
            name="region",
            label="Region",
            type="select_one",
        )

    def test_create_option(self):
        opt = FormOption.objects.create(
            question=self.question,
            name="ET04",
            label="Oromia",
        )
        self.assertEqual(opt.name, "ET04")
        self.assertEqual(opt.label, "Oromia")

    def test_str(self):
        opt = FormOption(
            question=self.question,
            name="ET04",
            label="Oromia",
        )
        self.assertEqual(str(opt), "form1 - region - ET04")

    def test_cascade_delete_question(self):
        FormOption.objects.create(
            question=self.question,
            name="ET04",
            label="Oromia",
        )
        self.question.delete()
        self.assertFalse(FormOption.objects.filter(name="ET04").exists())

    def test_cascade_delete_form(self):
        FormOption.objects.create(
            question=self.question,
            name="ET04",
            label="Oromia",
        )
        self.form.delete()
        self.assertFalse(
            FormOption.objects.filter(
                name="ET04"
            ).exists()
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class RejectionAuditModelTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="form1",
            name="Test Form",
        )
        self.submission = Submission.objects.create(
            uuid="sub-audit-001",
            form=self.form,
            kobo_id="100",
            submission_time=1700000000000,
            raw_data={"q": "a"},
        )
        self.plot = Plot.objects.create(
            plot_name="Farmer Audit",
            form=self.form,
            region="R",
            sub_region="SR",
            created_at=1700000000000,
            submission=self.submission,
        )
        self.validator = (
            SystemUser.objects.create_superuser(
                email="validator@test.local",
                password="Changeme123",
                name="validator",
            )
        )

    def test_rejection_audit_creation(self):
        audit = RejectionAudit.objects.create(
            plot=self.plot,
            submission=self.submission,
            validator=self.validator,
            reason_category="polygon_error",
            reason_text="Bad polygon",
        )
        self.assertEqual(
            audit.reason_category,
            "polygon_error",
        )
        self.assertEqual(
            audit.reason_text, "Bad polygon"
        )
        self.assertEqual(
            audit.sync_status, "pending"
        )

    def test_rejection_audit_str(self):
        audit = RejectionAudit.objects.create(
            plot=self.plot,
            submission=self.submission,
            validator=self.validator,
            reason_category="other",
        )
        expected = (
            f"Rejection #{audit.pk} "
            f"for {self.submission}"
        )
        self.assertEqual(str(audit), expected)

    def test_rejection_audit_cascade_delete(
        self,
    ):
        RejectionAudit.objects.create(
            plot=self.plot,
            submission=self.submission,
            validator=self.validator,
            reason_category="duplicate",
        )
        self.plot.delete()
        self.assertFalse(
            RejectionAudit.objects.filter(
                submission=self.submission
            ).exists()
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class FieldSettingsModelTest(TestCase):
    def test_create_field_settings(self):
        fs = FieldSettings.objects.create(
            name="title_deed_number",
        )
        self.assertEqual(fs.name, "title_deed_number")

    def test_name_uniqueness(self):
        FieldSettings.objects.create(
            name="title_deed_number",
        )
        with self.assertRaises(IntegrityError):
            FieldSettings.objects.create(
                name="title_deed_number",
            )


@override_settings(USE_TZ=False, TEST_ENV=True)
class FieldMappingModelTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="fm1",
            name="Test Form",
        )
        self.question = FormQuestion.objects.create(
            form=self.form,
            name="deed_no",
            label="Deed Number",
            type="text",
        )
        self.field = FieldSettings.objects.create(
            name="title_deed_number",
        )

    def test_create_field_mapping(self):
        mapping = FieldMapping.objects.create(
            field=self.field,
            form=self.form,
            form_question=self.question,
        )
        self.assertEqual(mapping.field, self.field)
        self.assertEqual(mapping.form, self.form)
        self.assertEqual(
            mapping.form_question, self.question
        )

    def test_unique_together_field_form(self):
        FieldMapping.objects.create(
            field=self.field,
            form=self.form,
            form_question=self.question,
        )
        q2 = FormQuestion.objects.create(
            form=self.form,
            name="deed_no_2",
            label="Deed Number 2",
            type="text",
        )
        with self.assertRaises(IntegrityError):
            FieldMapping.objects.create(
                field=self.field,
                form=self.form,
                form_question=q2,
            )

    def test_cascade_delete_field_settings(self):
        FieldMapping.objects.create(
            field=self.field,
            form=self.form,
            form_question=self.question,
        )
        self.field.delete()
        self.assertFalse(
            FieldMapping.objects.filter(
                form=self.form
            ).exists()
        )

    def test_cascade_delete_form_metadata(self):
        FieldMapping.objects.create(
            field=self.field,
            form=self.form,
            form_question=self.question,
        )
        self.form.delete()
        self.assertFalse(
            FieldMapping.objects.filter(
                field=self.field
            ).exists()
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionUniqueFormKoboIdTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="form-uniq",
            name="Test Form",
        )

    def test_duplicate_kobo_id_same_form_raises(
        self,
    ):
        Submission.objects.create(
            uuid="uuid-dup-1",
            form=self.form,
            kobo_id="555",
            submission_time=1700000000000,
            raw_data={},
        )
        with self.assertRaises(IntegrityError):
            Submission.objects.create(
                uuid="uuid-dup-2",
                form=self.form,
                kobo_id="555",
                submission_time=1700000000000,
                raw_data={},
            )

    def test_same_kobo_id_different_form_allowed(
        self,
    ):
        form2 = FormMetadata.objects.create(
            asset_uid="form-uniq-2",
            name="Test Form 2",
        )
        Submission.objects.create(
            uuid="uuid-cross-1",
            form=self.form,
            kobo_id="777",
            submission_time=1700000000000,
            raw_data={},
        )
        sub2 = Submission.objects.create(
            uuid="uuid-cross-2",
            form=form2,
            kobo_id="777",
            submission_time=1700000000000,
            raw_data={},
        )
        self.assertEqual(sub2.kobo_id, "777")

    def test_update_or_create_deduplicates(self):
        Submission.objects.create(
            uuid="uuid-orig",
            form=self.form,
            kobo_id="888",
            submission_time=1700000000000,
            raw_data={"old": True},
        )
        sub, is_new = (
            Submission.objects.update_or_create(
                form=self.form,
                kobo_id="888",
                defaults={
                    "uuid": "uuid-new",
                    "submission_time": (
                        1700000001000
                    ),
                    "raw_data": {"new": True},
                },
            )
        )
        self.assertFalse(is_new)
        self.assertEqual(sub.uuid, "uuid-new")
        self.assertEqual(
            sub.raw_data, {"new": True}
        )
        self.assertEqual(
            Submission.objects.filter(
                form=self.form, kobo_id="888"
            ).count(),
            1,
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionUpdatedFieldsTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="form-upd",
            name="Test Form",
        )

    def test_updated_by_defaults_to_none(self):
        sub = Submission.objects.create(
            uuid="uuid-upd-001",
            form=self.form,
            kobo_id="200",
            submission_time=1700000000000,
            raw_data={"q": "a"},
        )
        self.assertIsNone(sub.updated_by)

    def test_updated_at_defaults_to_none(self):
        sub = Submission.objects.create(
            uuid="uuid-upd-002",
            form=self.form,
            kobo_id="201",
            submission_time=1700000000000,
            raw_data={"q": "a"},
        )
        self.assertIsNone(sub.updated_at)


@override_settings(USE_TZ=False, TEST_ENV=True)
class PlotAreaHaDefaultTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="form-area",
            name="Test Form",
        )

    def test_area_ha_defaults_to_none(self):
        plot = Plot.objects.create(
            plot_name="Farmer Area",
            form=self.form,
            region="R",
            sub_region="SR",
            created_at=1700000000000,
        )
        self.assertIsNone(plot.area_ha)
