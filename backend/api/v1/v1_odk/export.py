import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape
from zipfile import ZipFile

import shapefile
from shapely import wkt as shapely_wkt
from shapely.geometry import mapping
from shapely.geometry.polygon import orient

from openpyxl import Workbook

from django.conf import settings
from api.v1.v1_odk.models import (
    FieldMapping,
    FarmerFieldMapping,
    FormQuestion,
)
from api.v1.v1_odk.serializers import (
    build_option_lookup,
    resolve_value,
)
from api.v1.v1_odk.constants import (
    PREFIX_FARM_ID,
    PREFIX_PLOT_ID,
)
from api.v1.v1_users.models import SystemUser
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
    ("FARMER_ID", "C", 254, 0),
    ("ENUMERATOR", "C", 254, 0),
    ("REGION", "C", 254, 0),
    ("SUB_REGION", "C", 254, 0),
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

    if plot.submission:
        raw = plot.submission.raw_data or {}
        approval = plot.submission.approval_status
        submit_time = (
            plot.submission.submission_time
        )

    form = plot.form
    region_spec = form.region_field or "region"
    sub_region_spec = (
        form.sub_region_field or "sub_region"
    )

    flagged = plot.flagged_for_review
    if flagged is True:
        needs_recl = "Yes"
    elif flagged is False:
        needs_recl = "No"
    else:
        needs_recl = ""

    return {
        "PLOT_ID": (
            f"{PREFIX_PLOT_ID}"
            f"{plot.submission.kobo_id}"
            if plot.submission
            else ""
        ),
        "FARMER_ID": (
            f"{PREFIX_FARM_ID}{plot.farmer.uid}"
            if plot.farmer
            else ""
        ),
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
        "SUB_REGION": (
            _resolve_field_spec(
                raw,
                sub_region_spec,
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


def _wkt_to_kml(wkt_string, name="Plot"):
    """Convert WKT polygon to a KML document string.

    Returns KML XML string or empty string on
    failure.
    """
    if not wkt_string:
        return ""
    try:
        geom = _parse_wkt(wkt_string)
        if geom.geom_type == "MultiPolygon":
            polygons = list(geom.geoms)
        elif geom.geom_type == "Polygon":
            polygons = [geom]
        else:
            return ""

        safe_name = xml_escape(str(name))
        placemarks = []
        for i, poly in enumerate(polygons):
            coords = " ".join(
                f"{c[0]},{c[1]},0"
                for c in poly.exterior.coords
            )
            pm_name = (
                safe_name
                if len(polygons) == 1
                else f"{safe_name} ({i + 1})"
            )
            placemarks.append(
                f"<Placemark>"
                f"<name>{pm_name}</name>"
                f"<Polygon>"
                f"<outerBoundaryIs>"
                f"<LinearRing>"
                f"<coordinates>"
                f"{coords}"
                f"</coordinates>"
                f"</LinearRing>"
                f"</outerBoundaryIs>"
                f"</Polygon>"
                f"</Placemark>"
            )

        return (
            '<?xml version="1.0" '
            'encoding="UTF-8"?>'
            '<kml xmlns='
            '"http://www.opengis.net/kml/2.2">'
            "<Document>"
            f"<name>{safe_name}</name>"
            + "".join(placemarks)
            + "</Document></kml>"
        )
    except Exception:
        return ""


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
                attrs["FARMER_ID"],
                attrs["ENUMERATOR"],
                attrs["REGION"],
                attrs["SUB_REGION"],
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


WHITESPACE_RE = re.compile(r"\s+")


def _extract_avg_altitude(raw_data, form):
    """Extract average altitude from the raw ODK
    geoshape string in raw_data.

    ODK format: "lat lng alt acc; ..."
    Returns rounded float or empty string.
    """
    polygon_field = form.polygon_field or ""
    fields = [
        f.strip()
        for f in polygon_field.split(",")
        if f.strip()
    ]
    geoshape_str = None
    for field in fields:
        val = raw_data.get(field)
        if val:
            geoshape_str = val
            break
    if not geoshape_str:
        return ""
    try:
        segments = geoshape_str.strip().split(";")
        altitudes = []
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            parts = WHITESPACE_RE.split(seg)
            if len(parts) >= 3:
                alt = float(parts[2])
                altitudes.append(alt)
        if altitudes:
            avg = sum(altitudes) / len(altitudes)
            return round(avg, 3)
    except (ValueError, IndexError):
        pass
    return ""


PLOT_TABLE_HEADERS = [
    "Plot ID",
    "Farmer ID",
    "Title Deed First Page",
    "Title Deed Second Page",
    "Latitude",
    "Longitude",
    "Altitude",
    "Entire Area Polygon",
    "Plantation Polygon",
]


def _get_kobo_base_url():
    """Get the Kobo base URL from the first
    SystemUser that has one configured."""
    return (
        SystemUser.objects.filter(
            kobo_url__isnull=False,
        )
        .exclude(kobo_url="")
        .values_list("kobo_url", flat=True)
        .first()
    ) or ""


def _resolve_attachment_url(
    raw_data, field_name, kobo_base_url
):
    """Resolve Kobo attachment URL for a title
    deed field.

    1. Get filename from raw_data[field_name]
    2. Match by media_file_basename in _attachments
    3. Build: kobo_url/media/original?media_file=
       <url-encoded attachment.filename>
    """
    if not field_name:
        return ""
    file_val = raw_data.get(field_name)
    if not file_val:
        return ""
    attachments = raw_data.get(
        "_attachments", []
    )
    for att in attachments:
        basename = att.get(
            "media_file_basename", ""
        )
        if basename == file_val:
            att_filename = att.get("filename", "")
            if att_filename and kobo_base_url:
                encoded = quote(
                    att_filename, safe=""
                )
                return (
                    f"{kobo_base_url}"
                    f"/media/original"
                    f"?media_file="
                    f"{encoded}"
                )
    return ""


def _build_farmer_headers(form):
    """Build dynamic Farmer table headers from
    FarmerFieldMapping: unique_fields first,
    then values_fields (deduped).

    Returns (headers, all_fields) where headers
    starts with 'FarmerID(primary key)' followed
    by FormQuestion.label for each field.
    all_fields is the ordered list of raw_data
    keys matching the headers.
    """
    mapping = FarmerFieldMapping.objects.filter(
        form=form
    ).first()
    if not mapping:
        return ["FarmerID(primary key)"], []

    unique_fields = [
        f.strip()
        for f in mapping.unique_fields.split(",")
        if f.strip()
    ]
    values_fields = [
        f.strip()
        for f in mapping.values_fields.split(",")
        if f.strip()
    ]

    # Combine: unique_fields first, then
    # values_fields (skip duplicates)
    seen = set(unique_fields)
    all_fields = list(unique_fields)
    for f in values_fields:
        if f not in seen:
            all_fields.append(f)
            seen.add(f)

    # Build question_name → label lookup
    q_labels = dict(
        FormQuestion.objects.filter(
            form=form,
            name__in=all_fields,
        ).values_list("name", "label")
    )

    headers = ["FarmerID(primary key)"]
    for field in all_fields:
        headers.append(
            q_labels.get(field, field)
        )

    return headers, all_fields


def generate_xlsx(queryset, form, filename):
    """Generate an XLSX file with two sheets:
    'Farmer table' and 'Plot Table'.

    Matches the Afforestation Monitoring Database
    column format.

    Returns (stored_file_path, record_count).
    """
    storage_key = quote(
        settings.STORAGE_SECRET, safe=""
    )
    web_domain = settings.WEBDOMAIN.rstrip("/")
    kobo_base_url = _get_kobo_base_url()

    # Build dynamic farmer headers
    farmer_headers, farmer_fields = (
        _build_farmer_headers(form)
    )

    # Resolve title deed field names
    deed_map = {}
    deed_qs = FieldMapping.objects.filter(
        form=form,
        field__name__in=[
            "title_deed_1",
            "title_deed_2",
        ],
    ).select_related("field", "form_question")
    for m in deed_qs:
        deed_map[m.field.name] = (
            m.form_question.name
        )
    td1_key = deed_map.get("title_deed_1")
    td2_key = deed_map.get("title_deed_2")

    wb = Workbook()

    # --- Farmer table sheet ---
    ws_farmer = wb.active
    ws_farmer.title = "Farmer table"
    ws_farmer.append(farmer_headers)

    seen_farmers = {}
    plot_rows = []

    qs = queryset.select_related(
        "submission", "farmer", "form"
    )

    for plot in qs.iterator():
        sub = plot.submission
        raw = sub.raw_data or {} if sub else {}
        farmer = plot.farmer

        farmer_id = ""
        if farmer:
            farmer_id = f"AB{farmer.uid}"
            if farmer.uid not in seen_farmers:
                seen_farmers[farmer.uid] = (
                    farmer.values or {}
                )

        # Title deed URLs
        td1_url = _resolve_attachment_url(
            raw, td1_key, kobo_base_url
        )
        td2_url = _resolve_attachment_url(
            raw, td2_key, kobo_base_url
        )

        # Centroid from polygon
        centroid_lat = ""
        centroid_lon = ""
        if plot.polygon_wkt:
            try:
                geom = _parse_wkt(
                    plot.polygon_wkt
                )
                c = geom.centroid
                centroid_lat = round(c.y, 6)
                centroid_lon = round(c.x, 6)
            except Exception:
                pass

        plot_id = (
            f"{PREFIX_PLOT_ID}{sub.kobo_id}" if sub else ""
        )

        altitude = _extract_avg_altitude(
            raw, form
        )

        plot_rows.append([
            plot_id,
            farmer_id,
            td1_url,
            td2_url,
            centroid_lat,
            centroid_lon,
            altitude,
            (
                f"{web_domain}"
                f"/api/v1/odk/plots"
                f"/{plot.uuid}/kml"
                f"/?key={storage_key}"
                if plot.polygon_wkt
                else ""
            ),
            "",  # Plantation Polygon
        ])

    # Write farmer rows sorted by uid
    for uid in sorted(
        seen_farmers.keys(),
        key=lambda u: int(u),
    ):
        vals = seen_farmers[uid]
        row = [f"{PREFIX_FARM_ID}{uid}"]
        for field in farmer_fields:
            row.append(vals.get(field) or "")
        ws_farmer.append(row)

    # --- Plot Table sheet ---
    ws_plot = wb.create_sheet(title="Plot Table")
    ws_plot.append(PLOT_TABLE_HEADERS)
    for row in plot_rows:
        ws_plot.append(row)

    # Write to temp file and upload
    xlsx_name = f"{filename}.xlsx"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = os.path.join(
            tmpdir, xlsx_name
        )
        wb.save(tmp_path)
        stored = storage.upload(
            tmp_path,
            folder=EXPORT_FOLDER,
            filename=xlsx_name,
        )

    return stored, len(plot_rows)


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
