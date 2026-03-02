# V5: Kobo Geometry Sync — Implementation

## Context

When a user edits plot polygon geometry and clicks Save, or resets a polygon to its original, the changes must be pushed back to KoboToolbox so both systems stay in sync. Additionally, when syncing from Kobo with comma-separated fallback polygon fields, the system must track **which field** the geometry was originally read from, so edits are written back to the correct Kobo field.

**Principle**: `submission.raw_data` is the single source of truth for "original" data. It holds the first-synced version from Kobo and is never modified by save or reset operations.

---

## Summary of Changes

### Model Changes

| Change | File |
|--------|------|
| Added `polygon_source_field` (nullable CharField) to `Plot` | `models.py` |
| Removed `instance_name` from `Plot` (redundant — `Submission` already has it) | `models.py` |
| Made `plot_name` nullable (`null=True, blank=True`) | `models.py` |
| Updated `Plot.__str__` with fallback chain: `plot_name` → `submission.instance_name` → `uuid` | `models.py` |
| Migration: `0005_remove_plot_instance_name_plot_polygon_source_field_and_more.py` | `migrations/` |

### Backend Files Modified/Created

| File | Change |
|------|--------|
| `backend/utils/polygon.py` | Added `coords_to_odk_geoshape()`, `wkt_to_odk_geoshape()`, `parse_wkt_polygon()`. Modified `_extract_first_nonempty()` to return `(value, field_name)` tuple. `extract_plot_data()` now includes `polygon_source_field`. `_build_plot_name()` returns `None` instead of `meta/instanceName` fallback. `build_overlap_reason()` uses `p.submission.instance_name`. `find_overlapping_plots()` adds `.select_related("submission")`. |
| `backend/utils/kobo_client.py` | Added `update_submission_data()` — uses **bulk PATCH** endpoint (`/api/v2/assets/{uid}/data/bulk/`) |
| `backend/api/v1/v1_odk/tasks.py` | Added `sync_kobo_submission_geometry()` async task |
| `backend/api/v1/v1_odk/funcs.py` | New file with `dispatch_kobo_geometry_sync()`, `check_and_flag_overlaps()`, `validate_and_check_plot()`, `rederive_plots()`, `sync_form_questions()`. Uses `plot.polygon_source_field` for correct Kobo field targeting. |
| `backend/api/v1/v1_odk/views.py` | `PlotViewSet.perform_update()` calls `dispatch_kobo_geometry_sync()`. `reset_polygon` sets `polygon_source_field` and dispatches Kobo sync. `get_queryset()` adds `.select_related("submission")`. Sync loop includes `polygon_source_field` in defaults. |
| `backend/api/v1/v1_odk/serializers.py` | `instance_name` changed to `SerializerMethodField` reading `obj.submission.instance_name`. `get_plot_name` handles `None` gracefully. API contract unchanged. |
| `backend/api/v1/v1_odk/management/commands/backfill_polygon_source.py` | New management command to backfill `polygon_source_field` for existing plots. Supports `--dry-run`. |
| `frontend/src/components/map/save-edit-dialog.js` | Updated dialog text to mention Kobo sync |
| `frontend/src/app/dashboard/map/page.js` | Updated toast messages to mention Kobo sync |

### Test Files Modified/Created

| File | Changes |
|------|---------|
| `tests/test_models.py` | Removed `instance_name` from Plot.objects.create calls. Added `test_plot_str_without_name`. |
| `tests/tests_plots_endpoint.py` | Removed `instance_name`. Added PATCH-triggers-Kobo-sync test. |
| `tests/tests_plots_reset_endpoint.py` | Removed `instance_name`. Added reset-triggers-Kobo-sync test. |
| `tests/tests_overlap_detection.py` | Removed `instance_name`. `_make_plot` helper creates mock Submission with instance_name. |
| `tests/tests_submissions_endpoint.py` | Removed `instance_name` from Plot.objects.create. |
| `tests/tests_forms_endpoint.py` | Removed `instance_name` from Plot.objects.create. |
| `tests/tests_polygon_utils.py` | Added `polygon_source_field` tests, `coords_to_odk_geoshape` tests, `wkt_to_odk_geoshape` tests. `test_plot_name_all_empty` expects `None`. |
| `tests/tests_tasks.py` | Added `SyncKoboSubmissionGeometryTest`, `KoboClientUpdateSubmissionDataTest` verifying bulk endpoint URL and payload. |
| `tests/tests_backfill_command.py` | New: 4 tests for `backfill_polygon_source` management command. |

---

## Key Implementation Details

### Polygon Source Field Tracking

`_extract_first_nonempty()` returns a `(value, field_name)` tuple. When a form has `polygon_field = "primary,fallback"` and the geometry comes from the `fallback` field, `polygon_source_field` is set to `"fallback"`. This ensures edits are synced back to the correct Kobo field.

```
polygon_field_name = (
    plot.polygon_source_field
    or form.polygon_field.split(",")[0].strip()
)
```

### Kobo API: Bulk PATCH Endpoint (Critical Fix)

The individual submission PATCH endpoint (`/api/v2/assets/{uid}/data/{id}/`) returns **405 Method Not Allowed** on KoboToolbox. The correct endpoint for updating submission data is the **bulk PATCH**:

```
PATCH /api/v2/assets/{asset_uid}/data/bulk/

{
    "payload": {
        "submission_ids": [submission_id],
        "data": {"field_name": "field_value"}
    }
}
```

This was discovered during live testing against `eu.kobotoolbox.org`.

### Serializer: instance_name as SerializerMethodField

`Plot.instance_name` was removed from the model (it duplicated `Submission.instance_name`). The API contract is preserved via:

```python
instance_name = serializers.SerializerMethodField()

def get_instance_name(self, obj):
    if obj.submission:
        return obj.submission.instance_name
    return None
```

### Backfill Management Command

For existing data where `polygon_source_field` is NULL:

```bash
python manage.py backfill_polygon_source           # Apply
python manage.py backfill_polygon_source --dry-run  # Preview
```

---

## Data Lifecycle

```
SAVE FLOW:
  User edits polygon on map
  → editedGeo state updated (React useState)
  → User clicks Save → SaveEditDialog confirms
  → Frontend: PATCH /v1/odk/plots/{uuid}/ {polygon_wkt, bbox}
  → Backend: PlotViewSet.perform_update() saves to DB
  → Backend: validate_and_check_plot() validates geometry + overlap detection
  → Backend: dispatch_kobo_geometry_sync() → async_task dispatched
  → Async worker: converts WKT → ODK geoshape via wkt_to_odk_geoshape()
  → Async worker: KoboClient.update_submission_data() bulk PATCHes Kobo
  → Frontend: setEditedGeo(null), refetch(), toast "Syncing to Kobo..."

RESET FLOW:
  User clicks Reset in toolbar
  → Frontend: POST /v1/odk/plots/{uuid}/reset_polygon/
  → Backend: extract_plot_data(submission.raw_data) → restores original geometry
  → Backend: plot.polygon_source_field = plot_data["polygon_source_field"]
  → Backend: plot.save() → DB updated with original
  → Backend: dispatch_kobo_geometry_sync() → async_task dispatched
  → Async worker: pushes original geometry to Kobo
  → Frontend: setEditedGeo(null), refetch(), toast "Syncing to Kobo..."

CANCEL FLOW (unchanged):
  User clicks Cancel
  → setEditedGeo(null), handleCancelEditing()
  → MapEditLayer unmounts, original polygon from plots[] re-renders
  → No API calls, pure frontend state reset

PRISTINE DATA CONTRACT:
  submission.raw_data is NEVER modified by any operation.
  It always holds the first-synced version from Kobo.
  Reset re-derives geometry FROM raw_data; it does not modify raw_data.
  After a reset, both local DB and Kobo reflect the original raw_data geometry.
```

---

## Edge Cases

1. **No Kobo credentials**: `dispatch_kobo_geometry_sync()` silently returns. Save/reset still work locally.
2. **No `polygon_field` configured on form**: Silently skips Kobo sync (don't know which field to update).
3. **No linked submission**: Silently skips (no `kobo_id` to target).
4. **Empty `polygon_wkt` after reset** (original had no polygon): Silently skips — cannot push empty geometry to Kobo.
5. **Kobo API failure**: Logged at ERROR level, user is not blocked. Local DB is already updated.
6. **Re-sync from Kobo after edit**: If a full sync is later triggered, `raw_data` will be overwritten with whatever Kobo has (which now includes the edit). This is expected — `raw_data` tracks Kobo's current state.
7. **Comma-separated `polygon_field`**: `polygon_source_field` tracks which field the geometry was read from. Writes go to that specific field, not always the first.
8. **`plot_name` is NULL**: When no `plot_name_field` is configured or no matching data exists, `plot_name` is stored as NULL. The serializer falls back to `submission.instance_name` for display.
9. **Orphan plots** (no linked submission): `instance_name` returns None, `__str__` falls back to UUID.

---

## Verification

All 167 tests pass. Flake8 clean.

```bash
docker-compose exec backend python manage.py test api.v1.v1_odk --verbosity=2
docker-compose exec backend flake8
```

Manual testing confirmed:
- Save edits sync to Kobo via bulk PATCH (verified against `eu.kobotoolbox.org`)
- Reset restores original geometry from `raw_data` and syncs to Kobo
- Kobo JSON API and XML both reflect synced coordinates
- Backfill command correctly sets `polygon_source_field` for existing plots (20 plots backfilled in staging)
