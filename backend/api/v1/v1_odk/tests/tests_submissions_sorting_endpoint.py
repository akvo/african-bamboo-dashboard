from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (FormMetadata, FormOption, FormQuestion, Plot,
                                  Submission)
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin
from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionSortingTest(TestCase, OdkTestHelperMixin):
    """Tests for server-side sorting of the
    submissions list endpoint via ?ordering= param.

    Covers hardcoded orderings (kobo_id, reviewed_by,
    start, end, area_ha) and dynamic sortable_fields
    from raw_data JSON keys."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()

        self.reviewer = SystemUser.objects.create_superuser(
            email="reviewer@test.local",
            password="Pass1234",
            name="Alice",
        )
        self.reviewer2 = SystemUser.objects.create_superuser(
            email="reviewer2@test.local",
            password="Pass1234",
            name="Bob",
        )

        self.form = FormMetadata.objects.create(
            asset_uid="sortForm",
            name="Sort Form",
            sortable_fields=[
                "First_Name",
                "Father_s_Name",
                "enumerator_id",
            ],
        )

        # select_one question with options where
        # raw names and labels sort differently
        q_enum = FormQuestion.objects.create(
            form=self.form,
            name="enumerator_id",
            label="Enumerator",
            type="select_one",
        )
        FormOption.objects.create(
            question=q_enum,
            name="enum_z",
            label="Alice",
        )
        FormOption.objects.create(
            question=q_enum,
            name="enum_a",
            label="Zara",
        )
        FormOption.objects.create(
            question=q_enum,
            name="enum_m",
            label="Bob",
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
                "enumerator_id": "enum_z",
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
                "enumerator_id": "enum_a",
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

        self.url = "/api/v1/odk/submissions/" "?asset_uid=sortForm"

    def _get_uuids(self, params=""):
        resp = self.client.get(
            f"{self.url}{params}",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        return [r["uuid"] for r in resp.json()["results"]]

    # ── Hardcoded orderings ──

    def test_sort_by_kobo_id_asc(self):
        uuids = self._get_uuids("&ordering=kobo_id")
        self.assertEqual(uuids, ["sort-b", "sort-c", "sort-a"])

    def test_sort_by_kobo_id_desc(self):
        uuids = self._get_uuids("&ordering=-kobo_id")
        self.assertEqual(uuids, ["sort-a", "sort-c", "sort-b"])

    def test_sort_by_reviewed_by_asc(self):
        uuids = self._get_uuids("&ordering=reviewed_by")
        # Alice < Bob, null last
        self.assertEqual(uuids, ["sort-a", "sort-b", "sort-c"])

    def test_sort_by_reviewed_by_desc(self):
        uuids = self._get_uuids("&ordering=-reviewed_by")
        # Bob > Alice, null last
        self.assertEqual(uuids, ["sort-b", "sort-a", "sort-c"])

    def test_sort_by_start_asc(self):
        uuids = self._get_uuids("&ordering=start")
        self.assertEqual(uuids, ["sort-a", "sort-c", "sort-b"])

    def test_sort_by_start_desc(self):
        uuids = self._get_uuids("&ordering=-start")
        self.assertEqual(uuids, ["sort-b", "sort-c", "sort-a"])

    def test_sort_by_end_asc(self):
        uuids = self._get_uuids("&ordering=end")
        self.assertEqual(uuids, ["sort-a", "sort-c", "sort-b"])

    def test_sort_by_end_desc(self):
        uuids = self._get_uuids("&ordering=-end")
        self.assertEqual(uuids, ["sort-b", "sort-c", "sort-a"])

    def test_sort_by_area_ha_asc(self):
        uuids = self._get_uuids("&ordering=area_ha")
        # 2.0 < 5.0, null last
        self.assertEqual(uuids, ["sort-b", "sort-a", "sort-c"])

    def test_sort_by_area_ha_desc(self):
        uuids = self._get_uuids("&ordering=-area_ha")
        # 5.0 > 2.0, null last
        self.assertEqual(uuids, ["sort-a", "sort-b", "sort-c"])

    # ── Default ordering ──

    def test_default_ordering_without_param(self):
        """Without ?ordering=, submissions are ordered
        by -submission_time (newest first)."""
        uuids = self._get_uuids("")
        self.assertEqual(uuids, ["sort-c", "sort-b", "sort-a"])

    # ── Invalid ordering ──

    def test_invalid_ordering_ignored(self):
        """An invalid ordering value falls back to
        default ordering."""
        uuids = self._get_uuids("&ordering=nonexistent")
        self.assertEqual(uuids, ["sort-c", "sort-b", "sort-a"])

    # ── Dynamic sortable_fields ──

    def test_sort_by_dynamic_field_asc(self):
        """Sort by a raw_data field configured in
        sortable_fields."""
        uuids = self._get_uuids("&ordering=First_Name")
        # Alpha < Charlie, null last
        self.assertEqual(uuids, ["sort-b", "sort-a", "sort-c"])

    def test_sort_by_dynamic_field_desc(self):
        uuids = self._get_uuids("&ordering=-First_Name")
        # Charlie > Alpha, null last
        self.assertEqual(uuids, ["sort-a", "sort-b", "sort-c"])

    def test_sort_by_second_dynamic_field(self):
        """Sort by another configured sortable_field
        (Father_s_Name)."""
        uuids = self._get_uuids("&ordering=Father_s_Name")
        # Bravo < Delta < Foxtrot
        self.assertEqual(uuids, ["sort-b", "sort-a", "sort-c"])

    def test_dynamic_field_not_in_allowlist(self):
        """A raw_data field NOT in sortable_fields
        is ignored, falls back to default ordering."""
        uuids = self._get_uuids("&ordering=Grandfather_s_Name")
        # Default: -submission_time
        self.assertEqual(uuids, ["sort-c", "sort-b", "sort-a"])

    # ── select_one label-based sorting ──

    def test_sort_select_one_by_label_asc(self):
        """select_one field sorts by option label,
        not raw value.
        Raw order: enum_a (Zara) < enum_m < enum_z
        Label order: Alice < Bob < Zara
        ASC by label: Alice(a) < Zara(b), null last.
        """
        uuids = self._get_uuids("&ordering=enumerator_id")
        # Alice=enum_z(sub_a), Zara=enum_a(sub_b),
        # null(sub_c) last
        self.assertEqual(uuids, ["sort-a", "sort-b", "sort-c"])

    def test_sort_select_one_by_label_desc(self):
        """DESC by label: Zara > Alice, null last."""
        uuids = self._get_uuids("&ordering=-enumerator_id")
        # Zara=enum_a(sub_b), Alice=enum_z(sub_a),
        # null(sub_c) last
        self.assertEqual(uuids, ["sort-b", "sort-a", "sort-c"])

    def test_sort_text_field_still_uses_raw(self):
        """Non-select fields still sort by raw value
        (regression guard)."""
        uuids = self._get_uuids("&ordering=First_Name")
        # Alpha < Charlie (raw text sort), null last
        self.assertEqual(uuids, ["sort-b", "sort-a", "sort-c"])

    # ── Sorting with pagination ──

    def test_sort_with_pagination(self):
        """Sorting respects limit/offset."""
        resp = self.client.get(
            f"{self.url}&ordering=kobo_id" "&limit=2&offset=0",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        uuids = [r["uuid"] for r in data["results"]]
        self.assertEqual(uuids, ["sort-b", "sort-c"])
        self.assertEqual(data["count"], 3)

        # Page 2
        resp = self.client.get(
            f"{self.url}&ordering=kobo_id" "&limit=2&offset=2",
            **self.auth,
        )
        uuids = [r["uuid"] for r in resp.json()["results"]]
        self.assertEqual(uuids, ["sort-a"])

    # ── Sorting with filters ──

    def test_sort_combined_with_status_filter(self):
        """Sorting works when combined with status
        filter."""
        self.sub_a.approval_status = 1
        self.sub_a.save()
        self.sub_b.approval_status = 1
        self.sub_b.save()

        uuids = self._get_uuids("&status=approved&ordering=kobo_id")
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
            [
                "First_Name",
                "Father_s_Name",
                "enumerator_id",
            ],
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
            "/api/v1/odk/submissions/" "?asset_uid=noSort",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["sortable_fields"], [])

    def test_list_response_no_asset_uid(self):
        """Without asset_uid, sortable_fields is
        empty."""
        resp = self.client.get(
            "/api/v1/odk/submissions/",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["sortable_fields"], [])


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionSortingNullHandlingTest(TestCase, OdkTestHelperMixin):
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

        self.url = "/api/v1/odk/submissions/" "?asset_uid=nullSort"

    def _get_uuids(self, params=""):
        resp = self.client.get(
            f"{self.url}{params}",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        return [r["uuid"] for r in resp.json()["results"]]

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
        uuids = self._get_uuids("&ordering=-area_ha")
        self.assertEqual(uuids[-1], "null-b")

    def test_null_dynamic_field_last_ascending(self):
        uuids = self._get_uuids("&ordering=score")
        self.assertEqual(uuids[-1], "null-b")

    def test_null_dynamic_field_last_descending(
        self,
    ):
        uuids = self._get_uuids("&ordering=-score")
        self.assertEqual(uuids[-1], "null-b")


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionSortingPaginationStabilityTest(TestCase, OdkTestHelperMixin):
    """Verify that rows with identical sort values
    produce stable pagination (no duplicates or
    missing rows) thanks to the secondary tiebreaker
    ordering (-submission_time, pk)."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()

        self.form = FormMetadata.objects.create(
            asset_uid="stableSort",
            name="Stable Sort Form",
            sortable_fields=["colour"],
        )

        # 5 submissions, all with the same area_ha
        # and same dynamic field value.
        # They differ only in submission_time and pk.
        self.subs = []
        for i in range(5):
            sub = Submission.objects.create(
                uuid=f"stable-{i}",
                form=self.form,
                kobo_id=str(500 + i),
                submission_time=(1700000000000 + i * 1000),
                raw_data={"colour": "red"},
            )
            Plot.objects.create(
                plot_name=f"P{i}",
                form=self.form,
                region="R",
                sub_region="S",
                created_at=1700000000000 + i * 1000,
                submission=sub,
                area_ha=1.0,
            )
            self.subs.append(sub)

        self.url = "/api/v1/odk/submissions/" "?asset_uid=stableSort"

    def _get_all_uuids_paged(self, ordering, page_size=2):
        """Fetch all pages and return concatenated
        uuid list."""
        all_uuids = []
        offset = 0
        while True:
            resp = self.client.get(
                f"{self.url}"
                f"&ordering={ordering}"
                f"&limit={page_size}"
                f"&offset={offset}",
                **self.auth,
            )
            self.assertEqual(resp.status_code, 200)
            results = resp.json()["results"]
            if not results:
                break
            all_uuids.extend(r["uuid"] for r in results)
            offset += page_size
        return all_uuids

    def test_no_duplicates_area_ha_asc(self):
        """All 5 rows with identical area_ha appear
        exactly once across pages."""
        uuids = self._get_all_uuids_paged("area_ha")
        self.assertEqual(len(uuids), 5)
        self.assertEqual(len(set(uuids)), 5)

    def test_no_duplicates_area_ha_desc(self):
        uuids = self._get_all_uuids_paged("-area_ha")
        self.assertEqual(len(uuids), 5)
        self.assertEqual(len(set(uuids)), 5)

    def test_no_duplicates_dynamic_field(self):
        """Identical dynamic sort values still
        produce stable pages."""
        uuids = self._get_all_uuids_paged("colour")
        self.assertEqual(len(uuids), 5)
        self.assertEqual(len(set(uuids)), 5)

    def test_tiebreaker_uses_submission_time(self):
        """Within identical sort values, rows are
        ordered by -submission_time (newest first),
        then pk."""
        uuids = self._get_all_uuids_paged("area_ha", page_size=10)
        # All have same area_ha, so secondary order
        # is -submission_time (newest first)
        expected = [f"stable-{i}" for i in range(4, -1, -1)]
        self.assertEqual(uuids, expected)

    def test_pages_are_consistent(self):
        """Page 1 + page 2 + page 3 contain no
        overlapping rows."""
        page1 = self._get_all_uuids_paged("area_ha", page_size=2)
        # Re-fetch individually to confirm
        resp1 = self.client.get(
            f"{self.url}&ordering=area_ha" "&limit=2&offset=0",
            **self.auth,
        )
        resp2 = self.client.get(
            f"{self.url}&ordering=area_ha" "&limit=2&offset=2",
            **self.auth,
        )
        resp3 = self.client.get(
            f"{self.url}&ordering=area_ha" "&limit=2&offset=4",
            **self.auth,
        )
        p1 = [r["uuid"] for r in resp1.json()["results"]]
        p2 = [r["uuid"] for r in resp2.json()["results"]]
        p3 = [r["uuid"] for r in resp3.json()["results"]]
        combined = p1 + p2 + p3
        self.assertEqual(len(combined), 5)
        self.assertEqual(len(set(combined)), 5)
        self.assertEqual(combined, page1)
