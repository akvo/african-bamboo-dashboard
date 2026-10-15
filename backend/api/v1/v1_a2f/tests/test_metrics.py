import copy
import os

from django.core.management import call_command
from django.test import TestCase

from api.v1.v1_a2f.metrics import compute_metrics, filter_options
from api.v1.v1_a2f.models import A2FSnapshot

FIXTURE = "api/v1/v1_a2f/tests/fixtures/a2f_dummy.xlsx"


class MetricsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_a2f", FIXTURE, stdout=open(os.devnull, "w"))

    def setUp(self):
        self.snap = A2FSnapshot.objects.get()

    def test_unfiltered_matches_mockup(self):
        """Every number on the issue #60 mockup, from the dummy data."""
        m = compute_metrics(self.snap, {})
        r, v = m["reach"], m["volume"]
        t, q, k = m["loan_terms"], m["portfolio_quality"], m["linked"]
        self.assertEqual(m["data_as_of"], "2026-09-30")
        self.assertEqual((r["borrowers"], r["members"]), (29, 36))
        self.assertAlmostEqual(r["borrowing_rate"], 0.806, 3)
        self.assertAlmostEqual(r["women_share"], 0.241, 3)
        self.assertAlmostEqual(r["youth_share"], 0.448, 3)
        self.assertEqual((r["coops_with_active_loans"], r["coops"]), (5, 6))
        self.assertEqual((v["disbursed"], v["loans"]), (995500, 34))
        self.assertEqual(v["outstanding"], 492475)
        self.assertEqual(round(v["average_loan"]), 29279)
        self.assertEqual(v["median_loan"], 23250)
        self.assertAlmostEqual(v["hectares"], 13.85)
        self.assertEqual(round(v["value_per_ha"]), 71877)
        self.assertAlmostEqual(v["outstanding_share"], 0.495, 3)
        self.assertAlmostEqual(t["average_interest_rate"], 0.1299, 4)
        self.assertEqual(
            t["collateral"],
            [
                {"type": "Group guarantee", "loans": 9, "amount": 252500},
                {"type": "Bamboo stock", "loans": 9, "amount": 343500},
                {"type": "Equipment", "loans": 8, "amount": 171500},
                {"type": "Land certificate", "loans": 8, "amount": 228000},
            ],
        )
        self.assertAlmostEqual(q["par30"], 0.143, 3)
        self.assertEqual(q["written_off"], 56420)
        self.assertAlmostEqual(q["written_off_share"], 0.057, 3)
        self.assertEqual(round(q["credit_score"]), 689)
        self.assertEqual(q["credit_score_borrowers"], 24)
        self.assertEqual(k["borrowing_with_title"]["n"], 15)
        self.assertAlmostEqual(k["borrowing_with_title"]["value"], 0.867, 3)
        self.assertEqual(k["borrowing_without_title"]["n"], 21)
        self.assertAlmostEqual(
            k["borrowing_without_title"]["value"], 0.762, 3
        )
        self.assertEqual(k["par30_trained"]["n"], 21)
        self.assertAlmostEqual(k["par30_trained"]["value"], 0.107, 3)
        self.assertEqual(k["par30_untrained"]["n"], 5)
        self.assertAlmostEqual(k["par30_untrained"]["value"], 0.309, 3)
        self.assertEqual(k["income_change_borrowers"]["n"], 29)
        self.assertEqual(
            round(k["income_change_borrowers"]["value"]), 3145
        )
        self.assertEqual(k["income_change_non_borrowers"]["n"], 7)
        self.assertEqual(
            round(k["income_change_non_borrowers"]["value"]), 3429
        )
        self.assertEqual(k["jobs_created"], 28)
        self.assertAlmostEqual(k["jobs_per_million"], 28.1, 1)

    def test_member_filter_narrows_members_and_loans(self):
        m = compute_metrics(self.snap, {"region": "Oromia"})
        self.assertEqual(m["reach"]["members"], 6)
        self.assertEqual(m["reach"]["coops"], 2)
        self.assertEqual(m["volume"]["loans"], 1)

    def test_loan_type_keeps_member_denominator(self):
        m = compute_metrics(self.snap, {"loan_type": "Group loan"})
        self.assertEqual(m["reach"]["members"], 36)
        self.assertEqual(m["volume"]["loans"], 8)
        self.assertEqual(m["reach"]["borrowers"], 8)

    def test_youth_filter_uses_data_as_of(self):
        youth = compute_metrics(self.snap, {"youth": "yes"})
        older = compute_metrics(self.snap, {"youth": "no"})
        self.assertEqual(
            youth["reach"]["members"] + older["reach"]["members"], 36
        )
        self.assertEqual(youth["reach"]["youth_share"], 1)

    def test_small_groups_are_suppressed(self):
        m = compute_metrics(self.snap, {"coop": "CO001"})
        group = m["linked"]["par30_untrained"]
        self.assertLess(group["n"], 5)
        self.assertIsNone(group["value"])

    def test_empty_selection_returns_nulls(self):
        m = compute_metrics(self.snap, {"coop": "CO006"})
        self.assertEqual(m["volume"]["loans"], 0)
        self.assertIsNone(m["volume"]["average_loan"])
        self.assertIsNone(m["volume"]["median_loan"])
        self.assertIsNone(m["portfolio_quality"]["par30"])
        self.assertIsNone(m["portfolio_quality"]["credit_score"])
        self.assertIsNone(m["linked"]["jobs_per_million"])

    def test_blank_optional_cells_are_skipped(self):
        snap = copy.deepcopy(self.snap)
        snap.loans[0]["interest_rate"] = None
        snap.members[0]["bamboo_area_ha"] = None
        snap.members[0]["date_of_birth"] = None
        m = compute_metrics(snap, {})
        self.assertAlmostEqual(m["volume"]["hectares"], 13.65)
        self.assertIsNotNone(m["loan_terms"]["average_interest_rate"])
        self.assertEqual(m["reach"]["borrowers"], 29)

    def test_filter_options_cover_whole_snapshot(self):
        o = filter_options(self.snap)
        self.assertEqual(o["regions"], ["Oromia", "Sidama"])
        self.assertEqual(o["woredas"]["Sidama"], ["Bursa", "Hula"])
        self.assertEqual(len(o["cooperatives"]), 6)
        self.assertEqual(
            o["cooperatives"][0],
            {"value": "CO001", "label": "Hula Bamboo Growers Cooperative"},
        )
        self.assertEqual(o["genders"], ["F", "M"])
        self.assertEqual(o["target_groups"], ["SHF", "YW"])
        self.assertEqual(len(o["loan_types"]), 4)
