from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.constants import (
    FlagSeverity,
    FlagType,
)
from api.v1.v1_odk.models import (
    FormMetadata,
    Plot,
    Submission,
)
from api.v1.v1_odk.utils.flagged_reason_converter import (
    convert_flagged_reason,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ConvertFlaggedReasonTest(TestCase):
    """Unit tests for convert_flagged_reason()."""

    def test_overlap_string(self):
        result = convert_flagged_reason(
            "Polygon overlaps with: Farmer A (inst_a)"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]["type"], FlagType.OVERLAP
        )
        self.assertEqual(
            result[0]["severity"], FlagSeverity.ERROR
        )

    def test_too_few_vertices(self):
        result = convert_flagged_reason(
            "Polygon has too few vertices. "
            "Minimum 3 distinct points required."
        )
        self.assertEqual(
            result[0]["type"],
            FlagType.GEOMETRY_TOO_FEW_VERTICES,
        )

    def test_self_intersect(self):
        result = convert_flagged_reason(
            "Polygon lines intersect or cross "
            "each other."
        )
        self.assertEqual(
            result[0]["type"],
            FlagType.GEOMETRY_SELF_INTERSECT,
        )

    def test_area_too_small(self):
        result = convert_flagged_reason(
            "Polygon area is too small. "
            "Minimum 10 square meters required."
        )
        self.assertEqual(
            result[0]["type"],
            FlagType.GEOMETRY_AREA_TOO_SMALL,
        )

    def test_no_polygon_data(self):
        result = convert_flagged_reason(
            "No polygon data found in submission."
        )
        self.assertEqual(
            result[0]["type"],
            FlagType.GEOMETRY_NO_DATA,
        )

    def test_failed_to_parse(self):
        result = convert_flagged_reason(
            "Failed to parse polygon geometry."
        )
        self.assertEqual(
            result[0]["type"],
            FlagType.GEOMETRY_PARSE_FAIL,
        )

    def test_none_returns_none(self):
        self.assertIsNone(
            convert_flagged_reason(None)
        )

    def test_empty_string_returns_none(self):
        self.assertIsNone(
            convert_flagged_reason("")
        )

    def test_already_list_returns_same(self):
        existing = [
            {
                "type": FlagType.OVERLAP,
                "severity": FlagSeverity.ERROR,
                "note": "test",
            }
        ]
        result = convert_flagged_reason(existing)
        self.assertEqual(result, existing)

    def test_unknown_string_defaults(self):
        result = convert_flagged_reason(
            "Something unexpected happened"
        )
        self.assertEqual(
            result[0]["type"],
            FlagType.GEOMETRY_PARSE_FAIL,
        )

    def test_note_preserves_original(self):
        original = (
            "Polygon overlaps with: "
            "Farmer A (inst_a)"
        )
        result = convert_flagged_reason(original)
        self.assertEqual(
            result[0]["note"], original
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class MigrateFlaggedReasonCommandTest(TestCase):
    """Tests for migrate_flagged_reason command."""

    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="mfr-form",
            name="Test Form",
        )
        self.sub = Submission.objects.create(
            uuid="mfr-sub-1",
            form=self.form,
            kobo_id="1",
            submission_time=1700000000000,
            raw_data={},
        )

    def _make_plot(self, uuid, flagged_reason):
        return Plot.objects.create(
            uuid=uuid,
            form=self.form,
            submission=self.sub
            if uuid == "mfr-plot-1"
            else None,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            flagged_for_review=(
                True if flagged_reason else None
            ),
            flagged_reason=flagged_reason,
        )

    def test_converts_overlap_string(self):
        plot = self._make_plot(
            "mfr-plot-1",
            [
                {
                    "type": "raw_string_placeholder",
                    "severity": "error",
                    "note": "temp",
                }
            ],
        )
        # Simulate legacy string by direct DB update
        Plot.objects.filter(pk=plot.pk).update(
            flagged_reason="Polygon overlaps with: X"
        )
        out = StringIO()
        call_command(
            "migrate_flagged_reason", stdout=out
        )
        plot.refresh_from_db()
        self.assertIsInstance(
            plot.flagged_reason, list
        )
        self.assertEqual(
            plot.flagged_reason[0]["type"],
            FlagType.OVERLAP,
        )

    def test_dry_run_no_modification(self):
        plot = self._make_plot("mfr-plot-1", None)
        Plot.objects.filter(pk=plot.pk).update(
            flagged_reason=(
                "No polygon data found in submission."
            )
        )
        out = StringIO()
        call_command(
            "migrate_flagged_reason",
            "--dry-run",
            stdout=out,
        )
        plot.refresh_from_db()
        # Should still be the raw string
        self.assertEqual(
            plot.flagged_reason,
            "No polygon data found in submission.",
        )
        self.assertIn("[DRY RUN]", out.getvalue())

    def test_skips_null_reason(self):
        self._make_plot("mfr-plot-1", None)
        out = StringIO()
        call_command(
            "migrate_flagged_reason", stdout=out
        )
        self.assertIn("Converted: 0", out.getvalue())

    def test_output_shows_counts(self):
        plot = self._make_plot("mfr-plot-1", None)
        Plot.objects.filter(pk=plot.pk).update(
            flagged_reason=(
                "Failed to parse polygon geometry."
            )
        )
        out = StringIO()
        call_command(
            "migrate_flagged_reason", stdout=out
        )
        output = out.getvalue()
        self.assertIn("Converted: 1", output)
        self.assertIn("Skipped: 0", output)
