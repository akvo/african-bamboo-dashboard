import math
import re

from api.v1.v1_odk.constants import (
    FlagSeverity,
    FlagType,
    WarningThresholds,
)

WHITESPACE_RE = re.compile(r"\s+")
EARTH_RADIUS_M = 6_371_000.0


def parse_odk_geoshape_full(input_str):
    """Parse ODK geoshape to list of dicts.

    Input:  "lat lng alt acc; lat lng alt acc; ..."
    Output: [{"lat", "lon", "alt", "acc"}, ...]
    Returns None if unparseable.
    """
    if not input_str or not input_str.strip():
        return None
    try:
        segments = input_str.strip().split(";")
        points = []
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            parts = WHITESPACE_RE.split(seg)
            if len(parts) < 2:
                return None
            point = {
                "lat": float(parts[0]),
                "lon": float(parts[1]),
                "alt": (
                    float(parts[2])
                    if len(parts) > 2
                    else 0.0
                ),
                "acc": (
                    float(parts[3])
                    if len(parts) > 3
                    else 0.0
                ),
            }
            points.append(point)
        if len(points) < 3:
            return None
        return points
    except (ValueError, IndexError):
        return None


def haversine_distance(lat1, lon1, lat2, lon2):
    """Distance in meters between two WGS84 points."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r)
        * math.cos(lat2_r)
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def coefficient_of_variation(values):
    """CV = std_dev / mean. Returns 0.0 if < 2."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    variance = sum(
        (v - mean) ** 2 for v in values
    ) / len(values)
    return math.sqrt(variance) / mean


def _make_flag(flag_type, note):
    """Build a warning flag dict."""
    return {
        "type": flag_type,
        "severity": FlagSeverity.WARNING,
        "note": note,
    }


def evaluate_warnings(raw_polygon_string, area_ha):
    """Run all 5 warning rules.

    Args:
        raw_polygon_string: ODK geoshape string
        area_ha: Pre-computed area from Plot.area_ha

    Returns list of {type, severity, note} dicts.
    """
    warnings = []

    points = parse_odk_geoshape_full(
        raw_polygon_string
    )
    if not points:
        return warnings

    # Remove closing point if it duplicates first
    if (
        len(points) > 1
        and points[0]["lat"] == points[-1]["lat"]
        and points[0]["lon"] == points[-1]["lon"]
    ):
        vertices = points[:-1]
    else:
        vertices = points

    num_vertices = len(vertices)

    # W1: GPS accuracy
    acc_values = [
        p["acc"] for p in vertices if p["acc"] > 0.0
    ]
    if acc_values:
        avg_acc = sum(acc_values) / len(acc_values)
        threshold = WarningThresholds.GPS_ACCURACY_MAX_M
        if avg_acc > threshold:
            warnings.append(
                _make_flag(
                    FlagType.GPS_ACCURACY_LOW,
                    f"Average GPS accuracy is "
                    f"{avg_acc:.1f}m "
                    f"(threshold: {threshold:.0f}m)",
                )
            )

    # W2: Point gap + collect distances for W3
    distances = []
    threshold = WarningThresholds.POINT_GAP_MAX_M
    for i in range(len(vertices) - 1):
        d = haversine_distance(
            vertices[i]["lat"],
            vertices[i]["lon"],
            vertices[i + 1]["lat"],
            vertices[i + 1]["lon"],
        )
        distances.append(d)
        if d > threshold:
            warnings.append(
                _make_flag(
                    FlagType.POINT_GAP_LARGE,
                    f"Gap of {d:.1f}m between "
                    f"points {i + 1}-{i + 2} "
                    f"(threshold: {threshold:.0f}m)",
                )
            )

    # W3: Uneven spacing (CV)
    if len(distances) >= 2:
        cv = coefficient_of_variation(distances)
        threshold = WarningThresholds.SPACING_CV_MAX
        if cv > threshold:
            warnings.append(
                _make_flag(
                    FlagType.POINT_SPACING_UNEVEN,
                    f"Uneven point spacing "
                    f"(CV={cv:.2f}, "
                    f"threshold: {threshold})",
                )
            )

    # W4: Area too large
    if (
        area_ha is not None
        and area_ha
        > WarningThresholds.AREA_MAX_HA
    ):
        warnings.append(
            _make_flag(
                FlagType.AREA_TOO_LARGE,
                f"Plot area is {area_ha:.1f}ha "
                f"(threshold: "
                f"{WarningThresholds.AREA_MAX_HA:.0f}"
                f"ha)",
            )
        )

    # W5: Too few vertices (rough boundary)
    if (
        WarningThresholds.VERTICES_ROUGH_MIN
        <= num_vertices
        <= WarningThresholds.VERTICES_ROUGH_MAX
    ):
        warnings.append(
            _make_flag(
                FlagType.VERTICES_TOO_FEW_ROUGH,
                f"Polygon has {num_vertices} "
                f"vertices (boundary may be "
                f"too rough)",
            )
        )

    return warnings
