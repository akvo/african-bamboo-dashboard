import math

from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.ops import transform


def calculate_area_ha(polygon_string):
    """Calculate area in hectares from ODK polygon.

    Format: "lat lng alt acc;lat lng alt acc;..."
    Returns area rounded to 2 decimals, or None.
    """
    if not polygon_string:
        return None

    try:
        points = []
        raw = polygon_string.strip().rstrip(";")
        segments = raw.split(";")
        for seg in segments:
            parts = seg.strip().split()
            if len(parts) < 2:
                continue
            lat = float(parts[0])
            lng = float(parts[1])
            points.append((lng, lat))

        if len(points) < 3:
            return None

        poly = Polygon(points)
        if not poly.is_valid or poly.is_empty:
            return None

        # Find UTM zone from centroid
        centroid = poly.centroid
        lon = centroid.x
        lat = centroid.y
        utm_zone = int((lon + 180) / 6) + 1
        hemisphere = (
            "north" if lat >= 0 else "south"
        )
        epsg = (
            32600 + utm_zone
            if hemisphere == "north"
            else 32700 + utm_zone
        )

        transformer = Transformer.from_crs(
            "EPSG:4326",
            f"EPSG:{epsg}",
            always_xy=True,
        )
        projected = transform(
            transformer.transform, poly
        )
        area_m2 = projected.area

        if math.isnan(area_m2) or math.isinf(area_m2):
            return None

        return round(area_m2 / 10000, 2)

    except (ValueError, TypeError, Exception):
        return None
