import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import shapefile
from shapely import wkt as shapely_wkt
from shapely.geometry import mapping
from shapely.geometry.polygon import orient

from django.conf import settings
from api.v1.v1_odk.serializers import (
    build_option_lookup,
    resolve_value,
)
from utils import storage

logger = logging.getLogger(__name__)

EXPORT_FOLDER = "exports"

WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",'
    'DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",'
    "6378137.0,298.257223563]],"
    'PRIMEM["Greenwich",0.0],'
    'UNIT["Degree",'
    "0.0174532925199433]]"
)

APPROVAL_LABELS = {
    None: "pending",
    1: "approved",
    2: "rejected",
}

# Shapefile field definitions:
# (name, type, size, decimal)
SHP_FIELDS = [
    ("PLOT_ID", "C", 40, 0),
    ("PLOT_NAME", "C", 254, 0),
    ("ENUMERATOR", "C", 254, 0),
    ("REGION", "C", 254, 0),
    ("WOREDA", "C", 254, 0),
    ("VAL_STATUS", "C", 20, 0),
    ("NEEDS_RECL", "C", 10, 0),
    ("REJ_REASON", "C", 254, 0),
    ("CREATED_AT", "C", 30, 0),
    ("SUBMIT_AT", "C", 30, 0),
]


def _epoch_ms_to_iso(epoch_ms):
    """Convert epoch milliseconds to ISO 8601."""
    if epoch_ms is None:
        return ""
    try:
        dt = datetime.fromtimestamp(
            epoch_ms / 1000.0, tz=timezone.utc
        )
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError, OSError):
        return ""


def _close_wkt_rings(wkt_string):
    """Close any unclosed linear rings in a
    WKT POLYGON or MULTIPOLYGON string.

    Fixes 'Points of LinearRing do not form
    a closed linestring' errors.
    """

    def _close_ring(match):
        coords_str = match.group(1)
        coords = [
            c.strip()
            for c in coords_str.split(",")
        ]
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        return "(" + ", ".join(coords) + ")"

    return re.sub(
        r"\(([^()]+)\)", _close_ring, wkt_string
    )


def _parse_wkt(wkt_string):
    """Parse WKT string into a Shapely geometry,
    attempting to repair unclosed rings if the
    initial parse fails."""
    try:
        geom = shapely_wkt.loads(wkt_string)
    except Exception:
        fixed = _close_wkt_rings(wkt_string)
        geom = shapely_wkt.loads(fixed)
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom


def _resolve_field_spec(
    raw_data, field_spec, option_map, type_map
):
    """Resolve comma-separated field spec from
    raw submission data.

    Mirrors PlotSerializer._resolve_plot_fields
    but accepts pre-built lookup maps.
    """
    if not raw_data or not field_spec:
        return None
    fields = [
        f.strip()
        for f in field_spec.split(",")
        if f.strip()
    ]
    parts = []
    for field in fields:
        raw_val = raw_data.get(field)
        if raw_val is None:
            continue
        opts = option_map.get(field)
        if opts:
            resolved = resolve_value(
                raw_val, opts, type_map.get(field)
            )
        else:
            resolved = raw_val
        val = str(resolved).strip()
        if val:
            parts.append(val)
    return " - ".join(parts) if parts else None


def resolve_plot_attributes(
    plot, option_map, type_map
):
    """Build attribute dict for a single plot.

    Returns a dict keyed by shapefile-safe
    field names (max 10 chars).
    """
    raw = {}
    approval = None
    submit_time = None
    instance_name = None

    if plot.submission:
        raw = plot.submission.raw_data or {}
        approval = plot.submission.approval_status
        submit_time = (
            plot.submission.submission_time
        )
        instance_name = (
            plot.submission.instance_name
        )

    form = plot.form
    region_spec = form.region_field or "region"
    woreda_spec = (
        form.sub_region_field or "woreda"
    )

    plot_name = plot.plot_name or instance_name

    flagged = plot.flagged_for_review
    if flagged is True:
        needs_recl = "Yes"
    elif flagged is False:
        needs_recl = "No"
    else:
        needs_recl = ""

    return {
        "PLOT_ID": str(plot.uuid),
        "PLOT_NAME": (plot_name or "")[:254],
        "ENUMERATOR": (
            _resolve_field_spec(
                raw,
                "enumerator_id",
                option_map,
                type_map,
            )
            or ""
        )[:254],
        "REGION": (
            _resolve_field_spec(
                raw,
                region_spec,
                option_map,
                type_map,
            )
            or ""
        )[:254],
        "WOREDA": (
            _resolve_field_spec(
                raw,
                woreda_spec,
                option_map,
                type_map,
            )
            or ""
        )[:254],
        "VAL_STATUS": APPROVAL_LABELS.get(
            approval, "pending"
        ),
        "NEEDS_RECL": needs_recl,
        "REJ_REASON": (
            plot.flagged_reason or ""
        )[:254],
        "CREATED_AT": _epoch_ms_to_iso(
            plot.created_at
        ),
        "SUBMIT_AT": _epoch_ms_to_iso(
            submit_time
        ),
    }


def _wkt_to_pyshp_parts(wkt_string):
    """Convert WKT POLYGON/MULTIPOLYGON to pyshp
    parts.

    Returns list of parts (list of [lon, lat])
    or None if invalid.
    """
    try:
        geom = _parse_wkt(wkt_string)

        if geom.geom_type == "MultiPolygon":
            polygons = geom.geoms
        elif geom.geom_type == "Polygon":
            polygons = [geom]
        else:
            logger.warning(
                "Unsupported geometry type: %s",
                geom.geom_type,
            )
            return None

        parts = []
        for poly in polygons:
            # Shapefile requires CW exterior,
            # CCW interior (sign=-1.0)
            poly = orient(poly, sign=-1.0)
            parts.append(
                [
                    [c[0], c[1]]
                    for c in poly.exterior.coords
                ]
            )
            for interior in poly.interiors:
                parts.append(
                    [
                        [c[0], c[1]]
                        for c in interior.coords
                    ]
                )
        return parts
    except Exception as e:
        logger.warning(
            "Failed to parse WKT: %s", e
        )
        return None


def generate_shapefile(
    queryset, form, filename
):
    """Generate a zipped Shapefile from a
    Plot queryset.

    Files are written to a temp directory then
    uploaded to persistent storage via
    utils.storage.

    Returns (stored_file_path, record_count).
    """
    option_map, type_map = build_option_lookup(
        form
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        shp_path = os.path.join(
            tmpdir, filename
        )
        w = shapefile.Writer(
            shp_path, encoding="utf-8"
        )
        w.autoBalance = 1

        for (
            name,
            ftype,
            size,
            decimal,
        ) in SHP_FIELDS:
            w.field(name, ftype, size, decimal)

        count = 0
        qs = queryset.select_related(
            "submission", "form"
        ).iterator()
        for plot in qs:
            parts = _wkt_to_pyshp_parts(
                plot.polygon_wkt
            )
            if parts is None:
                logger.warning(
                    "Skipping plot %s: "
                    "invalid geometry",
                    plot.uuid,
                )
                continue

            attrs = resolve_plot_attributes(
                plot, option_map, type_map
            )
            w.poly(parts)
            w.record(
                attrs["PLOT_ID"],
                attrs["PLOT_NAME"],
                attrs["ENUMERATOR"],
                attrs["REGION"],
                attrs["WOREDA"],
                attrs["VAL_STATUS"],
                attrs["NEEDS_RECL"],
                attrs["REJ_REASON"],
                attrs["CREATED_AT"],
                attrs["SUBMIT_AT"],
            )
            count += 1

        w.close()

        # Write .prj file
        prj_path = shp_path + ".prj"
        if not os.path.exists(prj_path):
            with open(
                prj_path, "w"
            ) as prj_file:
                prj_file.write(WGS84_PRJ)

        # Write .cpg file
        cpg_path = shp_path + ".cpg"
        with open(
            cpg_path, "w"
        ) as cpg_file:
            cpg_file.write("UTF-8")

        # Zip all shapefile components
        zip_name = f"{filename}.zip"
        zip_path = os.path.join(
            tmpdir, zip_name
        )
        exts = [
            "shp",
            "shx",
            "dbf",
            "prj",
            "cpg",
        ]
        with ZipFile(zip_path, "w") as zf:
            for ext in exts:
                fpath = f"{shp_path}.{ext}"
                if os.path.exists(fpath):
                    zf.write(
                        fpath,
                        arcname=(
                            f"{filename}.{ext}"
                        ),
                    )

        stored = storage.upload(
            zip_path,
            folder=EXPORT_FOLDER,
            filename=zip_name,
        )

    return stored, count


def generate_geojson(
    queryset, form, filename
):
    """Generate a GeoJSON file from a
    Plot queryset.

    The file is written to a temp directory
    then uploaded to persistent storage via
    utils.storage.

    Returns (stored_file_path, record_count).
    """
    option_map, type_map = build_option_lookup(
        form
    )

    features = []
    qs = queryset.select_related(
        "submission", "form"
    ).iterator()
    for plot in qs:
        try:
            geom = _parse_wkt(plot.polygon_wkt)
        except Exception as e:
            logger.warning(
                "Skipping plot %s: %s",
                plot.uuid,
                e,
            )
            continue

        attrs = resolve_plot_attributes(
            plot, option_map, type_map
        )
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(geom),
                "properties": attrs,
            }
        )

    collection = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {
                "name": (
                    "urn:ogc:def:crs:"
                    "EPSG::4326"
                )
            },
        },
        "features": features,
    }

    geojson_name = f"{filename}.geojson"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = os.path.join(
            tmpdir, geojson_name
        )
        with open(
            tmp_path, "w", encoding="utf-8"
        ) as f:
            json.dump(collection, f)

        stored = storage.upload(
            tmp_path,
            folder=EXPORT_FOLDER,
            filename=geojson_name,
        )

    return stored, len(features)


def cleanup_old_exports(max_age_hours=24):
    """Delete export files older than
    max_age_hours."""
    export_dir = (
        Path(settings.STORAGE_PATH) / EXPORT_FOLDER
    )
    if not export_dir.exists():
        return
    now = time.time()
    max_age_secs = max_age_hours * 3600
    for fpath in export_dir.iterdir():
        if fpath.is_file():
            age = now - fpath.stat().st_mtime
            if age > max_age_secs:
                rel = (
                    f"{EXPORT_FOLDER}/"
                    f"{fpath.name}"
                )
                try:
                    storage.delete(rel)
                except OSError:
                    pass
