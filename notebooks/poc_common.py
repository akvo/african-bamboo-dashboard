"""Shared loader for the V25–V27 geospatial POC notebooks.

The notebooks read the ignored real Kobo export in ``notebooks/data`` through
the production polygon helpers. Raw identifiers, names, and phone numbers are
never returned; submission identifiers are one-way hashes.

This module performs no database writes and no network access.
"""

import csv
import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pyproj import CRS, Transformer
from shapely.geometry import Polygon
from shapely.ops import transform as shapely_transform

__all__ = [
    "find_repo_root",
    "hashed_id",
    "load_backend_helpers",
    "load_records",
    "utm_crs_for",
    "dataset_utm_crs",
    "utm_transformer",
    "project_polygon",
    "poc_paths",
    "write_public_output",
    "synthetic_square",
    "public_dem_url",
    "public_worldcover_url",
    "preview_map",
]

# Public, well-known locations used only by the synthetic "what a flagged plot
# looks like" demos. They are deliberately far from the real collection area,
# so a committed map preview discloses nothing about where African Bamboo
# actually works. Every one is a named landmark, not a farm.
# Each coordinate was chosen by scanning the public source for a spot that
# genuinely trips its rule, so every demo shows the flagged branch rather than
# a near miss.
DEMO_LOCATIONS = {
    "steep_slope": (38.5324, 13.3912, "Simien escarpment, Amhara"),
    "high_elevation": (38.3750, 13.2350, "Simien massif, Amhara"),
    "trunk_road": (39.5300, 9.6800, "Trunk road near Debre Birhan"),
    "forest": (36.0503, 7.6497, "Kafa-Sheka forest belt, SNNPR"),
}

# Keys that must never reach the tracked outputs directory, because they
# localise a plot even without coordinates. `nearest_osm_id` pins a plot to a
# ring around a specific mappable OpenStreetMap way; bounds and geometry are
# self-evidently locating.
LOCATING_KEYS = frozenset(
    {
        "nearest_osm_id",
        "polygon",
        "polygon_wkt",
        "coords",
        "bounds",
        "bbox",
        "latitude",
        "longitude",
    }
)

CSV_DELIMITER = ";"


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Return the repository root that contains the backend Django app."""
    origin = start or Path.cwd()
    for candidate in [origin, *origin.parents]:
        if (candidate / "backend/api/v1/v1_odk/models.py").exists():
            return candidate
    raise RuntimeError("Run this notebook from inside the repository")


def hashed_id(value: Any, prefix: str = "poc") -> str:
    """Return a deterministic one-way identifier for POC output."""
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def poc_paths(version: str) -> Dict[str, Path]:
    """Return the repository paths used by a POC notebook."""
    repo_root = find_repo_root()
    data_dir = repo_root / "notebooks/data"
    output_dir = data_dir / f"{version}_poc_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return {
        "repo_root": repo_root,
        "data_dir": data_dir,
        "output_dir": output_dir,
        "csv": next(data_dir.glob("*_ab_realdata.csv")),
        "v24_output_dir": data_dir / "v24_poc_output",
    }


def _assert_not_locating(value: Any, path: str = "") -> None:
    """Raise if a payload carries a key that could localise a plot."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in LOCATING_KEYS:
                raise ValueError(
                    f"Refusing to write locating key '{path}{key}' to the "
                    "tracked outputs directory"
                )
            _assert_not_locating(item, f"{path}{key}.")
    elif isinstance(value, list):
        for item in value:
            _assert_not_locating(item, path)


def write_public_output(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Write a reviewable POC summary to the tracked ``notebooks/outputs``.

    Unlike the per-POC directories under ``notebooks/data``, this location is
    committed, so only aggregate and non-locating content belongs here. The
    payload is screened for locating keys before it is written; per-plot rows,
    georeferenced rasters, and source caches stay in the ignored directory.

    Args:
        name: Output file name, e.g. ``v25_elevation_summary.json``.
        payload: JSON-serialisable summary content.

    Returns:
        A small dict describing what was written.

    Raises:
        ValueError: If the payload contains a locating key.
    """
    _assert_not_locating(payload)
    outputs_dir = find_repo_root() / "notebooks/outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    destination = outputs_dir / name
    destination.write_text(json.dumps(payload, indent=2) + "\n")
    return {
        "file": f"notebooks/outputs/{name}",
        "tracked_by_git": True,
        "contains_per_plot_rows": False,
        "screened_for_locating_keys": True,
    }


def synthetic_square(
    longitude: float, latitude: float, side_m: float = 25.0
) -> Polygon:
    """Return a square WGS84 polygon of ``side_m`` centred on a coordinate.

    Used to hand-draw an example plot that trips a rule. The default 25 m side
    is 625 m2, close to the median real plot, so the demo carries the same
    resolution caveats the real data does.
    """
    metre_lat = 1.0 / 110574.0
    metre_lon = 1.0 / (111320.0 * math.cos(math.radians(latitude)))
    half_lat = side_m / 2.0 * metre_lat
    half_lon = side_m / 2.0 * metre_lon
    return Polygon(
        [
            (longitude - half_lon, latitude - half_lat),
            (longitude + half_lon, latitude - half_lat),
            (longitude + half_lon, latitude + half_lat),
            (longitude - half_lon, latitude + half_lat),
            (longitude - half_lon, latitude - half_lat),
        ]
    )


def public_dem_url(longitude: float, latitude: float) -> str:
    """Return the keyless Copernicus GLO-30 COG covering a coordinate.

    The AWS Open Data mirror needs no API key, so the synthetic demos work in
    any checkout. Production still reads the versioned local asset package.
    """
    lat_tag = f"{'N' if latitude >= 0 else 'S'}{abs(int(latitude)):02d}_00"
    lon_tag = f"{'E' if longitude >= 0 else 'W'}{abs(int(longitude)):03d}_00"
    name = f"Copernicus_DSM_COG_10_{lat_tag}_{lon_tag}_DEM"
    return (
        f"/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/"
        f"{name}/{name}.tif"
    )


def public_worldcover_url(longitude: float, latitude: float) -> str:
    """Return the ESA WorldCover 2021 v200 COG covering a coordinate."""
    lat_corner = math.floor(latitude / 3) * 3
    lon_corner = math.floor(longitude / 3) * 3
    hemisphere = "N" if lat_corner >= 0 else "S"
    meridian = "E" if lon_corner >= 0 else "W"
    tile = (
        f"{hemisphere}{abs(lat_corner):02d}"
        f"{meridian}{abs(lon_corner):03d}"
    )
    return (
        "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
        f"v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
    )


def preview_map(
    polygon: Polygon,
    flagged: bool,
    title: str,
    rows: Dict[str, Any],
    lines: Optional[List[Tuple[str, Any]]] = None,
    zoom: int = 17,
):
    """Render a synthetic plot on a Leaflet basemap for visual review.

    Args:
        polygon: The synthetic plot in WGS84.
        flagged: Whether the rule fired; drives red/green styling.
        title: Short caption shown above the map.
        rows: Label to value pairs listed in the polygon popup.
        lines: Optional ``(label, shapely LineString)`` overlays, e.g. roads.
        zoom: Initial zoom level.

    Returns:
        A ``folium.Map``. Jupyter renders it inline.

    Raises:
        ImportError: If folium is not installed.
    """
    try:
        import folium
    except ImportError as error:
        raise ImportError(
            "folium is required for the map preview. Install the notebook "
            "dependencies with: pip install -r notebooks/requirements.txt"
        ) from error
    except ValueError as error:
        # folium imports pandas. A pandas built against numpy 1.x raises
        # "numpy.dtype size changed" under numpy 2.x, which is an environment
        # problem rather than a notebook one. Everything above this cell has
        # already run, so surface the fix instead of a binary-layout trace.
        raise RuntimeError(
            "folium could not import because this environment mixes numpy 2 "
            "with a pandas built for numpy 1. Fix it with "
            "'pip install -U \"pandas>=2.2.2\"', or run the notebook against "
            "notebooks/requirements.txt in a clean environment. Only the map "
            "preview is affected; the measurements above are unaffected."
        ) from error

    colour = "#d63b2d" if flagged else "#2f9e44"
    centroid = polygon.centroid
    canvas = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=zoom,
        tiles="OpenStreetMap",
    )
    popup = "<br>".join(
        f"<b>{label}</b>: {value}" for label, value in rows.items()
    )
    folium.Polygon(
        locations=[(y, x) for x, y in polygon.exterior.coords],
        color=colour,
        weight=3,
        fill=True,
        fill_opacity=0.35,
        popup=folium.Popup(popup, max_width=320),
        tooltip=title,
    ).add_to(canvas)
    for label, line in lines or []:
        folium.PolyLine(
            locations=[(y, x) for x, y in line.coords],
            color="#e8a33d",
            weight=4,
            opacity=0.9,
            tooltip=label,
        ).add_to(canvas)
    caption = (
        f"{title} &mdash; {'FLAGGED' if flagged else 'clean'}. "
        "Synthetic example at a public landmark; not a real plot."
    )
    canvas.get_root().html.add_child(
        folium.Element(
            f"<div style='font:14px sans-serif;padding:6px 0;"
            f"color:{colour}'><b>{caption}</b></div>"
        )
    )
    return canvas


def load_backend_helpers(repo_root: Path):
    """Import the production polygon helpers without Django setup."""
    backend_dir = repo_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from api.v1.v1_odk.utils.area_calc import calculate_area_ha
    from utils.polygon import (
        compute_bbox,
        coords_to_wkt,
        parse_odk_geoshape,
        validate_polygon,
    )

    return {
        "calculate_area_ha": calculate_area_ha,
        "compute_bbox": compute_bbox,
        "coords_to_wkt": coords_to_wkt,
        "parse_odk_geoshape": parse_odk_geoshape,
        "validate_polygon": validate_polygon,
    }


def _dedupe(coords: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Drop repeated consecutive vertices.

    ODK captures repeated GPS fixes at the same position. The duplicates do
    not change the geometry but make GEOS emit spurious NaN warnings during
    distance measurement, so they are removed before building the polygon.
    """
    cleaned = [coords[0]]
    for point in coords[1:]:
        if point != cleaned[-1]:
            cleaned.append(point)
    if cleaned[0] != cleaned[-1]:
        cleaned.append(cleaned[0])
    return cleaned


def _iso_to_epoch_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(parsed.timestamp() * 1000)


def load_records(
    csv_path: Path, helpers: Dict[str, Any]
) -> Tuple[List[Dict], List[Dict]]:
    """Return (all records, valid records) with hashed identifiers only.

    Args:
        csv_path: Ignored real Kobo CSV export.
        helpers: Result of :func:`load_backend_helpers`.

    Returns:
        Tuple of every parsed record and the subset with valid geometry.
    """
    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream, delimiter=CSV_DELIMITER)
        header = next(reader)
        rows = list(reader)

    def first_column(name: str) -> int:
        return next(i for i, value in enumerate(header) if value == name)

    column = {
        "polygon": first_column("Auto Boundary Capture"),
        "kobo_id": first_column("_id"),
        "uuid": first_column("_uuid"),
        "submission_time": first_column("_submission_time"),
    }

    records: List[Dict] = []
    for row_number, row in enumerate(rows, start=1):
        polygon_string = row[column["polygon"]].strip()
        coords = helpers["parse_odk_geoshape"](polygon_string)
        if coords:
            valid, message = helpers["validate_polygon"](coords)
        else:
            valid, message = False, "unparseable"
        real_uuid = row[column["uuid"]].strip()
        records.append(
            {
                "plot_ref": hashed_id(real_uuid, "plot"),
                "submission_uuid": hashed_id(real_uuid, "submission"),
                "kobo_id": hashed_id(row[column["kobo_id"]], "kobo"),
                "submission_time": _iso_to_epoch_ms(
                    row[column["submission_time"]]
                ),
                "polygon_string": polygon_string,
                "coords": coords,
                "polygon_wkt": (
                    helpers["coords_to_wkt"](coords) if valid else None
                ),
                "polygon": Polygon(_dedupe(coords)) if valid else None,
                "area_ha": (
                    helpers["calculate_area_ha"](polygon_string)
                    if valid
                    else None
                ),
                "is_valid": valid,
                "validation_message": message,
                "raw_data": {
                    "auto_boundary_capture": polygon_string,
                    "region": "POC region",
                    "sub_region": "POC sub-region",
                    "plot_name": f"POC plot {row_number:03d}",
                },
            }
        )

    valid_records = [record for record in records if record["is_valid"]]
    return records, valid_records


def utm_crs_for(longitude: float, latitude: float) -> CRS:
    """Return the WGS84 UTM CRS covering the supplied coordinate."""
    zone = int((longitude + 180) // 6) + 1
    epsg = (32600 if latitude >= 0 else 32700) + zone
    return CRS.from_epsg(epsg)


def dataset_utm_crs(records: List[Dict]) -> CRS:
    """Return one UTM CRS covering every valid record in the dataset.

    The collection area spans well under one UTM zone, so a single projected
    CRS keeps pixel-intersection areas comparable across plots and avoids
    rebuilding a transformer per geometry.
    """
    polygons = [r["polygon"] for r in records if r.get("polygon")]
    if not polygons:
        raise ValueError("No valid polygons to derive a UTM zone from")
    lons = [p.centroid.x for p in polygons]
    lats = [p.centroid.y for p in polygons]
    return utm_crs_for(sum(lons) / len(lons), sum(lats) / len(lats))


def utm_transformer(target_crs: CRS) -> Transformer:
    """Return a reusable WGS84 to ``target_crs`` transformer."""
    return Transformer.from_crs("EPSG:4326", target_crs, always_xy=True)


def project_polygon(geometry, target_crs_or_transformer):
    """Project a WGS84 geometry using a CRS or a prepared transformer."""
    transformer = target_crs_or_transformer
    if isinstance(transformer, CRS):
        transformer = utm_transformer(transformer)
    return shapely_transform(transformer.transform, geometry)
