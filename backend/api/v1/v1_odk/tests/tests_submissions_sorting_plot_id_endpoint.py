from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    FormMetadata,
    MainPlot,
    MainPlotSubmission,
    Plot,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)


VALID_WKT = (
    "POLYGON(("
    "38.7 9.0, 38.701 9.0, "
    "38.701 9.001, 38.7 9.001, "
    "38.7 9.0))"
)

BASE_URL = "/api/v1/odk/submissions/"


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionSortingByPlotIdTest(
    TestCase, OdkTestHelperMixin
):
    """Test sorting submissions by main_plot_uid."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formSortPlotId",
            name="Form Sort Plot ID",
        )
        # Create 3 submissions with different UIDs
        self.subs = []
        for i, (uid, kobo, plot_uid) in enumerate(
            [
                ("s-aaa", "101", "PLT00003"),
                ("s-bbb", "102", "PLT00001"),
                ("s-ccc", "103", None),
            ]
        ):
            sub = Submission.objects.create(
                uuid=uid,
                form=self.form,
                kobo_id=kobo,
                submission_time=(
                    1700000000000 + i * 1000
                ),
                submitted_by="tester",
                instance_name=f"Instance {uid}",
                raw_data={"q1": "a1"},
            )
            Plot.objects.create(
                submission=sub,
                form=self.form,
                plot_name=f"Plot {uid}",
                polygon_wkt=VALID_WKT,
                min_lat=9.0,
                max_lat=9.001,
                min_lon=38.7,
                max_lon=38.701,
                created_at=1700000000000,
            )
            if plot_uid:
                mp = MainPlot.objects.create(
                    form=self.form,
                    uid=plot_uid,
                )
                MainPlotSubmission.objects.create(
                    main_plot=mp,
                    submission=sub,
                )
            self.subs.append(sub)

    def _list_url(self, ordering=None):
        url = (
            f"{BASE_URL}"
            f"?asset_uid={self.form.asset_uid}"
        )
        if ordering:
            url += f"&ordering={ordering}"
        return url

    def _get_uids(self, ordering):
        resp = self.client.get(
            self._list_url(ordering),
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        return [
            r["main_plot_uid"]
            for r in resp.json()["results"]
        ]

    @patch("api.v1.v1_odk.views.async_task")
    def test_sort_ascending(self, _mock):
        """Ascending: PLT00001, PLT00003, None."""
        uids = self._get_uids("main_plot_uid")
        self.assertEqual(
            uids,
            ["PLT00001", "PLT00003", None],
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_sort_descending(self, _mock):
        """Descending: PLT00003, PLT00001,
        None (nulls last)."""
        uids = self._get_uids("-main_plot_uid")
        self.assertEqual(
            uids,
            ["PLT00003", "PLT00001", None],
        )

    @patch("api.v1.v1_odk.views.async_task")
    def test_no_ordering_default(self, _mock):
        """Without ordering param, uses default
        submission_time order."""
        resp = self.client.get(
            self._list_url(),
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 3)
