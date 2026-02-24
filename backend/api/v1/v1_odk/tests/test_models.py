from django.db import IntegrityError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (ApprovalStatus, FormMetadata, FormOption,
                                  FormQuestion, Plot, Submission)


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
            reviewer_notes="Boundary unclear",
        )
        self.assertEqual(
            sub.approval_status,
            ApprovalStatus.REJECTED,
        )
        self.assertEqual(
            sub.get_approval_status_display(),
            "Not approved",
        )
        self.assertEqual(sub.reviewer_notes, "Boundary unclear")

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
            instance_name="inst-1",
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
            instance_name="inst-2",
            form=self.form,
            region="Region A",
            sub_region="Sub A",
            created_at=1700000000000,
        )
        self.assertIsNone(plot.polygon_wkt)
        self.assertIsNone(plot.min_lat)

    def test_plot_str(self):
        plot = Plot(plot_name="Farmer B")
        self.assertEqual(str(plot), "Farmer B")

    def test_submission_set_null_on_delete(self):
        plot = Plot.objects.create(
            plot_name="Farmer C",
            instance_name="inst-3",
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

    def test_one_to_one_constraint(self):
        Plot.objects.create(
            uuid="plot-1",
            plot_name="Farmer D",
            instance_name="inst-4",
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
                instance_name="inst-5",
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
        self.assertFalse(FormOption.objects.filter(name="ET04").exists())
