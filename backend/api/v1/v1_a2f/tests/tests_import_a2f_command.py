import os
import shutil
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from openpyxl import load_workbook

from api.v1.v1_a2f.models import A2FSnapshot

FIXTURE = "api/v1/v1_a2f/tests/fixtures/a2f_dummy.xlsx"


class ImportA2FCommandTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _variant(self, edit, name="variant.xlsx"):
        """Save a copy of the fixture after ``edit(workbook)``."""
        wb = load_workbook(FIXTURE)
        edit(wb)
        path = os.path.join(self.tmp, name)
        wb.save(path)
        return path

    def _import(self, path=FIXTURE):
        call_command("import_a2f", path, stdout=open(os.devnull, "w"))

    def test_imports_every_sheet(self):
        self._import()
        snap = A2FSnapshot.objects.get()
        self.assertEqual(str(snap.data_as_of), "2026-09-30")
        self.assertEqual(len(snap.cooperatives), 6)
        self.assertEqual(len(snap.members), 36)
        self.assertEqual(len(snap.loans), 34)
        self.assertEqual(len(snap.parcels), 42)
        self.assertEqual(snap.parameters["etb_per_eur"], "184.25")

    def test_file_name_does_not_matter(self):
        path = os.path.join(self.tmp, "snapshot")
        shutil.copy(FIXTURE, path)
        self._import(path)
        self.assertEqual(A2FSnapshot.objects.count(), 1)

    def test_reimport_replaces_snapshot(self):
        self._import()
        path = self._variant(
            lambda wb: wb["loans"].delete_rows(3, 33)
        )
        self._import(path)
        snap = A2FSnapshot.objects.get()
        self.assertEqual(len(snap.loans), 1)

    def _assert_rejected(self, path, message):
        self._import()
        with self.assertRaisesMessage(CommandError, message):
            self._import(path)
        snap = A2FSnapshot.objects.get()
        self.assertEqual(len(snap.loans), 34)

    def test_wrong_header_keeps_previous_snapshot(self):
        def rename(wb):
            wb["loans"]["E1"] = "amount"

        self._assert_rejected(self._variant(rename), "Sheet 'loans'")

    def test_missing_sheet_keeps_previous_snapshot(self):
        def drop(wb):
            del wb["parcels"]

        self._assert_rejected(
            self._variant(drop), "Missing sheet 'parcels'"
        )

    def test_bad_date_names_sheet_row_and_column(self):
        def corrupt(wb):
            wb["loans"]["N3"] = "not a date"

        self._assert_rejected(
            self._variant(corrupt),
            "Sheet 'loans' row 3 column 'disbursement_date'",
        )

    def test_missing_data_as_of_is_rejected(self):
        def clear(wb):
            wb["parameters"]["B2"] = None

        self._assert_rejected(self._variant(clear), "data_as_of")

    def test_unreadable_file_is_rejected(self):
        path = os.path.join(self.tmp, "junk.xlsx")
        with open(path, "w") as f:
            f.write("not a workbook")
        self._assert_rejected(path, "Cannot open")
