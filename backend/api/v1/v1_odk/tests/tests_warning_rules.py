import math

from django.test import TestCase

from api.v1.v1_odk.constants import (
    FlagSeverity,
    FlagType,
    WarningThresholds,
)
from api.v1.v1_odk.utils.warning_rules import (
    coefficient_of_variation,
    evaluate_warnings,
    haversine_distance,
    parse_odk_geoshape_full,
)


class ParseOdkGeoshapeFullTest(TestCase):
    def test_basic_parse(self):
        s = (
            "-7.39 109.36 0 5.0;"
            "-7.40 109.37 0 3.0;"
            "-7.41 109.38 0 4.0;"
            "-7.39 109.36 0 5.0"
        )
        pts = parse_odk_geoshape_full(s)
        self.assertEqual(len(pts), 4)
        self.assertAlmostEqual(pts[0]["lat"], -7.39)
        self.assertAlmostEqual(pts[0]["lon"], 109.36)
        self.assertAlmostEqual(pts[0]["acc"], 5.0)

    def test_missing_accuracy(self):
        s = "-7.39 109.36;-7.40 109.37;-7.41 109.38"
        pts = parse_odk_geoshape_full(s)
        self.assertEqual(len(pts), 3)
        self.assertAlmostEqual(pts[0]["acc"], 0.0)
        self.assertAlmostEqual(pts[0]["alt"], 0.0)

    def test_none_input(self):
        self.assertIsNone(parse_odk_geoshape_full(None))

    def test_empty_input(self):
        self.assertIsNone(parse_odk_geoshape_full(""))

    def test_too_few_points(self):
        s = "-7.39 109.36 0 5.0;-7.40 109.37 0 3.0"
        self.assertIsNone(parse_odk_geoshape_full(s))

    def test_invalid_input(self):
        self.assertIsNone(
            parse_odk_geoshape_full("not a polygon")
        )


class HaversineDistanceTest(TestCase):
    def test_same_point(self):
        d = haversine_distance(0, 0, 0, 0)
        self.assertAlmostEqual(d, 0.0)

    def test_known_distance(self):
        # ~111 km between 0,0 and 1,0
        d = haversine_distance(0, 0, 1, 0)
        self.assertAlmostEqual(d, 111195, delta=200)

    def test_short_distance(self):
        # Two close points
        d = haversine_distance(
            -7.39, 109.36, -7.3901, 109.36
        )
        self.assertGreater(d, 0)
        self.assertLess(d, 20)


class CoefficientOfVariationTest(TestCase):
    def test_uniform_values(self):
        cv = coefficient_of_variation(
            [10.0, 10.0, 10.0]
        )
        self.assertAlmostEqual(cv, 0.0)

    def test_varied_values(self):
        cv = coefficient_of_variation(
            [10.0, 20.0, 30.0]
        )
        self.assertGreater(cv, 0)

    def test_single_value(self):
        cv = coefficient_of_variation([10.0])
        self.assertAlmostEqual(cv, 0.0)

    def test_empty(self):
        cv = coefficient_of_variation([])
        self.assertAlmostEqual(cv, 0.0)

    def test_two_values(self):
        cv = coefficient_of_variation([5.0, 15.0])
        self.assertGreater(cv, 0)


class EvaluateWarningsW1Test(TestCase):
    """W1: GPS accuracy too low."""

    def test_high_accuracy_triggers(self):
        # 3 points with acc > 15m
        s = (
            "-7.39 109.36 0 20.0;"
            "-7.40 109.37 0 18.0;"
            "-7.41 109.38 0 22.0;"
            "-7.39 109.36 0 20.0"
        )
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertIn(FlagType.GPS_ACCURACY_LOW, types)

    def test_low_accuracy_no_warning(self):
        s = (
            "-7.39 109.36 0 5.0;"
            "-7.40 109.37 0 3.0;"
            "-7.41 109.38 0 4.0;"
            "-7.39 109.36 0 5.0"
        )
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertNotIn(
            FlagType.GPS_ACCURACY_LOW, types
        )

    def test_all_zero_accuracy_no_warning(self):
        s = (
            "-7.39 109.36 0 0.0;"
            "-7.40 109.37 0 0.0;"
            "-7.41 109.38 0 0.0;"
            "-7.39 109.36 0 0.0"
        )
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertNotIn(
            FlagType.GPS_ACCURACY_LOW, types
        )

    def test_mixed_zero_and_real_accuracy(self):
        # Only non-zero values averaged: (20+18)/2 = 19
        s = (
            "-7.39 109.36 0 20.0;"
            "-7.40 109.37 0 0.0;"
            "-7.41 109.38 0 18.0;"
            "-7.39 109.36 0 20.0"
        )
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertIn(FlagType.GPS_ACCURACY_LOW, types)


class EvaluateWarningsW2Test(TestCase):
    """W2: Point gap too large."""

    def test_large_gap_triggers(self):
        # Points ~600m apart
        s = (
            "-7.39 109.36 0 0;"
            "-7.39 109.366 0 0;"
            "-7.395 109.366 0 0;"
            "-7.39 109.36 0 0"
        )
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertIn(FlagType.POINT_GAP_LARGE, types)

    def test_small_gap_no_warning(self):
        # Points very close together
        s = (
            "-7.3900 109.3600 0 0;"
            "-7.3901 109.3601 0 0;"
            "-7.3902 109.3600 0 0;"
            "-7.3900 109.3600 0 0"
        )
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertNotIn(
            FlagType.POINT_GAP_LARGE, types
        )

    def test_reports_per_segment(self):
        # All segments have large gaps
        s = (
            "-7.39 109.36 0 0;"
            "-7.39 109.37 0 0;"
            "-7.40 109.37 0 0;"
            "-7.39 109.36 0 0"
        )
        warnings = evaluate_warnings(s, 5.0)
        gap_warnings = [
            w
            for w in warnings
            if w["type"] == FlagType.POINT_GAP_LARGE
        ]
        # Each segment > 50m should produce a warning
        for w in gap_warnings:
            self.assertIn("points", w["note"])


class EvaluateWarningsW3Test(TestCase):
    """W3: Uneven point spacing."""

    def test_uneven_spacing_triggers(self):
        # One very long segment, one very short
        s = (
            "-7.39 109.36 0 0;"
            "-7.39 109.37 0 0;"
            "-7.3901 109.3701 0 0;"
            "-7.39 109.36 0 0"
        )
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertIn(
            FlagType.POINT_SPACING_UNEVEN, types
        )

    def test_even_spacing_no_warning(self):
        # Roughly equidistant points
        s = (
            "-7.390 109.360 0 0;"
            "-7.391 109.360 0 0;"
            "-7.392 109.360 0 0;"
            "-7.393 109.360 0 0;"
            "-7.390 109.360 0 0"
        )
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertNotIn(
            FlagType.POINT_SPACING_UNEVEN, types
        )


class EvaluateWarningsW4Test(TestCase):
    """W4: Area too large."""

    def test_large_area_triggers(self):
        s = (
            "-7.39 109.36 0 0;"
            "-7.40 109.37 0 0;"
            "-7.41 109.38 0 0;"
            "-7.39 109.36 0 0"
        )
        warnings = evaluate_warnings(s, 25.0)
        types = [w["type"] for w in warnings]
        self.assertIn(FlagType.AREA_TOO_LARGE, types)

    def test_small_area_no_warning(self):
        s = (
            "-7.39 109.36 0 0;"
            "-7.40 109.37 0 0;"
            "-7.41 109.38 0 0;"
            "-7.39 109.36 0 0"
        )
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertNotIn(
            FlagType.AREA_TOO_LARGE, types
        )

    def test_none_area_no_warning(self):
        s = (
            "-7.39 109.36 0 0;"
            "-7.40 109.37 0 0;"
            "-7.41 109.38 0 0;"
            "-7.39 109.36 0 0"
        )
        warnings = evaluate_warnings(s, None)
        types = [w["type"] for w in warnings]
        self.assertNotIn(
            FlagType.AREA_TOO_LARGE, types
        )

    def test_boundary_area_no_warning(self):
        s = (
            "-7.39 109.36 0 0;"
            "-7.40 109.37 0 0;"
            "-7.41 109.38 0 0;"
            "-7.39 109.36 0 0"
        )
        # Exactly at threshold → no warning
        warnings = evaluate_warnings(
            s, WarningThresholds.AREA_MAX_HA
        )
        types = [w["type"] for w in warnings]
        self.assertNotIn(
            FlagType.AREA_TOO_LARGE, types
        )


class EvaluateWarningsW5Test(TestCase):
    """W5: Too few vertices (rough boundary)."""

    def test_six_vertices_triggers(self):
        # 6 distinct + closing = 7 points
        s = (
            "-7.390 109.360 0 0;"
            "-7.391 109.361 0 0;"
            "-7.392 109.362 0 0;"
            "-7.393 109.361 0 0;"
            "-7.392 109.360 0 0;"
            "-7.391 109.359 0 0;"
            "-7.390 109.360 0 0"
        )
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertIn(
            FlagType.VERTICES_TOO_FEW_ROUGH, types
        )

    def test_ten_vertices_triggers(self):
        # 10 distinct + closing = 11 points
        pts = [
            f"-7.{390 + i} 109.{360 + i} 0 0"
            for i in range(10)
        ]
        pts.append(pts[0])
        s = ";".join(pts)
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertIn(
            FlagType.VERTICES_TOO_FEW_ROUGH, types
        )

    def test_five_vertices_no_warning(self):
        # 5 distinct + closing = 6 points
        s = (
            "-7.390 109.360 0 0;"
            "-7.391 109.361 0 0;"
            "-7.392 109.362 0 0;"
            "-7.393 109.361 0 0;"
            "-7.392 109.360 0 0;"
            "-7.390 109.360 0 0"
        )
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertNotIn(
            FlagType.VERTICES_TOO_FEW_ROUGH, types
        )

    def test_eleven_vertices_no_warning(self):
        pts = [
            f"-7.{390 + i} 109.{360 + i} 0 0"
            for i in range(11)
        ]
        pts.append(pts[0])
        s = ";".join(pts)
        warnings = evaluate_warnings(s, 5.0)
        types = [w["type"] for w in warnings]
        self.assertNotIn(
            FlagType.VERTICES_TOO_FEW_ROUGH, types
        )


class EvaluateWarningsMultipleTest(TestCase):
    """Multiple warnings on same plot."""

    def test_multiple_warnings(self):
        # High accuracy + large area
        s = (
            "-7.39 109.36 0 20.0;"
            "-7.40 109.37 0 18.0;"
            "-7.41 109.38 0 22.0;"
            "-7.39 109.36 0 20.0"
        )
        warnings = evaluate_warnings(s, 25.0)
        types = [w["type"] for w in warnings]
        self.assertIn(FlagType.GPS_ACCURACY_LOW, types)
        self.assertIn(FlagType.AREA_TOO_LARGE, types)

    def test_no_warnings_clean_plot(self):
        # Low accuracy, small area, many vertices,
        # evenly spaced
        pts = []
        for i in range(15):
            angle = 2 * math.pi * i / 15
            lat = -7.39 + 0.001 * math.cos(angle)
            lon = 109.36 + 0.001 * math.sin(angle)
            pts.append(f"{lat} {lon} 0 3.0")
        pts.append(pts[0])
        s = ";".join(pts)
        warnings = evaluate_warnings(s, 2.0)
        self.assertEqual(
            warnings, [], f"Unexpected: {warnings}"
        )

    def test_all_warnings_severity(self):
        s = (
            "-7.39 109.36 0 20.0;"
            "-7.40 109.37 0 18.0;"
            "-7.41 109.38 0 22.0;"
            "-7.39 109.36 0 20.0"
        )
        warnings = evaluate_warnings(s, 25.0)
        for w in warnings:
            self.assertEqual(
                w["severity"], FlagSeverity.WARNING
            )

    def test_unparseable_returns_empty(self):
        warnings = evaluate_warnings(None, 5.0)
        self.assertEqual(warnings, [])

    def test_empty_string_returns_empty(self):
        warnings = evaluate_warnings("", 5.0)
        self.assertEqual(warnings, [])
