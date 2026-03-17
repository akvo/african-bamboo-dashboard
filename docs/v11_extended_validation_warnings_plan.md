# V11: Extended Validation Warnings — Implementation Plan

**Source**: [extended-validation-validation-user-ac.md](extended-validation-validation-user-ac.md)
**Rule logic reference**: [extended-validation-rules.md](extended-validation-rules.md)
**Branch**: `feature/28-extended-validation-rules-warnings`

---

## Overview

Implement 5 warning-level validation checks **in the backend** that run during Kobo sync. Warnings do not reject plots — they attach flags for Helen's data quality review in the dashboard.

Key design decisions:

1. **`Plot.flagged_reason`** migrates from `CharField(500)` → `JSONField` holding a list of `{type, severity, note}` objects
2. All validation/warning type codes and **configurable thresholds** live in `constants.py`
3. **`Plot.area_ha`** (already computed during sync) is reused for the W4 area check — no redundant calculation
4. The 5 rules are computed in the backend during sync, not read from the mobile app's `dcu_validation_warnings` field

---

## Warning Rules

| # | Rule | Threshold (configurable) | Input |
|---|---|---|---|
| W1 | GPS accuracy too low | Average > 15 m | Accuracy values from ODK geoshape `lat lng alt acc` |
| W2 | Point gap too large | Any gap > 50 m | Haversine distance between consecutive vertices |
| W3 | Uneven point spacing | CV > 0.5 | Coefficient of Variation of inter-point distances |
| W4 | Plot area too large | > 20 ha | `Plot.area_ha` (pre-computed via UTM projection) |
| W5 | Too few vertices (rough boundary) | 6–10 vertices | Vertex count excluding closing point |

---

## Constants (`constants.py`)

All type codes and thresholds in one place:

```python
class FlagType:
    """Validation flag type codes."""

    # Geometry errors (existing)
    GEOMETRY_NO_DATA = "GEOMETRY_NO_DATA"
    GEOMETRY_PARSE_FAIL = "GEOMETRY_PARSE_FAIL"
    GEOMETRY_TOO_FEW_VERTICES = (
        "GEOMETRY_TOO_FEW_VERTICES"
    )
    GEOMETRY_SELF_INTERSECT = (
        "GEOMETRY_SELF_INTERSECT"
    )
    GEOMETRY_AREA_TOO_SMALL = (
        "GEOMETRY_AREA_TOO_SMALL"
    )

    # Overlap (existing)
    OVERLAP = "OVERLAP"

    # Warnings (new — W1–W5)
    GPS_ACCURACY_LOW = "GPS_ACCURACY_LOW"
    POINT_GAP_LARGE = "POINT_GAP_LARGE"
    POINT_SPACING_UNEVEN = "POINT_SPACING_UNEVEN"
    AREA_TOO_LARGE = "AREA_TOO_LARGE"
    VERTICES_TOO_FEW_ROUGH = (
        "VERTICES_TOO_FEW_ROUGH"
    )


class FlagSeverity:
    ERROR = "error"
    WARNING = "warning"


class WarningThresholds:
    """Configurable thresholds for warning rules.

    Agreed with African Bamboo, January 2026.
    """

    GPS_ACCURACY_MAX_M = 15.0
    POINT_GAP_MAX_M = 50.0
    SPACING_CV_MAX = 0.5
    AREA_MAX_HA = 20.0
    VERTICES_ROUGH_MIN = 6
    VERTICES_ROUGH_MAX = 10
```

---

## Data Model Change

### Before

```python
flagged_reason = models.CharField(
    max_length=500, null=True, blank=True
)
```

### After

```python
flagged_reason = models.JSONField(
    null=True, blank=True, default=None,
    help_text="List of flags: [{type, severity, note}]",
)
```

### JSON Structure

```json
[
  {
    "type": "OVERLAP",
    "severity": "error",
    "note": "Polygon overlaps with: Farmer A (enum_001-ET0407-2026-01-15)"
  },
  {
    "type": "POINT_GAP_LARGE",
    "severity": "warning",
    "note": "Gap of 671.3m between points 1-2 (threshold: 50m)"
  },
  {
    "type": "AREA_TOO_LARGE",
    "severity": "warning",
    "note": "Plot area is 44.7ha (threshold: 20ha)"
  }
]
```

- `flagged_for_review = True` when **any** flag exists (error or warning)
- `flagged_for_review = False` when checked and clean (empty list → stored as `None`)
- `flagged_for_review = None` when not yet checked

### Migration

Single `RunSQL` migration (`0010_alter_flagged_reason_to_json.py`) with `USING` clause + `state_operations`:

- `ALTER COLUMN flagged_reason TYPE jsonb USING CASE ... END` converts data atomically during the type change
- `state_operations` with `AlterField` keeps Django's ORM state in sync
- PostgreSQL cannot cast raw strings to JSONB directly, so `USING` maps each known string pattern to the correct JSON structure
- Reverse migration converts back to `VARCHAR(500)` using the first flag's `note`

### Management Command: `migrate_flagged_reason`

Standalone command for post-migration verification and manual re-runs:

```bash
python manage.py migrate_flagged_reason           # Apply
python manage.py migrate_flagged_reason --dry-run  # Preview
```

Uses shared converter in `utils/flagged_reason_converter.py`. Idempotent — skips values that are already JSON lists.

---

## Backend Changes

### Files Modified/Created

| File | Change |
|------|--------|
| `constants.py` | Added `FlagType`, `FlagSeverity`, `WarningThresholds` classes |
| `models.py` | `flagged_reason` → `JSONField` |
| `migrations/0010_alter_flagged_reason_to_json.py` | `RunSQL` with `USING` clause + `state_operations` |
| `management/commands/migrate_flagged_reason.py` | **New** — management command with `--dry-run` |
| `utils/flagged_reason_converter.py` | **New** — shared `convert_flagged_reason()` function |
| `utils/warning_rules.py` | **New** — `parse_odk_geoshape_full()`, `haversine_distance()`, `coefficient_of_variation()`, `evaluate_warnings()` |
| `utils/polygon.py` | `extract_plot_data()` returns structured `[{type, severity, note}]` flags; added `_geometry_error_type()` helper |
| `funcs.py` | `check_and_flag_overlaps()` additive (only manages OVERLAP type); `validate_and_check_plot()` preserves warning flags; helper functions `_non_overlap_flags()`, `_make_overlap_flag()`, `_append_overlap_flag()`, `_warning_flags()`, `_make_error_flag()` |
| `views.py` | Sync loop calls `evaluate_warnings()`, merges geometry errors + warnings + overlaps |
| `serializers.py` | No changes — `JSONField` auto-serializes |

### `extract_plot_data()` — Structured Flags

Three error paths now return `[{type, severity, note}]` instead of flat strings:

```python
result["flagged_reason"] = [
    {
        "type": FlagType.GEOMETRY_NO_DATA,
        "severity": FlagSeverity.ERROR,
        "note": "No polygon data found in submission.",
    }
]
```

`_geometry_error_type(error_msg)` maps `validate_polygon()` error messages to `FlagType` constants.

### `check_and_flag_overlaps()` — Additive Merge

Only manages `OVERLAP` flags, preserves all other flag types:

- `_non_overlap_flags()` filters out existing OVERLAP entries
- Adds new OVERLAP flag if overlaps found
- Preserves warning flags when no overlaps (sets `flagged_for_review` based on remaining flags)
- `_append_overlap_flag()` adds OVERLAP to existing plots (with duplicate prevention)

### `validate_and_check_plot()` — Preserves Warnings

After polygon edit/reset:
- `_warning_flags()` extracts warning-severity flags
- Geometry errors + preserved warnings merged on invalid geometry
- On valid geometry: sets warnings only, then `check_and_flag_overlaps()` adds OVERLAP if needed

### Sync Loop (`views.py`)

```python
plot_data = extract_plot_data(item, form)
raw_polygon = plot_data.get("raw_polygon_string")
area = calculate_area_ha(raw_polygon)

# Warning rules for valid geometry
warnings = []
if plot_data["polygon_wkt"]:
    warnings = evaluate_warnings(raw_polygon, area)

# Merge geometry errors + warnings
all_flags = []
if plot_data["flagged_reason"]:
    all_flags.extend(plot_data["flagged_reason"])
if warnings:
    all_flags.extend(warnings)

# Set on defaults (tri-state preserved when no flags)
if all_flags:
    defaults["flagged_for_review"] = True
    defaults["flagged_reason"] = all_flags

# Overlap detection runs after plot creation (additive)
if plot_data["polygon_wkt"]:
    check_and_flag_overlaps(plot)
```

---

## Frontend Changes

### Files Modified/Created

| File | Change |
|------|--------|
| `lib/flag.js` | **New** — `FlagType`, `FlagSeverity`, `FlagMessages` constants; `parseFlags()`, `splitFlags()` helpers |
| `components/map/plot-card-item.js` | Uses `splitFlags()` to show separate error (red `AlertCircle`) and warning (amber `AlertTriangle`) banners with counts |
| `components/map/plot-header-card.js` | Replaced `AlertBanner` with `FlagList` component; shows each flag individually with severity-colored icon + `FlagMessages` label; props changed from `alertMessage`/`alertTooltip` to `flaggedReason` |
| `components/map/plot-detail-panel.js` | Removed old `alertMessage`/`alertTooltip` computation; passes `flaggedReason={plot?.flagged_reason}` to `PlotHeaderCard` |

### `lib/flag.js` — Shared Constants & Helpers

```javascript
const FlagType = {
  GEOMETRY_NO_DATA: "GEOMETRY_NO_DATA",
  GEOMETRY_PARSE_FAIL: "GEOMETRY_PARSE_FAIL",
  // ... all 11 types
};

const FlagSeverity = { ERROR: "error", WARNING: "warning" };

const FlagMessages = {
  [FlagType.GEOMETRY_NO_DATA]: "No geometry data provided.",
  [FlagType.OVERLAP]: "Plot overlap detected.",
  [FlagType.GPS_ACCURACY_LOW]: "Average GPS accuracy > 15m",
  // ... all 11 messages
};

function parseFlags(flaggedReason) { /* array guard */ }
function splitFlags(flaggedReason) { /* → { errors, warnings } */ }
```

### `plot-card-item.js` — Dual Alert Banners

```javascript
const { errors, warnings } = splitFlags(plot.flagged_reason);

// Red banner: "1 data issue detected" / "3 data issues detected"
// Amber banner: "1 warning" / "5 warnings"
// Both can appear simultaneously
```

### `plot-header-card.js` — `FlagList` Component

Each flag rendered individually:
- Error flags: red `AlertCircle` icon + `border-status-rejected` styling
- Warning flags: amber `AlertTriangle` icon + `border-status-flagged` styling
- Label from `FlagMessages[flag.type]`, fallback to `flag.note`
- Tooltip shows `flag.note` for detail (e.g., specific segment info)

---

## Implementation Phases (All Complete)

### Phase 1: Constants & Warning Engine ✅

1. Added `FlagType`, `FlagSeverity`, `WarningThresholds` to `constants.py`
2. Created `utils/warning_rules.py` with `parse_odk_geoshape_full()`, `haversine_distance()`, `coefficient_of_variation()`, `evaluate_warnings()`
3. 36 unit tests in `tests/tests_warning_rules.py`

### Phase 2: Data Model Migration ✅

1. Changed `flagged_reason` to `JSONField` in model
2. `RunSQL` migration with `USING` clause for atomic VARCHAR→JSONB conversion
3. Created `migrate_flagged_reason` management command with `--dry-run`
4. Shared converter in `utils/flagged_reason_converter.py`
5. 15 unit tests in `tests/tests_migrate_flagged_reason_command.py`

### Phase 3: Backend Integration ✅

1. Updated `extract_plot_data()` → structured flags with `_geometry_error_type()` mapper
2. Updated `check_and_flag_overlaps()` → additive JSON merge (only manages OVERLAP)
3. Updated `validate_and_check_plot()` → preserves warning flags after edit/reset
4. Updated sync loop → calls `evaluate_warnings()` + merges geometry + warnings + overlaps
5. Updated 12 assertions across 4 test files for JSON format
6. All 414 backend tests pass, flake8 clean

### Phase 4: Frontend Display ✅

1. Created `lib/flag.js` — shared constants (`FlagType`, `FlagSeverity`, `FlagMessages`) and helpers (`parseFlags`, `splitFlags`)
2. Updated `plot-card-item.js` — dual error/warning banners with counts
3. Updated `plot-header-card.js` — `FlagList` component with per-flag severity-colored display
4. Updated `plot-detail-panel.js` — passes `flaggedReason` prop instead of legacy alert strings
5. ESLint clean, Next.js build passes

---

## Test Results

### Backend — 414 tests pass

| Suite | Tests | Status |
|-------|-------|--------|
| Warning rules (`tests_warning_rules.py`) | 36 | ✅ |
| Management command (`tests_migrate_flagged_reason_command.py`) | 15 | ✅ |
| Overlap detection (`tests_overlap_detection.py`) | Updated 3 | ✅ |
| Polygon utils (`tests_polygon_utils.py`) | Updated 3 | ✅ |
| Plot reset (`tests_plots_reset_endpoint.py`) | Updated 2 | ✅ |
| Revert pending (`tests_revert_pending_endpoint.py`) | Updated 3 | ✅ |
| All other existing tests | 352 | ✅ |

### Frontend — lint + build clean

---

## AC Checklist

### Constants & Engine
- [x] `FlagType` defines all 11 type codes
- [x] `FlagSeverity` defines `error` / `warning`
- [x] `WarningThresholds` configurable in `constants.py`
- [x] `evaluate_warnings()` implements all 5 rules
- [x] W1 skips `0.0` accuracy values
- [x] W2 reports per-segment with indices
- [x] W3 requires ≥ 3 points (2 segments)
- [x] W4 uses `Plot.area_ha` (no recomputation)
- [x] W5 excludes closing point from count

### Data Model & Migration
- [x] `flagged_reason` migrated to `JSONField`
- [x] `RunSQL` migration with `USING` clause (atomic VARCHAR→JSONB)
- [x] `migrate_flagged_reason` management command with `--dry-run`
- [x] Shared converter in `utils/flagged_reason_converter.py`
- [x] Existing string data converted to `[{type, severity, note}]`
- [x] No data loss (21 flagged plots converted, verified)
- [x] Management command is idempotent (skips already-converted rows)

### Backend Integration
- [x] `extract_plot_data()` returns structured flags
- [x] `check_and_flag_overlaps()` additive (only manages OVERLAP)
- [x] `validate_and_check_plot()` preserves warning flags
- [x] Sync loop runs `evaluate_warnings()` for valid plots
- [x] Flags merged: geometry errors + warnings + overlaps
- [x] Multiple warnings per plot supported

### Frontend
- [x] `lib/flag.js` — shared `FlagType`, `FlagSeverity`, `FlagMessages`, `parseFlags()`, `splitFlags()`
- [x] Plot card shows error count (red `AlertCircle`) + warning count (amber `AlertTriangle`)
- [x] Detail header shows per-flag list with severity-colored icons and `FlagMessages` labels
- [x] Backwards-compatible with `null` flagged_reason (`parseFlags` returns `[]`)

### Tests
- [x] Warning rules: all 5 rules + edge cases (36 tests)
- [x] Helpers: haversine, CV, geoshape parser
- [x] Management command: type mapping, idempotency, dry-run (15 tests)
- [x] All 12 existing flagged_reason assertions updated for JSON format
- [x] 414 backend tests pass, flake8 clean
- [x] Frontend ESLint + Next.js build clean

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| VARCHAR → JSONB migration fails on existing data | `RunSQL` with `USING` clause converts data atomically; tested on staging (21 plots converted) |
| Frontend breaks on JSON format | `parseFlags()` guards with `Array.isArray()`; returns `[]` for null/non-array |
| Overlap reason grows unbounded | OVERLAP entries are replaced (not appended) each recomputation |
| `area_ha` is None for invalid polygons | W4 skips when `area_ha` is None (warnings only run for valid geometry) |
| Raw polygon string unavailable | `raw_polygon_string` already extracted in sync loop and passed through |

---

## Out of Scope

- Reading warnings from mobile app's `dcu_validation_warnings` field (backend computes its own)
- Writing warnings back to Kobo (mobile app handles this)
- Configurable thresholds via admin UI (constants file is sufficient)
- Warning export/reporting beyond the dashboard UI
- Dashboard filter by error/warning category (future enhancement)
