# Implementation: Async Export Plots to Shapefile / GeoJSON

## Context

The "Export data" button exists in the dashboard UI but had no functionality. African Bamboo needs to export cleaned/validated parcel geometries and metadata as GIS-compatible files (Shapefile and GeoJSON) for QGIS/ArcGIS and carbon MRV workflows. Exports use the edited geometry from DCU (`polygon_wkt`), not raw Kobo data, and respect current UI filters.

The export runs **asynchronously via the Django-Q2 worker**, so large exports don't block the HTTP request. The frontend polls for completion and auto-triggers the download.

## Architecture: Async Export Flow

```
1. User clicks "Export data"
2. POST /api/v1/odk/plots/export/  ->  creates Job (pending), dispatches async_task  ->  returns {id, status}
3. Worker picks up task  ->  generates file in tmp/exports/  ->  updates Job (done)
4. Frontend polls GET /api/v1/jobs/{id}/  every 2s
5. When status=done  ->  auto-download via GET /api/v1/jobs/{id}/download/
```

Both `backend` and `worker` services share the same Docker volume (`./backend:/app`). Export files are written to `BASE_DIR/tmp/exports/` within the shared volume.

## Apps & Endpoints

### v1_jobs app (`backend/api/v1/v1_jobs/`)

Reusable async job tracking app (following Eswatini Droughtmap Hub pattern):

- **constants.py** — `JobTypes` (export_shapefile, export_geojson), `JobStatus` (pending, on_progress, failed, done)
- **models.py** — `Jobs` model with task_id, type, status, attempt, result, info (JSON), created, available
- **serializers.py** — `JobSerializer`
- **views.py** — `GET /api/v1/jobs/{id}/` (status), `GET /api/v1/jobs/{id}/download/` (file download)

### Export endpoint (on PlotViewSet)

- `POST /api/v1/odk/plots/export/` — Initiate export
  - Body: `{ form_id, format ("shp"|"geojson"), status, search }`
  - Returns `201` with job object

### Export utilities (`backend/api/v1/v1_odk/export.py`)

- `generate_shapefile()` — Creates zipped .shp/.shx/.dbf/.prj via pyshp
- `generate_geojson()` — Creates GeoJSON FeatureCollection
- `resolve_plot_attributes()` — Builds attribute dict with Shapefile-safe field names
- `cleanup_old_exports()` — Removes files older than 24h

### Export task (`backend/api/v1/v1_odk/tasks.py`)

- `generate_export_file(job_id)` — Async task dispatched via Django-Q2

## Exported Attributes

| Shapefile Field | Source | Type |
|---|---|---|
| PLOT_ID | plot.uuid | C(40) |
| PLOT_NAME | plot.plot_name or submission.instance_name | C(254) |
| ENUMERATOR | resolved from enumerator_id in raw_data | C(254) |
| REGION | resolved via form.region_field | C(254) |
| WOREDA | resolved via form.sub_region_field | C(254) |
| VAL_STATUS | submission.approval_status -> pending/approved/rejected | C(20) |
| NEEDS_RECL | plot.flagged_for_review -> Yes/No | C(10) |
| REJ_REASON | plot.flagged_reason | C(254) |
| CREATED_AT | epoch ms -> ISO 8601 | C(30) |
| SUBMIT_AT | submission.submission_time -> ISO 8601 | C(30) |

## Frontend

- **ExportProvider** context at dashboard layout level (persists polling across page navigation)
- **useExport** hook provides `startExport()` and `isExporting`
- **ExportToast** renders toast at layout level using existing ToastNotification component
- Export button shows spinner during export, auto-triggers download on completion

## Files

| File | Description |
|---|---|
| `backend/requirements.txt` | Added `pyshp==3.0.3` |
| `backend/api/v1/v1_jobs/` | New app: constants, models, serializers, views, urls |
| `backend/api/v1/v1_odk/export.py` | Export file generation utilities |
| `backend/api/v1/v1_odk/tasks.py` | Added `generate_export_file` async task |
| `backend/api/v1/v1_odk/views.py` | Added search filter + export action on PlotViewSet |
| `backend/api/v1/v1_odk/tests/tests_plots_export_endpoint.py` | 16 tests |
| `frontend/src/hooks/useExport.js` | ExportProvider context + hook |
| `frontend/src/components/export-toast.js` | ExportProviderWithToast wrapper |
| `frontend/src/app/dashboard/layout.js` | Wrapped with ExportProviderWithToast |
| `frontend/src/app/dashboard/page.js` | Wired up export button |
