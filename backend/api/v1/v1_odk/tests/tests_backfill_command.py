from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    FormMetadata,
    Plot,
    Submission,
)

VALID_GEOSHAPE = (
    "7.05 38.47 0 0;"
    "7.06 38.47 0 0;"
    "7.06 38.48 0 0;"
    "7.05 38.48 0 0;"
    "7.05 38.47 0 0"
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class BackfillPolygonSourceTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="bf-form",
            name="Backfill Form",
            polygon_field="primary,fallback",
        )
        self.sub = Submission.objects.create(
            uuid="bf-sub-1",
            form=self.form,
            kobo_id="1",
            submission_time=1700000000000,
            raw_data={
                "fallback": VALID_GEOSHAPE,
            },
        )
        self.plot = Plot.objects.create(
            form=self.form,
            submission=self.sub,
            plot_name="Farmer A",
            polygon_wkt=(
                "POLYGON(("
                "38.47 7.05, 38.47 7.06, "
                "38.48 7.06, 38.48 7.05, "
                "38.47 7.05))"
            ),
            min_lat=7.05,
            max_lat=7.06,
            min_lon=38.47,
            max_lon=38.48,
            region="R",
            sub_region="SR",
            created_at=1700000000000,
        )

    def test_backfill_sets_source_field(self):
        self.assertIsNone(
            self.plot.polygon_source_field
        )
        out = StringIO()
        call_command(
            "backfill_polygon_source",
            stdout=out,
        )
        self.plot.refresh_from_db()
        self.assertEqual(
            self.plot.polygon_source_field,
            "fallback",
        )
        self.assertIn("Updated 1", out.getvalue())

    def test_dry_run_does_not_write(self):
        out = StringIO()
        call_command(
            "backfill_polygon_source",
            "--dry-run",
            stdout=out,
        )
        self.plot.refresh_from_db()
        self.assertIsNone(
            self.plot.polygon_source_field
        )
        self.assertIn("DRY RUN", out.getvalue())

    def test_skips_plot_without_matching_data(
        self,
    ):
        sub2 = Submission.objects.create(
            uuid="bf-sub-2",
            form=self.form,
            kobo_id="2",
            submission_time=1700000000000,
            raw_data={"other_field": "value"},
        )
        Plot.objects.create(
            form=self.form,
            submission=sub2,
            plot_name="No Geo",
            region="R",
            sub_region="SR",
            created_at=1700000000000,
        )
        out = StringIO()
        call_command(
            "backfill_polygon_source",
            stdout=out,
        )
        self.assertIn("skipped 1", out.getvalue())

    def test_skips_already_backfilled(self):
        self.plot.polygon_source_field = "primary"
        self.plot.save()
        out = StringIO()
        call_command(
            "backfill_polygon_source",
            stdout=out,
        )
        self.assertIn("Found 0", out.getvalue())
        self.plot.refresh_from_db()
        self.assertEqual(
            self.plot.polygon_source_field,
            "primary",
        )
