from django.test import TestCase

from utils.polygon import (
    _build_joined_value,
    compute_bbox,
    coords_to_wkt,
    extract_plot_data,
    parse_odk_geoshape,
    validate_polygon,
)


class ParseOdkGeoshapeTest(TestCase):
    def test_valid_square_with_alt_acc(self):
        input_str = (
            "0.0 0.0 0 0; "
            "0.001 0.0 0 0; "
            "0.001 0.001 0 0; "
            "0.0 0.001 0 0; "
            "0.0 0.0 0 0"
        )
        coords = parse_odk_geoshape(input_str)
        self.assertIsNotNone(coords)
        self.assertEqual(len(coords), 5)
        # lat=0.0, lng=0.0 -> (lon=0.0, lat=0.0)
        self.assertEqual(coords[0], (0.0, 0.0))

    def test_auto_close(self):
        input_str = "9.0 38.7 0 0; " "9.001 38.7 0 0; " "9.001 38.701 0 0"
        coords = parse_odk_geoshape(input_str)
        self.assertIsNotNone(coords)
        self.assertEqual(len(coords), 4)
        self.assertEqual(coords[0], coords[-1])

    def test_two_points_returns_none(self):
        input_str = "0.0 0.0 0 0; 1.0 1.0 0 0"
        self.assertIsNone(parse_odk_geoshape(input_str))

    def test_without_alt_acc(self):
        input_str = (
            "0.0 0.0; " "0.001 0.0; " "0.001 0.001; " "0.0 0.001; " "0.0 0.0"
        )
        coords = parse_odk_geoshape(input_str)
        self.assertIsNotNone(coords)
        self.assertEqual(len(coords), 5)

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_odk_geoshape(""))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(parse_odk_geoshape("   "))

    def test_invalid_format_returns_none(self):
        self.assertIsNone(parse_odk_geoshape("not a polygon"))

    def test_coordinate_order_lon_lat(self):
        input_str = (
            "9.0 38.7 0 0; "
            "9.001 38.7 0 0; "
            "9.001 38.701 0 0; "
            "9.0 38.701 0 0"
        )
        coords = parse_odk_geoshape(input_str)
        # ODK: lat=9.0 lng=38.7
        # -> (lon=38.7, lat=9.0)
        self.assertAlmostEqual(coords[0][0], 38.7)
        self.assertAlmostEqual(coords[0][1], 9.0)


class CoordsToWktTest(TestCase):
    def test_simple_polygon(self):
        coords = [
            (0.0, 0.0),
            (1.0, 0.0),
            (1.0, 1.0),
            (0.0, 0.0),
        ]
        wkt = coords_to_wkt(coords)
        self.assertEqual(
            wkt,
            "POLYGON((" "0.0 0.0, 1.0 0.0, " "1.0 1.0, 0.0 0.0))",
        )


class ComputeBboxTest(TestCase):
    def test_simple_bbox(self):
        coords = [
            (38.7, 9.0),
            (38.8, 9.0),
            (38.8, 9.1),
            (38.7, 9.1),
            (38.7, 9.0),
        ]
        bbox = compute_bbox(coords)
        self.assertAlmostEqual(bbox["min_lon"], 38.7)
        self.assertAlmostEqual(bbox["max_lon"], 38.8)
        self.assertAlmostEqual(bbox["min_lat"], 9.0)
        self.assertAlmostEqual(bbox["max_lat"], 9.1)


class ValidatePolygonTest(TestCase):
    def test_valid_large_polygon(self):
        coords = [
            (0.0, 0.0),
            (0.001, 0.0),
            (0.001, 0.001),
            (0.0, 0.001),
            (0.0, 0.0),
        ]
        valid, msg = validate_polygon(coords)
        self.assertTrue(valid)
        self.assertEqual(msg, "")

    def test_too_few_vertices(self):
        coords = [
            (0.0, 0.0),
            (1.0, 0.0),
            (0.0, 0.0),
        ]
        valid, msg = validate_polygon(coords)
        self.assertFalse(valid)
        self.assertIn("vertices", msg)

    def test_area_too_small(self):
        coords = [
            (0.0, 0.0),
            (0.000001, 0.0),
            (0.000001, 0.000001),
            (0.0, 0.000001),
            (0.0, 0.0),
        ]
        valid, msg = validate_polygon(coords)
        self.assertFalse(valid)
        self.assertIn("small", msg)

    def test_self_intersecting_bowtie(self):
        coords = [
            (0.0, 0.0),
            (1.0, 1.0),
            (1.0, 0.0),
            (0.0, 1.0),
            (0.0, 0.0),
        ]
        valid, msg = validate_polygon(coords)
        self.assertFalse(valid)
        self.assertIn("intersect", msg.lower())


class ExtractPlotDataTest(TestCase):
    def _mock_form(self, **kwargs):
        class MockForm:
            polygon_field = kwargs.get("polygon_field", None)
            region_field = kwargs.get("region_field", None)
            sub_region_field = kwargs.get("sub_region_field", None)
            plot_name_field = kwargs.get("plot_name_field", None)

        return MockForm()

    def test_no_polygon_field_returns_null_geom(
        self,
    ):
        form = self._mock_form()
        result = extract_plot_data({}, form)
        self.assertIsNotNone(result)
        self.assertIsNone(result["polygon_wkt"])
        self.assertIsNone(result["min_lat"])

    def test_missing_key_returns_null_geom(self):
        form = self._mock_form(polygon_field="boundary")
        result = extract_plot_data({"other": "value"}, form)
        self.assertIsNotNone(result)
        self.assertIsNone(result["polygon_wkt"])

    def test_invalid_polygon_returns_null_geom(
        self,
    ):
        form = self._mock_form(polygon_field="boundary")
        result = extract_plot_data({"boundary": "invalid data"}, form)
        self.assertIsNotNone(result)
        self.assertIsNone(result["polygon_wkt"])

    def test_valid_extraction(self):
        form = self._mock_form(
            polygon_field="boundary",
            region_field="region",
            sub_region_field="woreda",
            plot_name_field=(
                "First_Name," "Father_s_Name," "Grandfather_s_Name"
            ),
        )
        raw = {
            "boundary": (
                "0.0 0.0 0 0; "
                "0.001 0.0 0 0; "
                "0.001 0.001 0 0; "
                "0.0 0.001 0 0; "
                "0.0 0.0 0 0"
            ),
            "region": "Oromia",
            "woreda": "Jimma",
            "First_Name": "Abebe",
            "Father_s_Name": "Kebede",
            "Grandfather_s_Name": "Tadesse",
        }
        result = extract_plot_data(raw, form)
        self.assertIsNotNone(result)
        self.assertEqual(result["region"], "Oromia")
        self.assertEqual(result["sub_region"], "Jimma")
        self.assertEqual(
            result["plot_name"],
            "Abebe Kebede Tadesse",
        )
        self.assertIn("POLYGON", result["polygon_wkt"])
        self.assertIsNotNone(result["min_lat"])

    def test_plot_name_partial_fields(self):
        form = self._mock_form(
            plot_name_field=("First_Name,Father_s_Name"),
        )
        raw = {"First_Name": "Abebe"}
        result = extract_plot_data(raw, form)
        self.assertEqual(result["plot_name"], "Abebe")

    def test_plot_name_all_empty(self):
        form = self._mock_form(
            plot_name_field=("First_Name,Father_s_Name"),
        )
        result = extract_plot_data({}, form)
        self.assertEqual(result["plot_name"], "Unknown")

    def test_polygon_field_fallback(self):
        form = self._mock_form(
            polygon_field=("primary_boundary," "fallback_boundary"),
        )
        raw = {
            "fallback_boundary": (
                "0.0 0.0 0 0; "
                "0.001 0.0 0 0; "
                "0.001 0.001 0 0; "
                "0.0 0.001 0 0; "
                "0.0 0.0 0 0"
            ),
        }
        result = extract_plot_data(raw, form)
        self.assertIsNotNone(result["polygon_wkt"])

    def test_always_returns_dict(self):
        form = self._mock_form()
        result = extract_plot_data({}, form)
        self.assertIsInstance(result, dict)
        self.assertIn("polygon_wkt", result)
        self.assertIn("plot_name", result)
        self.assertIn("region", result)
        self.assertIn("flagged_for_review", result)
        self.assertIn("flagged_reason", result)

    def test_multi_region_field_joins(self):
        form = self._mock_form(
            region_field="region,region_specify",
        )
        raw = {
            "region": "Oromia",
            "region_specify": "Zone 1",
        }
        result = extract_plot_data(raw, form)
        self.assertEqual(
            result["region"], "Oromia - Zone 1"
        )

    def test_multi_sub_region_skips_empty(self):
        form = self._mock_form(
            sub_region_field=(
                "woreda,woreda_specify,kebele"
            ),
        )
        raw = {
            "woreda": "Jimma",
            "woreda_specify": "",
            "kebele": "K01",
        }
        result = extract_plot_data(raw, form)
        self.assertEqual(
            result["sub_region"], "Jimma - K01"
        )

    def test_no_polygon_field_not_flagged(self):
        """When no polygon_field is configured,
        plot should NOT be flagged."""
        form = self._mock_form()
        result = extract_plot_data({}, form)
        self.assertIsNone(result["flagged_for_review"])
        self.assertIsNone(result["flagged_reason"])

    def test_missing_polygon_data_flagged(self):
        """When polygon_field is configured but
        data is missing, plot should be flagged."""
        form = self._mock_form(
            polygon_field="boundary"
        )
        result = extract_plot_data(
            {"other": "value"}, form
        )
        self.assertTrue(result["flagged_for_review"])
        self.assertEqual(
            result["flagged_reason"],
            "No polygon data found in submission.",
        )

    def test_unparseable_polygon_flagged(self):
        """When polygon data cannot be parsed,
        plot should be flagged."""
        form = self._mock_form(
            polygon_field="boundary"
        )
        result = extract_plot_data(
            {"boundary": "not valid geo"}, form
        )
        self.assertTrue(result["flagged_for_review"])
        self.assertEqual(
            result["flagged_reason"],
            "Failed to parse polygon geometry.",
        )

    def test_invalid_validation_flagged(self):
        """When polygon fails validation,
        plot should be flagged with the
        validation error message."""
        form = self._mock_form(
            polygon_field="boundary"
        )
        # Only 2 distinct points + closing = too few
        raw = {
            "boundary": (
                "0.0 0.0 0 0; "
                "1.0 0.0 0 0; "
                "0.0 0.0 0 0"
            ),
        }
        result = extract_plot_data(raw, form)
        self.assertTrue(result["flagged_for_review"])
        self.assertIn(
            "vertices", result["flagged_reason"]
        )

    def test_valid_polygon_not_flagged(self):
        """When polygon is valid,
        plot should NOT be flagged."""
        form = self._mock_form(
            polygon_field="boundary"
        )
        raw = {
            "boundary": (
                "0.0 0.0 0 0; "
                "0.001 0.0 0 0; "
                "0.001 0.001 0 0; "
                "0.0 0.001 0 0; "
                "0.0 0.0 0 0"
            ),
        }
        result = extract_plot_data(raw, form)
        self.assertIsNone(result["flagged_for_review"])
        self.assertIsNone(result["flagged_reason"])
        self.assertIsNotNone(result["polygon_wkt"])


class BuildJoinedValueTest(TestCase):
    def test_joins_non_empty(self):
        raw = {"a": "X", "b": "Y", "c": "Z"}
        result = _build_joined_value(raw, "a,b,c")
        self.assertEqual(result, "X - Y - Z")

    def test_skips_empty_and_missing(self):
        raw = {"a": "X", "b": "", "c": None}
        result = _build_joined_value(raw, "a,b,c,d")
        self.assertEqual(result, "X")

    def test_empty_spec_returns_empty(self):
        result = _build_joined_value(
            {"a": "X"}, None
        )
        self.assertEqual(result, "")

    def test_all_empty_returns_empty(self):
        result = _build_joined_value({}, "a,b")
        self.assertEqual(result, "")
