# v12 — Export to XLSX Implementation Plan

## Objective

Implement a downloadable `.xlsx` export of the full cleaned dataset from the DCU app, structured to align with the existing **Afforestation Monitoring Database** format (Farmer Table sheet + Plot Table sheet), preserving Farmer ID and Plot ID continuity and including additional DCU fields as new columns.

Based on: `docs/export-to-excel-user-ac.md`

---

## Status: Implemented

All three phases are complete. See commits on `feature/30-export-of-cleaned-data`.

---

## Reference: Afforestation Monitoring Database Schema

### Farmer Table columns (dynamic via FarmerFieldMapping)
| # | Column | Source |
|---|--------|--------|
| 1 | FarmerID (primary key) | `AB` + sequential zero-padded UID (`AB00001`, `AB00002`, ...) |
| 2+ | *Dynamic columns* | Built from `FarmerFieldMapping.unique_fields` + `values_fields`, headers from `FormQuestion.label` |

### Plot Table columns
| # | Column | Source |
|---|--------|--------|
| 1 | Plot ID | `PLT` + `Submission.kobo_id` |
| 2 | Farmer ID | `AB` + `Farmer.uid` (FK) |
| 3 | Title Deed First Page | Kobo attachment URL (via FieldMapping) |
| 4 | Title Deed Second Page | Kobo attachment URL (via FieldMapping) |
| 5 | Latitude | Centroid lat from polygon_wkt |
| 6 | Longitude | Centroid lon from polygon_wkt |
| 7 | Altitude | Average altitude from ODK geoshape string |
| 8 | Entire Area Polygon | On-demand KML download URL (via `STORAGE_SECRET` auth) |
| 9 | Plantation Polygon | Reserved (empty) |

---

## Phase 1: Farmer Pre-processing — DONE

### 1.1 Migration: Farmer, FarmerFieldMapping, Plot.farmer

**File**: `backend/api/v1/v1_odk/migrations/0011_farmer_farmerfieldmapping_plot_farmer.py`

Single migration creates:
- `Farmer` model with `uid`, `lookup_key`, `values` (JSONField)
- `FarmerFieldMapping` model with `form` FK, `unique_fields` (TextField), `values_fields` (TextField)
- `Plot.farmer` FK (nullable, SET_NULL)

### 1.2 Models

**File**: `backend/api/v1/v1_odk/models.py`

```python
class Farmer(models.Model):
    uid = CharField(max_length=125, unique=True)
    lookup_key = CharField(max_length=500, unique=True)
    values = JSONField(null=True, blank=True)

class FarmerFieldMapping(models.Model):
    form = ForeignKey(FormMetadata, CASCADE)
    unique_fields = TextField()  # comma-separated
    values_fields = TextField()  # comma-separated
```

`Plot.farmer` — ForeignKey to Farmer (nullable, SET_NULL, related_name="plots")

### 1.3 Farmer sync utility

**File**: `backend/api/v1/v1_odk/utils/farmer_sync.py`

`sync_farmers_for_form(form)` orchestrates:
1. Reads `FarmerFieldMapping` for the form
2. Resolves field values from `raw_data` using `build_option_lookup` / `resolve_value`
3. Builds lookup key from unique fields joined with `" - "`
4. Creates/updates `Farmer` records with sequential zero-padded UIDs
5. Links plots to farmers via `Plot.farmer` FK
6. Returns `{"created": N, "updated": N, "linked": N}`

### 1.4 Management command

**File**: `backend/api/v1/v1_odk/management/commands/sync_farmers.py`

```bash
python manage.py sync_farmers              # all forms
python manage.py sync_farmers --form <uid> # specific form
```

### 1.5 Tests

**File**: `backend/api/v1/v1_odk/tests/tests_farmer_sync.py`

15 tests covering: field resolution (text, select, missing), lookup key building, UID generation (first, sequential, beyond 5 digits), sync create/update/link/dedup/no-mapping, management command.

---

## Phase 2: XLSX Export — DONE

### 2.1 Job type

**File**: `backend/api/v1/v1_jobs/constants.py`

```python
export_xlsx = 3
```

### 2.2 XLSX generation

**File**: `backend/api/v1/v1_odk/export.py`

`generate_xlsx(queryset, form, filename)` — creates two-sheet workbook:
- **Sheet "Farmer table"**: Dynamic headers from `FarmerFieldMapping` → `FormQuestion.label`. One row per unique farmer, sorted by UID.
- **Sheet "Plot Table"**: Fixed 9-column layout (Plot ID, Farmer ID, Title Deed 1 & 2, Lat, Lon, Altitude, KML URL, Plantation Polygon).

Key helpers:
- `_build_farmer_headers(form)` — builds dynamic farmer column headers
- `_extract_avg_altitude(raw_data, form)` — averages altitude from ODK geoshape string
- `_resolve_attachment_url(raw_data, field_name, kobo_base_url)` — resolves Kobo media URLs
- `_wkt_to_kml(wkt_string, name)` — converts WKT polygon to KML XML document

### 2.3 KML endpoint

**File**: `backend/api/v1/v1_odk/views.py`

`GET /api/v1/odk/plots/{uuid}/kml/?key={STORAGE_SECRET}` — returns on-demand KML file download per plot, authenticated via `STORAGE_SECRET` query param (AllowAny permission, no JWT needed). Content-Type: `application/vnd.google-earth.kml+xml`.

The XLSX "Entire Area Polygon" column contains the full KML download URL: `{WEBDOMAIN}/api/v1/odk/plots/{uuid}/kml/?key={STORAGE_SECRET}`

### 2.4 Export task & view

**Files**: `backend/api/v1/v1_odk/tasks.py`, `backend/api/v1/v1_odk/views.py`

- `generate_export_file()` handles `JobTypes.export_xlsx`: runs `sync_farmers_for_form(form)` before generating XLSX
- Export view accepts `format: "xlsx"` alongside `"shp"` and `"geojson"`

### 2.5 Frontend export dropdown

**Files**: `frontend/src/app/dashboard/page.js`, `frontend/src/hooks/useExport.js`

- Export button is a dropdown with Shapefile, GeoJSON, and Download Clean Data (.xlsx) options
- `useExport` hook accepts format parameter

### 2.6 Tests

**File**: `backend/api/v1/v1_odk/tests/tests_export_xlsx.py`

33 tests across 6 test classes:
- `ExtractAvgAltitudeTest` (4) — geoshape altitude extraction
- `ResolveAttachmentUrlTest` (5) — Kobo attachment URL resolution
- `GetKoboBaseUrlTest` (2) — Kobo base URL lookup
- `BuildFarmerHeadersTest` (3) — dynamic farmer headers
- `GenerateXlsxTest` (12) — full XLSX generation (sheets, headers, rows, IDs, centroids, altitude, KML URL, no-geometry)
- `ExportXlsxEndpointTest` (2) — endpoint job creation
- `WktToKmlTest` (4) — KML conversion

**File**: `backend/api/v1/v1_odk/tests/tests_plot_kml_endpoint.py`

4 tests: valid key returns KML, invalid key 403, missing key 403, no polygon 404.

---

## Phase 3: Farmers & Enumerators Page — DONE

### 3.1 Farmer list endpoint

**File**: `backend/api/v1/v1_odk/views.py`

`GET /api/v1/odk/farmers/?form_id=<uid>&search=<query>&limit=10&offset=0`

`FarmerViewSet` (ListModelMixin + GenericViewSet):
- Filters by `form_id` via `plots__form__asset_uid`
- Search on `lookup_key` (case-insensitive)
- Values dict filtered to form's `FarmerFieldMapping` fields, keys replaced with `FormQuestion.label`
- Leaf-name matching for cross-form key resolution (handles group-prefixed field names)
- Response: `{ uid, farmer_id, name, values, plot_count }`

### 3.2 Enumerator list endpoint

**File**: `backend/api/v1/v1_odk/views.py`

`GET /api/v1/odk/enumerators/?form_id=<uid>&search=<query>&limit=10&offset=0`

`EnumeratorViewSet` (ListModelMixin + GenericViewSet):
- Derives unique enumerators from `Submission.raw_data.enumerator_id`
- Resolves raw values to labels via `FormOption` (using `build_option_lookup` / `resolve_value`)
- Manual pagination (aggregation done in Python)
- Response: `{ code, name, submission_count }`

### 3.3 Farmer field mapping endpoint

**File**: `backend/api/v1/v1_odk/views.py`

`GET/PUT /api/v1/odk/forms/{asset_uid}/farmer-field-mapping/`

Action on `FormMetadataViewSet`:
- GET: returns `{ unique_fields: [...], values_fields: [...] }` (arrays)
- PUT: creates or updates `FarmerFieldMapping`, validates `unique_fields` non-empty, defaults `values_fields` to `unique_fields` if empty

### 3.4 Frontend: Sidebar nav

**File**: `frontend/src/components/app-sidebar.js`

Added "Farmers and Enumerators" nav item with `Users` icon.

### 3.5 Frontend: Page implementation

**File**: `frontend/src/app/dashboard/farmers-n-enumerators/page.js`

- **Form selector**: Dropdown using `useForms()` context to filter both tabs by active form
- **Tabs**: Farmers | Enumerators
- **Search**: Per-tab search input
- **Farmers table**: Farmer ID (mono), Name, dynamic value columns (from form mapping with label headers), Plot count
- **Enumerators table**: Code (FormOption.name), Name (FormOption.label), Submission count
- **Pagination**: Page controls with limit/offset
- Custom `usePaginatedData(endpoint, formId)` hook with form-aware fetching and offset reset on form change

### 3.6 Frontend: Farmer Fields config tab

**File**: `frontend/src/app/dashboard/forms/page.js`

Third tab "Farmer Fields" in form configuration dialog:
- **Unique fields (identity)**: Multi-select for farmer deduplication key
- **Values fields (data to store)**: Multi-select for fields stored on farmer record
- Saved alongside other mappings on "Save Mappings"

### 3.7 Tests

**File**: `backend/api/v1/v1_odk/tests/tests_farmers_endpoint.py`

12 tests: auth, list all, filter by form (2 forms), search, farmer_id prefix, plot count, values filtered by form mapping (2 forms), leaf-name matching, pagination (2).

**File**: `backend/api/v1/v1_odk/tests/tests_enumerators_endpoint.py`

9 tests: auth, list all, filter by form, code/name fields, submission count, search (case-insensitive), pagination, no-enumerator excluded.

**File**: `backend/api/v1/v1_odk/tests/tests_farmer_field_mapping_endpoint.py`

7 tests: auth, GET empty, PUT create, PUT update, PUT validation, PUT defaults, GET after PUT roundtrip.

---

## URL Registration

**File**: `backend/api/v1/v1_odk/urls.py`

```python
router.register(r"forms", views.FormMetadataViewSet)
router.register(r"submissions", views.SubmissionViewSet)
router.register(r"plots", views.PlotViewSet)
router.register(r"field-settings", views.FieldSettingsViewSet)
router.register(r"field-mappings", views.FieldMappingViewSet)
router.register(r"farmers", views.FarmerViewSet)
router.register(r"enumerators", views.EnumeratorViewSet, basename="enumerator")
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `openpyxl` | >=3.1 | XLSX file generation |

---

## Files Changed / Created

### Phase 1 — Farmer Pre-processing
| Action | File |
|--------|------|
| Create | `backend/api/v1/v1_odk/migrations/0011_farmer_farmerfieldmapping_plot_farmer.py` |
| Create | `backend/api/v1/v1_odk/utils/farmer_sync.py` |
| Create | `backend/api/v1/v1_odk/management/commands/sync_farmers.py` |
| Create | `backend/api/v1/v1_odk/tests/tests_farmer_sync.py` |
| Modify | `backend/api/v1/v1_odk/models.py` |

### Phase 2 — XLSX Export + KML
| Action | File |
|--------|------|
| Create | `backend/api/v1/v1_odk/tests/tests_export_xlsx.py` |
| Create | `backend/api/v1/v1_odk/tests/tests_plot_kml_endpoint.py` |
| Modify | `backend/api/v1/v1_jobs/constants.py` |
| Modify | `backend/api/v1/v1_jobs/views.py` |
| Modify | `backend/api/v1/v1_odk/export.py` |
| Modify | `backend/api/v1/v1_odk/tasks.py` |
| Modify | `backend/api/v1/v1_odk/views.py` |
| Modify | `backend/requirements.txt` |
| Modify | `frontend/src/app/dashboard/page.js` |
| Modify | `frontend/src/hooks/useExport.js` |

### Phase 3 — Farmers & Enumerators Page
| Action | File |
|--------|------|
| Create | `backend/api/v1/v1_odk/tests/tests_farmers_endpoint.py` |
| Create | `backend/api/v1/v1_odk/tests/tests_enumerators_endpoint.py` |
| Create | `backend/api/v1/v1_odk/tests/tests_farmer_field_mapping_endpoint.py` |
| Create | `frontend/src/app/dashboard/farmers-n-enumerators/page.js` |
| Modify | `backend/api/v1/v1_odk/views.py` |
| Modify | `backend/api/v1/v1_odk/urls.py` |
| Modify | `frontend/src/components/app-sidebar.js` |
| Modify | `frontend/src/app/dashboard/forms/page.js` |
