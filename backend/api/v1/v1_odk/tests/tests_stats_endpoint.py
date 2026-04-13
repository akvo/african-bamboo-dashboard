from django.test import TestCase

from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
)
from api.v1.v1_odk.models import (
    FormMetadata,
    Plot,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)


class StatsEndpointTestCase(
    OdkTestHelperMixin, TestCase
):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="stats_form_001",
            name="Stats Test Form",
        )
        # 3 approved, 2 pending (NULL)
        for i in range(5):
            sub = Submission.objects.create(
                uuid=f"stats-sub-{i}",
                form=self.form,
                kobo_id=str(i),
                submission_time=(
                    1700000000000 + i
                ),
                raw_data={},
                approval_status=(
                    ApprovalStatusTypes.APPROVED
                    if i < 3
                    else None
                ),
            )
            Plot.objects.create(
                uuid=f"stats-plot-{i}",
                form=self.form,
                submission=sub,
                area_ha=10.0 + i,
                region="Region A",
                created_at=1700000000000 + i,
            )

    def test_stats_totals(self):
        url = "/api/v1/odk/plots/stats/"
        res = self.client.get(
            url,
            {"form_id": "stats_form_001"},
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(
            data["total_plots"], 5
        )
        # 10+11+12+13+14 = 60
        self.assertAlmostEqual(
            data["total_area_ha"], 60.0
        )
        # 3 approved / 5 total = 60%
        self.assertAlmostEqual(
            data["approval_percentage"], 60.0
        )
        self.assertEqual(
            data["pending_count"], 2
        )
        # pending: 13 + 14 = 27
        self.assertAlmostEqual(
            data["pending_area_ha"], 27.0
        )
        # approved: 10 + 11 + 12 = 33
        self.assertAlmostEqual(
            data["approved_area_ha"], 33.0
        )

    def test_stats_with_region_filter(self):
        url = "/api/v1/odk/plots/stats/"
        res = self.client.get(
            url,
            {
                "form_id": "stats_form_001",
                "region": "No Match",
            },
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(
            data["total_plots"], 0
        )
        self.assertEqual(
            data["total_area_ha"], 0
        )
        self.assertEqual(
            data["approval_percentage"], 0
        )
        self.assertEqual(
            data["approved_area_ha"], 0
        )

    def test_stats_requires_auth(self):
        url = "/api/v1/odk/plots/stats/"
        res = self.client.get(
            url,
            {"form_id": "stats_form_001"},
        )
        self.assertEqual(res.status_code, 401)
