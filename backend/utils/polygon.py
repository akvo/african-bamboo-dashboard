import logging
import math
import re
from shapely.geometry import (
    Polygon as ShapelyPolygon,
)
from shapely import wkt as shapely_wkt

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


def coords_to_odk_geoshape(coords):
    """Convert [(lon, lat), ...] to ODK geoshape format.

    Output: "lat lng 0 0; lat lng 0 0; ..."
    Altitude and accuracy are set to 0.
    """
    parts = []
    for lon, lat in coords:
        parts.append(f"{lat} {lon} 0 0")
    return "; ".join(parts)


def parse_wkt_polygon(wkt_string):
    """Parse WKT POLYGON to coordinate list.

    Returns list of (lon, lat) tuples, or None.
    """
    if not wkt_string or not wkt_string.strip():
        return None
    try:
        match = re.match(
            r"POLYGON\(\((.+)\)\)",
            wkt_string.strip(),
        )
        if not match:
            return None
        inner = match.group(1)
        pairs = [
            p.strip() for p in inner.split(",")
        ]
        coords = []
        for pair in pairs:
            parts = pair.split()
            if len(parts) < 2:
                return None
            lon = float(parts[0])
            lat = float(parts[1])
            coords.append((lon, lat))
        return coords
    except (ValueError, AttributeError):
        return None


def wkt_to_odk_geoshape(wkt_string):
    """Convert WKT POLYGON string to ODK geoshape.

    Returns empty string on invalid input.
    """
    coords = parse_wkt_polygon(wkt_string)
    if not coords:
        return ""
    return coords_to_odk_geoshape(coords)


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
    non-empty (value, field_name) tuple.
    Returns (None, None) if all empty."""
    for field in fields:
        val = raw_data.get(field)
        if val and str(val).strip():
            return str(val).strip(), field
    return None, None


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
    Returns None when no fields match."""
    fields = _split_csv_fields(plot_name_field)
    if not fields:
        return None
    parts = []
    for field in fields:
        val = raw_data.get(field)
        if val and str(val).strip():
            parts.append(str(val).strip())
    return " ".join(parts) if parts else None


def _polygons_overlap(wkt_a, wkt_b):
    """Check if two WKT polygons truly overlap.

    Returns True if they share area (not just
    an edge or corner). Returns False on error.
    """
    try:
        poly_a = shapely_wkt.loads(wkt_a)
        poly_b = shapely_wkt.loads(wkt_b)
        if not isinstance(
            poly_a, ShapelyPolygon
        ) or not isinstance(
            poly_b, ShapelyPolygon
        ):
            return False
        if not poly_a.is_valid or not poly_b.is_valid:
            return False
        if not poly_a.intersects(poly_b):
            return False
        # Touching edges/corners only -> no overlap
        return not poly_a.touches(poly_b)
    except Exception:
        return False


def find_overlapping_plots(
    plot_wkt, bbox, form_id, exclude_pk=None
):
    """Find plots that overlap with the given
    polygon within the same form.

    Phase 1: Fast DB bounding-box query.
    Phase 2: Shapely confirmation.
    Returns list of overlapping Plot objects.
    """
    from api.v1.v1_odk.models import Plot

    candidates = (
        Plot.objects.filter(
            form_id=form_id,
            min_lon__lte=bbox["max_lon"],
            max_lon__gte=bbox["min_lon"],
            min_lat__lte=bbox["max_lat"],
            max_lat__gte=bbox["min_lat"],
        )
        .exclude(polygon_wkt__isnull=True)
        .select_related("submission")
    )

    if exclude_pk is not None:
        candidates = candidates.exclude(
            pk=exclude_pk
        )

    overlapping = []
    for candidate in candidates:
        if _polygons_overlap(
            plot_wkt, candidate.polygon_wkt
        ):
            overlapping.append(candidate)
    return overlapping


def build_overlap_reason(overlapping_plots):
    """Build a reason string listing overlapping
    plots. Truncates to 500 chars if needed."""
    parts = []
    for p in overlapping_plots:
        inst = (
            p.submission.instance_name
            if p.submission
            else None
        ) or str(p.uuid)
        parts.append(
            f"{p.plot_name or inst} ({inst})"
        )
    msg = (
        "Polygon overlaps with: "
        + ", ".join(parts)
    )
    if len(msg) > 500:
        msg = msg[:497] + "..."
    return msg


def append_overlap_reason(
    existing_reason, new_plot_name, new_instance
):
    """Append overlap info to an existing reason.

    Skips if the instance already appears
    in the reason (duplicate prevention).
    Truncates to 500 chars.
    """
    if (
        existing_reason
        and new_instance in existing_reason
    ):
        return existing_reason

    overlap_msg = (
        f"Polygon overlaps with: "
        f"{new_plot_name} ({new_instance})"
    )

    if not existing_reason:
        return overlap_msg

    combined = f"{existing_reason}; {overlap_msg}"
    if len(combined) > 500:
        combined = combined[:497] + "..."
    return combined


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
        "polygon_source_field": None,
        "min_lat": None,
        "max_lat": None,
        "min_lon": None,
        "max_lon": None,
        "region": region,
        "sub_region": sub_region,
        "plot_name": plot_name,
        "flagged_for_review": None,
        "flagged_reason": None,
    }

    polygon_fields = _split_csv_fields(form.polygon_field)
    if not polygon_fields:
        return result

    polygon_str, source_field = (
        _extract_first_nonempty(
            raw_data, polygon_fields
        )
    )
    result["polygon_source_field"] = source_field
    if not polygon_str:
        logger.warning(
            "No polygon data found in fields: %s",
            polygon_fields,
        )
        result["flagged_for_review"] = True
        result["flagged_reason"] = (
            "No polygon data found in submission."
        )
        return result

    coords = parse_odk_geoshape(polygon_str)
    if coords is None:
        logger.warning(
            "Failed to parse polygon from "
            "fields: %s",
            polygon_fields,
        )
        result["flagged_for_review"] = True
        result["flagged_reason"] = (
            "Failed to parse polygon geometry."
        )
        return result

    is_valid, error_msg = validate_polygon(coords)
    if not is_valid:
        logger.warning(
            "Invalid polygon: %s", error_msg
        )
        result["flagged_for_review"] = True
        result["flagged_reason"] = error_msg
        return result

    bbox = compute_bbox(coords)
    result["polygon_wkt"] = coords_to_wkt(coords)
    result["min_lat"] = bbox["min_lat"]
    result["max_lat"] = bbox["max_lat"]
    result["min_lon"] = bbox["min_lon"]
    result["max_lon"] = bbox["max_lon"]

    return result
