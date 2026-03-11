from django.test import TestCase

from api.v1.v1_odk.utils.area_calc import (
    calculate_area_ha,
)


class CalculateAreaHaTest(TestCase):
    def test_valid_polygon_returns_float(self):
        polygon = (
            "39.468 -0.330 0.0 0.0;"
            "39.467 -0.330 0.0 0.0;"
            "39.467 -0.329 0.0 0.0;"
            "39.468 -0.329 0.0 0.0;"
            "39.468 -0.330 0.0 0.0"
        )
        result = calculate_area_ha(polygon)
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0)

    def test_empty_string_returns_none(self):
        result = calculate_area_ha("")
        self.assertIsNone(result)

    def test_none_returns_none(self):
        result = calculate_area_ha(None)
        self.assertIsNone(result)

    def test_fewer_than_3_points_returns_none(self):
        polygon = (
            "39.468 -0.330 0.0 0.0;"
            "39.467 -0.330 0.0 0.0"
        )
        result = calculate_area_ha(polygon)
        self.assertIsNone(result)

    def test_real_coordinates(self):
        polygon = (
            "39.46805687327031 "
            "-0.3300974518060684 0.0 0.0;"
            "39.4676399 "
            "-0.3301053 0.0 0.0;"
            "39.46765620922471 "
            "-0.3298141434788704 0.0 0.0;"
            "39.46803720247954 "
            "-0.3297269716858864 0.0 0.0;"
            "39.46805687327031 "
            "-0.3300974518060684 0.0 0.0"
        )
        result = calculate_area_ha(polygon)
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0)

    def test_trailing_semicolon(self):
        polygon = (
            "39.468 -0.330 0.0 0.0;"
            "39.467 -0.330 0.0 0.0;"
            "39.467 -0.329 0.0 0.0;"
            "39.468 -0.329 0.0 0.0;"
            "39.468 -0.330 0.0 0.0;"
        )
        result = calculate_area_ha(polygon)
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0)

    def test_result_rounded_to_2_decimals(self):
        polygon = (
            "39.468 -0.330 0.0 0.0;"
            "39.467 -0.330 0.0 0.0;"
            "39.467 -0.329 0.0 0.0;"
            "39.468 -0.329 0.0 0.0;"
            "39.468 -0.330 0.0 0.0"
        )
        result = calculate_area_ha(polygon)
        self.assertIsNotNone(result)
        as_str = str(result)
        if "." in as_str:
            decimals = len(as_str.split(".")[1])
            self.assertLessEqual(decimals, 2)

    def test_invalid_non_numeric_returns_none(self):
        polygon = (
            "abc def 0.0 0.0;"
            "ghi jkl 0.0 0.0;"
            "mno pqr 0.0 0.0;"
            "abc def 0.0 0.0"
        )
        result = calculate_area_ha(polygon)
        self.assertIsNone(result)
