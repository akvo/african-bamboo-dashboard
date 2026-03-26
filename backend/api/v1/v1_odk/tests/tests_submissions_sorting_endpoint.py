from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    FormMetadata,
    Plot,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)
from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionSortingTest(
    TestCase, OdkTestHelperMixin
):
    """Tests for server-side sorting of the
    submissions list endpoint via ?ordering= param.

    Covers hardcoded orderings (kobo_id, reviewed_by,
    start, end, area_ha) and dynamic sortable_fields
    from raw_data JSON keys."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()

        self.reviewer = (
            SystemUser.objects.create_superuser(
                email="reviewer@test.local",
                password="Pass1234",
                name="Alice",
            )
        )
        self.reviewer2 = (
            SystemUser.objects.create_superuser(
                email="reviewer2@test.local",
                password="Pass1234",
                name="Bob",
            )
        )

        self.form = FormMetadata.objects.create(
            asset_uid="sortForm",
            name="Sort Form",
            sortable_fields=[
                "First_Name",
                "Father_s_Name",
            ],
        )

        # Submission A: earliest start, largest area
        self.sub_a = Submission.objects.create(
            uuid="sort-a",
            form=self.form,
            kobo_id="300",
            submission_time=1700000000000,
            raw_data={
                "start": "2025-01-10T08:00:00",
                "end": "2025-01-11T08:00:00",
                "First_Name": "Charlie",
                "Father_s_Name": "Delta",
            },
            updated_by=self.reviewer,
        )
        Plot.objects.create(
            plot_name="Plot A",
            form=self.form,
            region="R1",
            sub_region="S1",
            created_at=1700000000000,
            submission=self.sub_a,
            area_ha=5.0,
        )

        # Submission B: latest start, smallest area
        self.sub_b = Submission.objects.create(
            uuid="sort-b",
            form=self.form,
            kobo_id="100",
            submission_time=1700000001000,
            raw_data={
                "start": "2025-03-15T08:00:00",
                "end": "2025-03-16T08:00:00",
                "First_Name": "Alpha",
                "Father_s_Name": "Bravo",
            },
            updated_by=self.reviewer2,
        )
        Plot.objects.create(
            plot_name="Plot B",
            form=self.form,
            region="R1",
            sub_region="S1",
            created_at=1700000001000,
            submission=self.sub_b,
            area_ha=2.0,
        )

        # Submission C: middle start, no area, no
        # reviewer, no First_Name
        self.sub_c = Submission.objects.create(
            uuid="sort-c",
            form=self.form,
            kobo_id="200",
            submission_time=1700000002000,
            raw_data={
                "start": "2025-02-20T08:00:00",
                "end": "2025-02-21T08:00:00",
                "Father_s_Name": "Foxtrot",
            },
        )
        Plot.objects.create(
            plot_name="Plot C",
            form=self.form,
            region="R1",
            sub_region="S1",
            created_at=1700000002000,
            submission=self.sub_c,
            area_ha=None,
        )

        self.url = (
            "/api/v1/odk/submissions/"
            "?asset_uid=sortForm"
        )

    def _get_uuids(self, params=""):
        resp = self.client.get(
            f"{self.url}{params}",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        return [
            r["uuid"] for r in resp.json()["results"]
        ]

    # ── Hardcoded orderings ──

    def test_sort_by_kobo_id_asc(self):
        uuids = self._get_uuids("&ordering=kobo_id")
        self.assertEqual(
            uuids, ["sort-b", "sort-c", "sort-a"]
        )

    def test_sort_by_kobo_id_desc(self):
        uuids = self._get_uuids("&ordering=-kobo_id")
        self.assertEqual(
            uuids, ["sort-a", "sort-c", "sort-b"]
        )

    def test_sort_by_reviewed_by_asc(self):
        uuids = self._get_uuids(
            "&ordering=reviewed_by"
        )
        # Alice < Bob, null last
        self.assertEqual(
            uuids, ["sort-a", "sort-b", "sort-c"]
        )

    def test_sort_by_reviewed_by_desc(self):
        uuids = self._get_uuids(
            "&ordering=-reviewed_by"
        )
        # Bob > Alice, null last
        self.assertEqual(
            uuids, ["sort-b", "sort-a", "sort-c"]
        )

    def test_sort_by_start_asc(self):
        uuids = self._get_uuids("&ordering=start")
        self.assertEqual(
            uuids, ["sort-a", "sort-c", "sort-b"]
        )

    def test_sort_by_start_desc(self):
        uuids = self._get_uuids("&ordering=-start")
        self.assertEqual(
            uuids, ["sort-b", "sort-c", "sort-a"]
        )

    def test_sort_by_end_asc(self):
        uuids = self._get_uuids("&ordering=end")
        self.assertEqual(
            uuids, ["sort-a", "sort-c", "sort-b"]
        )

    def test_sort_by_end_desc(self):
        uuids = self._get_uuids("&ordering=-end")
        self.assertEqual(
            uuids, ["sort-b", "sort-c", "sort-a"]
        )

    def test_sort_by_area_ha_asc(self):
        uuids = self._get_uuids("&ordering=area_ha")
        # 2.0 < 5.0, null last
        self.assertEqual(
            uuids, ["sort-b", "sort-a", "sort-c"]
        )

    def test_sort_by_area_ha_desc(self):
        uuids = self._get_uuids(
            "&ordering=-area_ha"
        )
        # 5.0 > 2.0, null last
        self.assertEqual(
            uuids, ["sort-a", "sort-b", "sort-c"]
        )

    # ── Default ordering ──

    def test_default_ordering_without_param(self):
        """Without ?ordering=, submissions are ordered
        by -submission_time (newest first)."""
        uuids = self._get_uuids("")
        self.assertEqual(
            uuids, ["sort-c", "sort-b", "sort-a"]
        )

    # ── Invalid ordering ──

    def test_invalid_ordering_ignored(self):
        """An invalid ordering value falls back to
        default ordering."""
        uuids = self._get_uuids(
            "&ordering=nonexistent"
        )
        self.assertEqual(
            uuids, ["sort-c", "sort-b", "sort-a"]
        )

    # ── Dynamic sortable_fields ──

    def test_sort_by_dynamic_field_asc(self):
        """Sort by a raw_data field configured in
        sortable_fields."""
        uuids = self._get_uuids(
            "&ordering=First_Name"
        )
        # Alpha < Charlie, null last
        self.assertEqual(
            uuids, ["sort-b", "sort-a", "sort-c"]
        )

    def test_sort_by_dynamic_field_desc(self):
        uuids = self._get_uuids(
            "&ordering=-First_Name"
        )
        # Charlie > Alpha, null last
        self.assertEqual(
            uuids, ["sort-a", "sort-b", "sort-c"]
        )

    def test_sort_by_second_dynamic_field(self):
        """Sort by another configured sortable_field
        (Father_s_Name)."""
        uuids = self._get_uuids(
            "&ordering=Father_s_Name"
        )
        # Bravo < Delta < Foxtrot
        self.assertEqual(
            uuids, ["sort-b", "sort-a", "sort-c"]
        )

    def test_dynamic_field_not_in_allowlist(self):
        """A raw_data field NOT in sortable_fields
        is ignored, falls back to default ordering."""
        uuids = self._get_uuids(
            "&ordering=Grandfather_s_Name"
        )
        # Default: -submission_time
        self.assertEqual(
            uuids, ["sort-c", "sort-b", "sort-a"]
        )

    # ── Sorting with pagination ──

    def test_sort_with_pagination(self):
        """Sorting respects limit/offset."""
        resp = self.client.get(
            f"{self.url}&ordering=kobo_id"
            "&limit=2&offset=0",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        uuids = [r["uuid"] for r in data["results"]]
        self.assertEqual(uuids, ["sort-b", "sort-c"])
        self.assertEqual(data["count"], 3)

        # Page 2
        resp = self.client.get(
            f"{self.url}&ordering=kobo_id"
            "&limit=2&offset=2",
            **self.auth,
        )
        uuids = [
            r["uuid"]
            for r in resp.json()["results"]
        ]
        self.assertEqual(uuids, ["sort-a"])

    # ── Sorting with filters ──

    def test_sort_combined_with_status_filter(self):
        """Sorting works when combined with status
        filter."""
        self.sub_a.approval_status = 1
        self.sub_a.save()
        self.sub_b.approval_status = 1
        self.sub_b.save()

        uuids = self._get_uuids(
            "&status=approved&ordering=kobo_id"
        )
        self.assertEqual(uuids, ["sort-b", "sort-a"])

    # ── sortable_fields in list response ──

    def test_list_response_includes_sortable_fields(
        self,
    ):
        resp = self.client.get(
            self.url,
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("sortable_fields", data)
        self.assertEqual(
            data["sortable_fields"],
            ["First_Name", "Father_s_Name"],
        )

    def test_list_response_sortable_fields_empty(
        self,
    ):
        """Forms without sortable_fields return
        empty list."""
        FormMetadata.objects.create(
            asset_uid="noSort",
            name="No Sort",
        )
        resp = self.client.get(
            "/api/v1/odk/submissions/"
            "?asset_uid=noSort",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["sortable_fields"], []
        )

    def test_list_response_no_asset_uid(self):
        """Without asset_uid, sortable_fields is
        empty."""
        resp = self.client.get(
            "/api/v1/odk/submissions/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["sortable_fields"], []
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionSortingNullHandlingTest(
    TestCase, OdkTestHelperMixin
):
    """Verify null values sort last regardless of
    sort direction."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()

        self.form = FormMetadata.objects.create(
            asset_uid="nullSort",
            name="Null Sort Form",
            sortable_fields=["score"],
        )

        # Sub with start date
        self.sub_with = Submission.objects.create(
            uuid="null-a",
            form=self.form,
            kobo_id="10",
            submission_time=1700000000000,
            raw_data={
                "start": "2025-01-01T00:00:00",
                "score": "85",
            },
        )
        Plot.objects.create(
            plot_name="P1",
            form=self.form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=self.sub_with,
            area_ha=3.0,
        )

        # Sub without start date
        self.sub_without = Submission.objects.create(
            uuid="null-b",
            form=self.form,
            kobo_id="20",
            submission_time=1700000001000,
            raw_data={},
        )
        Plot.objects.create(
            plot_name="P2",
            form=self.form,
            region="R",
            sub_region="S",
            created_at=1700000001000,
            submission=self.sub_without,
            area_ha=None,
        )

        self.url = (
            "/api/v1/odk/submissions/"
            "?asset_uid=nullSort"
        )

    def _get_uuids(self, params=""):
        resp = self.client.get(
            f"{self.url}{params}",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        return [
            r["uuid"] for r in resp.json()["results"]
        ]

    def test_null_start_last_ascending(self):
        uuids = self._get_uuids("&ordering=start")
        self.assertEqual(uuids[-1], "null-b")

    def test_null_start_last_descending(self):
        uuids = self._get_uuids("&ordering=-start")
        self.assertEqual(uuids[-1], "null-b")

    def test_null_area_last_ascending(self):
        uuids = self._get_uuids("&ordering=area_ha")
        self.assertEqual(uuids[-1], "null-b")

    def test_null_area_last_descending(self):
        uuids = self._get_uuids(
            "&ordering=-area_ha"
        )
        self.assertEqual(uuids[-1], "null-b")

    def test_null_dynamic_field_last_ascending(self):
        uuids = self._get_uuids("&ordering=score")
        self.assertEqual(uuids[-1], "null-b")

    def test_null_dynamic_field_last_descending(
        self,
    ):
        uuids = self._get_uuids("&ordering=-score")
        self.assertEqual(uuids[-1], "null-b")
