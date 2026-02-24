import logging
import math
import re

logger = logging.getLogger(__name__)

METERS_PER_DEGREE_AT_EQUATOR = 111320.0
MIN_VERTICES = 4  # 3 distinct points + 1 closing
MIN_AREA_SQ_METERS = 10.0
WHITESPACE_RE = re.compile(r"\s+")


def parse_odk_geoshape(input_str):
    """Parse ODK geoshape format to coordinate list.

    Input:  "lat lng alt acc; lat lng alt acc; ..."
    Output: list of (lon, lat) tuples, or None.
    """
    if not input_str or not input_str.strip():
        return None
    try:
        segments = input_str.strip().split(";")
        coords = []
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            parts = WHITESPACE_RE.split(seg)
            if len(parts) < 2:
                return None
            lat = float(parts[0])
            lng = float(parts[1])
            coords.append((lng, lat))

        if len(coords) < 3:
            return None

        if coords[0] != coords[-1]:
            coords.append(coords[0])

        return coords
    except (ValueError, IndexError):
        logger.warning(
            "Failed to parse ODK geoshape: %s",
            input_str[:100],
        )
        return None


def coords_to_wkt(coords):
    """Convert [(lon, lat), ...] to WKT POLYGON."""
    pairs = ", ".join(f"{lon} {lat}" for lon, lat in coords)
    return f"POLYGON(({pairs}))"


def compute_bbox(coords):
    """Compute bounding box from coordinates.

    Returns dict with min_lat, max_lat,
    min_lon, max_lon.
    """
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return {
        "min_lat": min(lats),
        "max_lat": max(lats),
        "min_lon": min(lons),
        "max_lon": max(lons),
    }


def _calculate_area_sq_meters(coords):
    """Shoelace formula for area, converted to
    square meters using centroid latitude."""
    n = len(coords)
    area_deg = 0.0
    for i in range(n - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        area_deg += x1 * y2 - x2 * y1
    area_deg = abs(area_deg) / 2.0

    lats = [c[1] for c in coords]
    centroid_lat = sum(lats) / len(lats)

    m_per_deg_lat = METERS_PER_DEGREE_AT_EQUATOR
    m_per_deg_lon = METERS_PER_DEGREE_AT_EQUATOR * math.cos(
        math.radians(centroid_lat)
    )
    return area_deg * m_per_deg_lat * m_per_deg_lon


def _is_valid_geometry(coords):
    """Check polygon for self-intersections
    using Shapely."""
    try:
        from shapely.geometry import Polygon as ShapelyPolygon

        poly = ShapelyPolygon(coords)
        return poly.is_valid
    except Exception:
        return False


def validate_polygon(coords):
    """Validate polygon coordinates.

    Returns (is_valid, error_message).
    If valid, error_message is empty string.
    """
    if len(coords) < MIN_VERTICES:
        return (
            False,
            "Polygon has too few vertices. "
            "Minimum 3 distinct points required.",
        )

    if not _is_valid_geometry(coords):
        return (
            False,
            "Polygon lines intersect or cross  each other.",
        )

    area = _calculate_area_sq_meters(coords)
    if area < MIN_AREA_SQ_METERS:
        return (
            False,
            "Polygon area is too small. "
            f"Minimum {MIN_AREA_SQ_METERS:.0f} "
            "square meters required.",
        )

    return (True, "")


def _split_csv_fields(field_value):
    """Split a comma-separated field config
    into a list of trimmed, non-empty names."""
    if not field_value:
        return []
    return [f.strip() for f in field_value.split(",") if f.strip()]


def _extract_first_nonempty(raw_data, fields):
    """Try each field in order, return the first
    non-empty value. Returns None if all empty."""
    for field in fields:
        val = raw_data.get(field)
        if val and str(val).strip():
            return str(val).strip()
    return None


def _build_joined_value(raw_data, field_spec):
    """Build a value from comma-separated field
    names. Non-empty values joined with ' - '.
    Returns empty string if no valid fields."""
    fields = _split_csv_fields(field_spec)
    parts = []
    for field in fields:
        val = raw_data.get(field)
        if val and str(val).strip():
            parts.append(str(val).strip())
    return " - ".join(parts) if parts else ""


def _build_plot_name(raw_data, plot_name_field):
    """Build plot name from comma-separated field
    names. Values are joined with spaces.
    Returns "Unknown" if no valid fields found."""
    fields = _split_csv_fields(plot_name_field)
    if not fields:
        return "Unknown"
    parts = []
    for field in fields:
        val = raw_data.get(field)
        if val and str(val).strip():
            parts.append(str(val).strip())
    return " ".join(parts) if parts else "Unknown"


def extract_plot_data(raw_data, form):
    """Extract plot fields from submission raw_data.

    Always returns a dict. If polygon data is
    invalid or missing, geometry fields are None.
    Plots are always created so users can fix
    geometry manually in the frontend map.

    Field conventions:
    - polygon_field: comma-separated fallback
      paths, first non-empty match is used
    - plot_name_field: comma-separated field
      names, values joined with spaces
    - region_field / sub_region_field:
      comma-separated field names,
      non-empty values joined with ' - '
    """
    region = _build_joined_value(
        raw_data, form.region_field
    )
    sub_region = _build_joined_value(
        raw_data, form.sub_region_field
    )

    plot_name = _build_plot_name(raw_data, form.plot_name_field)

    result = {
        "polygon_wkt": None,
        "min_lat": None,
        "max_lat": None,
        "min_lon": None,
        "max_lon": None,
        "region": region,
        "sub_region": sub_region,
        "plot_name": plot_name,
    }

    polygon_fields = _split_csv_fields(form.polygon_field)
    if not polygon_fields:
        return result

    polygon_str = _extract_first_nonempty(raw_data, polygon_fields)
    if not polygon_str:
        logger.warning(
            "No polygon data found in fields: %s",
            polygon_fields,
        )
        return result

    coords = parse_odk_geoshape(polygon_str)
    if coords is None:
        logger.warning(
            "Failed to parse polygon from " "fields: %s",
            polygon_fields,
        )
        return result

    is_valid, error_msg = validate_polygon(coords)
    if not is_valid:
        logger.warning("Invalid polygon: %s", error_msg)
        return result

    bbox = compute_bbox(coords)
    result["polygon_wkt"] = coords_to_wkt(coords)
    result["min_lat"] = bbox["min_lat"]
    result["max_lat"] = bbox["max_lat"]
    result["min_lon"] = bbox["min_lon"]
    result["max_lon"] = bbox["max_lon"]

    return result
