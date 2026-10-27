import datetime
import json
import os
import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from openpyxl import Workbook

SPECIES_HEADER = ["Yushania ", "Milletia ", "Hegenia", "Mulberry", "Total"]
SURVIVAL_HEADER = ["farmer_name", "farmer_id", "date_monitoring"] + [
    f"total_{kind}_{suffix}"
    for suffix in ("ya", "mf", "ha", "mam", "all")
    for kind in ("planted", "survived")
]


def visit(name, farmer_id, day, planted, survived):
    """One survival visit; the four species split the totals evenly."""
    row = [name, farmer_id, datetime.datetime(2026, 6, day)]
    for _ in range(4):
        row += [planted / 4, survived / 4]
    return row + [str(planted), str(survived)]


class BuildPlantingKpisCommandTest(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def _save(self, name, sheets):
        wb = Workbook()
        wb.remove(wb.active)
        for title, rows in sheets.items():
            ws = wb.create_sheet(title)
            for row in rows:
                ws.append(row)
        wb.save(os.path.join(self.dir, name))

    def _er_model(self, name, total):
        rows = [[None] * 19 for _ in range(4)]
        rows[0][11] = "Vintage period"
        rows[1][11] = "1-Aug-2024 to 31-Dec-2024"
        rows[2][11] = "1-Jan-2025 to 31-Jul-2064"
        rows[3][11], rows[3][18] = "Total ", total
        self._save(name, {"Net GHG Benefit": rows})

    def _fixtures(self):
        # No plot size column: area from the _20ha in the name. The
        # Total column is ignored, blank rows are padding.
        self._save(
            "AB_Planting_2024_20ha.xlsx",
            {
                "Seedling distrbution-Hula": [
                    ["First Name"] + SPECIES_HEADER,
                    ["Girja", 10, 1, 1, 10, 999],
                    [None, None, None, None, None, None],
                ],
                "Seedling distrbution-Bursa": [
                    ["First Name"] + SPECIES_HEADER,
                    ["Rodu", 10, 1, 1, 10, None],
                ],
                "Survival checklist-Hula": [["ignored"], ["x"]],
            },
        )
        self._save(
            "AB_Planting_2025_100ha.xlsx",
            {
                "Seedling distrbution-Hula": [
                    ["First Name", "Plot size"] + SPECIES_HEADER,
                    ["Majora", 0.2, 40, 38, 38, 106, None],
                    ["Kia", 0.4, 40, 38, 38, 106, None],
                ],
            },
        )
        # Older survival file and ER model are superseded.
        self._save(
            "AB_Survival_Monitoring_2025.xlsx",
            {
                "Seedling Survival Monitoring": [
                    SURVIVAL_HEADER,
                    visit("Old", "AB00009", 1, 100, 1),
                ]
            },
        )
        self._save(
            "AB_Survival_Monitoring_2026.xlsx",
            {
                "Seedling Survival Monitoring": [
                    SURVIVAL_HEADER,
                    visit("Test ", "Test", 9, 100, 0),
                    # Same farmer three ways; the latest visit counts.
                    visit("Abebe", "AB 00351", 1, 100, 10),
                    visit("Abebe", "ABOO351", 20, 100, 90),
                    visit("Abebe", "00351", 5, 100, 50),
                    # A sixth digit is cut; of a same-day pair the
                    # first visit counts.
                    visit("Kia", "AB003521", 3, 100, 80),
                    visit("Kia", "AB00352", 3, 100, 0),
                ]
            },
        )
        self._er_model("AB_ER_Model_2025.xlsx", 1)
        self._er_model("AB_ER_Model_2026.xlsx", 14404611.44)

    def _run(self):
        out = StringIO()
        call_command("build_planting_kpis", self.dir, stdout=out)
        return json.loads(out.getvalue())

    def test_builds_figures_from_the_file_set(self):
        self._fixtures()
        data = self._run()
        self.assertEqual(data["planting_years"], [2024, 2025])
        self.assertEqual(data["plots"], 4)
        self.assertEqual(data["hectares"], 20.6)
        self.assertEqual(
            [(s["name"], s["seedlings"]) for s in data["species"]],
            [
                ("Yushania alpina (highland bamboo)", 100),
                ("Millettia ferruginea", 78),
                ("Hagenia abyssinica", 78),
                ("Morus alba (mulberry)", 232),
            ],
        )
        self.assertEqual(data["monitored_plots"], 2)
        self.assertEqual(data["survival_rate"], 85.0)
        self.assertEqual(data["species"][0]["survival_rate"], 85.0)
        self.assertEqual(data["monitoring_up_to"], "2026-06-20")
        self.assertEqual(
            data["carbon"],
            {
                "tco2e": 14404611,
                "period_start": "2024-08-01",
                "period_end": "2064-07-31",
            },
        )

    def test_rejects_a_list_without_plot_size_or_area(self):
        self._fixtures()
        os.rename(
            os.path.join(self.dir, "AB_Planting_2024_20ha.xlsx"),
            os.path.join(self.dir, "AB_Planting_2024.xlsx"),
        )
        with self.assertRaisesMessage(CommandError, "no plot size"):
            self._run()

    def test_rejects_an_empty_folder(self):
        with self.assertRaisesMessage(CommandError, "AB_Planting"):
            self._run()
