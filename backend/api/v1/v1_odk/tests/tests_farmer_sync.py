from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    Farmer,
    FarmerFieldMapping,
    FormMetadata,
    FormOption,
    FormQuestion,
    Plot,
    Submission,
)
from api.v1.v1_odk.serializers import (
    build_option_lookup,
)
from api.v1.v1_odk.utils.farmer_sync import (
    build_farmer_lookup_key,
    generate_next_farmer_uid,
    resolve_field_value,
    sync_farmers_for_form,
)


def _create_form_with_questions():
    """Create a form with questions and options
    for testing."""
    form = FormMetadata.objects.create(
        asset_uid="test_form",
        name="Test Form",
    )

    FormQuestion.objects.create(
        form=form,
        name="First_Name",
        label="First Name",
        type="text",
    )
    FormQuestion.objects.create(
        form=form,
        name="Father_s_Name",
        label="Father Name",
        type="text",
    )
    FormQuestion.objects.create(
        form=form,
        name="Grandfather_s_Name",
        label="Grandfather Name",
        type="text",
    )
    FormQuestion.objects.create(
        form=form,
        name="age_of_farmer",
        label="Age",
        type="integer",
    )
    FormQuestion.objects.create(
        form=form,
        name="phone_q",
        label="Phone Number",
        type="text",
    )
    q_enum = FormQuestion.objects.create(
        form=form,
        name="enumerator_id",
        label="Enumerator",
        type="select_one",
    )
    FormOption.objects.create(
        question=q_enum,
        name="enum_001",
        label="John Doe",
    )

    return form


def _create_submission(form, kobo_id, raw_data):
    """Create a submission with a linked plot."""
    sub = Submission.objects.create(
        uuid=f"uuid-{kobo_id}",
        form=form,
        kobo_id=kobo_id,
        submission_time=1700000000000,
        raw_data=raw_data,
    )
    plot = Plot.objects.create(
        form=form,
        submission=sub,
        region="Region1",
        sub_region="SubRegion1",
        created_at=1700000000000,
    )
    return sub, plot


@override_settings(USE_TZ=False, TEST_ENV=True)
class ResolveFieldValueTest(TestCase):
    def setUp(self):
        self.form = _create_form_with_questions()
        self.option_map, self.type_map = (
            build_option_lookup(self.form)
        )

    def test_resolve_text_field(self):
        raw = {"First_Name": "Dara"}
        val = resolve_field_value(
            raw,
            "First_Name",
            self.option_map,
            self.type_map,
        )
        self.assertEqual(val, "Dara")

    def test_resolve_select_field(self):
        """select_one resolves to label."""
        raw = {"enumerator_id": "enum_001"}
        val = resolve_field_value(
            raw,
            "enumerator_id",
            self.option_map,
            self.type_map,
        )
        self.assertEqual(val, "John Doe")

    def test_resolve_missing_field(self):
        raw = {"First_Name": "Dara"}
        val = resolve_field_value(
            raw,
            "nonexistent",
            self.option_map,
            self.type_map,
        )
        self.assertIsNone(val)

    def test_resolve_empty_value(self):
        raw = {"First_Name": ""}
        val = resolve_field_value(
            raw,
            "First_Name",
            self.option_map,
            self.type_map,
        )
        self.assertIsNone(val)


@override_settings(USE_TZ=False, TEST_ENV=True)
class BuildLookupKeyTest(TestCase):
    def setUp(self):
        self.form = _create_form_with_questions()
        self.option_map, self.type_map = (
            build_option_lookup(self.form)
        )
        self.unique_fields = [
            "First_Name",
            "Father_s_Name",
            "Grandfather_s_Name",
        ]

    def test_build_lookup_key(self):
        raw = {
            "First_Name": "Dara",
            "Father_s_Name": "Hora",
            "Grandfather_s_Name": "Daye",
        }
        key = build_farmer_lookup_key(
            raw,
            self.unique_fields,
            self.option_map,
            self.type_map,
        )
        self.assertEqual(key, "Dara - Hora - Daye")

    def test_skips_empty_fields(self):
        raw = {
            "First_Name": "Dara",
            "Father_s_Name": "",
            "Grandfather_s_Name": "Daye",
        }
        key = build_farmer_lookup_key(
            raw,
            self.unique_fields,
            self.option_map,
            self.type_map,
        )
        self.assertEqual(key, "Dara - Daye")

    def test_all_empty_returns_none(self):
        raw = {}
        key = build_farmer_lookup_key(
            raw,
            self.unique_fields,
            self.option_map,
            self.type_map,
        )
        self.assertIsNone(key)


@override_settings(USE_TZ=False, TEST_ENV=True)
class GenerateUidTest(TestCase):
    def test_first_farmer(self):
        uid = generate_next_farmer_uid()
        self.assertEqual(uid, "00001")

    def test_sequential(self):
        Farmer.objects.create(
            uid="00005",
            lookup_key="test-key-5",
        )
        uid = generate_next_farmer_uid()
        self.assertEqual(uid, "00006")

    def test_beyond_five_digits(self):
        Farmer.objects.create(
            uid="99999",
            lookup_key="test-key-99999",
        )
        uid = generate_next_farmer_uid()
        self.assertEqual(uid, "100000")


@override_settings(USE_TZ=False, TEST_ENV=True)
class SyncFarmersTest(TestCase):
    def setUp(self):
        self.form = _create_form_with_questions()

    def test_no_mapping_configured(self):
        result = sync_farmers_for_form(self.form)
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["linked"], 0)

    def test_creates_new_farmers(self):
        FarmerFieldMapping.objects.create(
            form=self.form,
            unique_fields=(
                "First_Name,"
                "Father_s_Name,"
                "Grandfather_s_Name"
            ),
            values_fields=(
                "First_Name,"
                "Father_s_Name,"
                "Grandfather_s_Name,"
                "age_of_farmer,phone_q"
            ),
        )
        _create_submission(
            self.form,
            "k001",
            {
                "First_Name": "Dara",
                "Father_s_Name": "Hora",
                "Grandfather_s_Name": "Daye",
                "age_of_farmer": "38",
                "phone_q": "0712345678",
            },
        )

        result = sync_farmers_for_form(self.form)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["linked"], 1)

        farmer = Farmer.objects.first()
        self.assertEqual(farmer.uid, "00001")
        self.assertEqual(
            farmer.lookup_key,
            "Dara - Hora - Daye",
        )
        self.assertEqual(
            farmer.values["First_Name"], "Dara"
        )
        self.assertEqual(
            farmer.values["age_of_farmer"], "38"
        )

    def test_updates_existing_farmer_values(self):
        FarmerFieldMapping.objects.create(
            form=self.form,
            unique_fields=(
                "First_Name,"
                "Father_s_Name,"
                "Grandfather_s_Name"
            ),
            values_fields=(
                "First_Name,"
                "Father_s_Name,"
                "Grandfather_s_Name,"
                "age_of_farmer,phone_q"
            ),
        )
        _create_submission(
            self.form,
            "k001",
            {
                "First_Name": "Dara",
                "Father_s_Name": "Hora",
                "Grandfather_s_Name": "Daye",
                "age_of_farmer": "38",
                "phone_q": "0712345678",
            },
        )

        # First sync
        sync_farmers_for_form(self.form)

        # Update submission raw_data
        sub = Submission.objects.get(kobo_id="k001")
        sub.raw_data["age_of_farmer"] = "39"
        sub.save()

        # Second sync
        result = sync_farmers_for_form(self.form)
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 1)

        farmer = Farmer.objects.first()
        self.assertEqual(farmer.uid, "00001")
        self.assertEqual(
            farmer.values["age_of_farmer"], "39"
        )

    def test_links_plot_to_farmer(self):
        FarmerFieldMapping.objects.create(
            form=self.form,
            unique_fields=(
                "First_Name,"
                "Father_s_Name,"
                "Grandfather_s_Name"
            ),
            values_fields="First_Name",
        )
        _, plot = _create_submission(
            self.form,
            "k001",
            {
                "First_Name": "Dara",
                "Father_s_Name": "Hora",
                "Grandfather_s_Name": "Daye",
            },
        )
        self.assertIsNone(plot.farmer)

        sync_farmers_for_form(self.form)

        plot.refresh_from_db()
        self.assertIsNotNone(plot.farmer)
        self.assertEqual(
            plot.farmer.lookup_key,
            "Dara - Hora - Daye",
        )

    def test_multiple_plots_same_farmer(self):
        FarmerFieldMapping.objects.create(
            form=self.form,
            unique_fields=(
                "First_Name,"
                "Father_s_Name,"
                "Grandfather_s_Name"
            ),
            values_fields="First_Name",
        )
        raw = {
            "First_Name": "Dara",
            "Father_s_Name": "Hora",
            "Grandfather_s_Name": "Daye",
        }
        _, plot1 = _create_submission(
            self.form, "k001", raw
        )
        _, plot2 = _create_submission(
            self.form, "k002", raw
        )

        sync_farmers_for_form(self.form)

        self.assertEqual(Farmer.objects.count(), 1)

        plot1.refresh_from_db()
        plot2.refresh_from_db()
        self.assertEqual(
            plot1.farmer_id, plot2.farmer_id
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class SyncFarmersCommandTest(TestCase):
    def setUp(self):
        self.form = _create_form_with_questions()
        FarmerFieldMapping.objects.create(
            form=self.form,
            unique_fields=(
                "First_Name,"
                "Father_s_Name,"
                "Grandfather_s_Name"
            ),
            values_fields="First_Name",
        )
        _create_submission(
            self.form,
            "k001",
            {
                "First_Name": "Dara",
                "Father_s_Name": "Hora",
                "Grandfather_s_Name": "Daye",
            },
        )

    def test_management_command(self):
        out = StringIO()
        call_command("sync_farmers", stdout=out)
        output = out.getvalue()
        self.assertIn("created=1", output)
        self.assertEqual(Farmer.objects.count(), 1)

    def test_command_specific_form(self):
        out = StringIO()
        call_command(
            "sync_farmers",
            "--form",
            "test_form",
            stdout=out,
        )
        output = out.getvalue()
        self.assertIn("created=1", output)

    def test_command_unknown_form(self):
        err = StringIO()
        call_command(
            "sync_farmers",
            "--form",
            "nonexistent",
            stderr=err,
        )
        self.assertIn(
            "not found", err.getvalue()
        )
