# Extended Validation Rules (Warning Flags)

## Overview

Five data-quality warning checks run automatically when submissions are synced from KoboToolbox. Unlike reject-level validation (polygon geometry, overlap detection), these rules **do not block** submissions — they attach warning flags for review.

Rules were confirmed with African Bamboo in January 2026.

## Warning Rules

| # | Rule | Threshold | What it checks |
|---|---|---|---|
| W1 | GPS accuracy too low | Average > 15 m | Mean of per-point accuracy values from the geoshape |
| W2 | Point gap too large | Any gap > 50 m | Haversine distance between consecutive polygon vertices |
| W3 | Uneven point spacing | CV > 0.5 | Coefficient of Variation of all inter-point distances |
| W4 | Plot area too large | > 20 ha | Area via Shoelace formula with latitude correction |
| W5 | Too few vertices | 6–10 vertices | Vertex count excluding the closing point |

### W1: GPS Accuracy

Computes the average of `GeoCoordinate.acc` values from the ODK geoshape string (`lat lng alt acc; ...`). Points where accuracy is `0.0` are skipped (unavailable). If all points have `0.0` accuracy, no warning is generated.

### W2: Point Gap

Checks each consecutive pair of polygon vertices using Haversine distance. Returns **one warning per segment** that exceeds 50m, including the segment indices in the message (e.g., "Gap of 671.3m between points 1-2").

### W3: Uneven Spacing

Computes all inter-point distances, then calculates the Coefficient of Variation (standard deviation / mean). A CV > 0.5 indicates some segments are significantly longer or shorter than others, suggesting uneven walking pace or GPS drift. Requires at least 3 points (2 segments) for a meaningful CV.

### W4: Area Too Large

Calculates plot area using the Shoelace formula in degree-space, then converts to hectares using centroid latitude for the longitude correction factor. Plots exceeding 20 hectares are flagged.

### W5: Low Vertex Count

Counts distinct vertices (excluding the closing point that duplicates the first). Polygons with fewer than 6 vertices are already rejected by `PolygonValidator`. This rule flags the 6–10 range where the polygon is technically valid but the boundary may be too rough to be useful.

## When Warnings Run

```
Sync from KoboToolbox
  └─ extractPlotsFromSubmissions()
       ├─ Extract plot geometry (PlotExtractor)
       └─ computeAndPersistWarnings()
            ├─ Parse geoshape → GeoCoordinates
            ├─ Calculate area in hectares
            ├─ WarningRuleEngine.evaluate() → List<PlotWarning>
            └─ Save to plot_warnings table
```

Warnings are computed for **all submissions that don't already have warnings** — including submissions that were synced before the warning feature was added.

## Polygon Field Discovery

Polygon field names vary across forms (e.g., `boundary_mapping/manual_boundary`, `validate_polygon`, `consent_group/consented/boundary_mapping/Open_Area_GeoMapping`). The app discovers them dynamically:

1. `GET /api/v2/assets/{assetUid}/` fetches the form structure
2. Parses `content.survey` and filters for `type == "geoshape"` or `type == "geotrace"`
3. Uses `$xpath` (full path) with fallback to `name`
4. Caches discovered field paths in `FormMetadataEntity.polygonFields`

No static configuration file is needed.

## Kobo Write-Back

Warnings are synced back to KoboToolbox via two redundant strategies:

### Primary: Bulk PATCH

```
PATCH /api/v2/assets/{assetUid}/data/bulk/
```

Writes a pipe-delimited string to the `dcu_validation_warnings` calculate field:

```
GPS_ACCURACY_LOW: 18.3m (>15m) | AREA_TOO_LARGE: 44.7ha (>20ha)
```

Requires a `calculate` field in the XLSForm:

| type | name | calculation |
|---|---|---|
| calculate | dcu_validation_warnings | `once('')` |

### Fallback: Submission Notes

```
POST /api/v1/notes
```

Each warning posted as a separate note with `[DCU Warning]` prefix:

```
[DCU Warning] Average GPS accuracy is 18.3m (threshold: 15m)
[DCU Warning] Plot area is 44.7ha (threshold: 20ha)
```

## UI Display

- **Submission list**: Amber warning badge with count on each submission that has warnings
- **Submission detail**: Warning section with amber cards showing human-readable messages, displayed before the answer items
- **Dashboard filter**: Warning icon toggle in the top bar filters the list to show only submissions with warnings (icon turns amber when active)

## Data Storage

Warnings are stored in the `plot_warnings` table:

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-generated |
| `plotSubmissionUuid` | TEXT | FK to submission UUID |
| `warningType` | TEXT | Enum name (e.g., `GPS_ACCURACY_LOW`) |
| `message` | TEXT | Human-readable text for UI and notes |
| `shortText` | TEXT | Compact text for the PATCH field |
| `value` | REAL | Measured value that triggered the warning |
| `fieldSynced` | INTEGER | Whether PATCH to Kobo succeeded |
| `notesSynced` | INTEGER | Whether POST note to Kobo succeeded |

Indexed on `plotSubmissionUuid` and `warningType`.

## Key Files

| File | Purpose |
|---|---|
| `validation/WarningRuleEngine.kt` | All 5 rules + area calculation |
| `validation/GeoMath.kt` | Haversine distance, coefficient of variation |
| `validation/PlotWarning.kt` | `WarningType` enum + `PlotWarning` data class |
| `data/entity/PlotWarningEntity.kt` | Room entity with sync tracking |
| `data/dao/PlotWarningDao.kt` | CRUD, aggregation, sync status queries |
| `data/repository/KoboRepository.kt` | Warning compute, Kobo sync, field discovery |
| `data/repository/PlotExtractor.kt` | Plot extraction with dynamic polygon fields |
| `ui/screen/SubmissionDetailScreen.kt` | Warning display in detail view |
| `ui/component/SubmissionListItem.kt` | Warning badge on list items |

## Relationship to Other Validation

| Validation | Level | Effect | When |
|---|---|---|---|
| Polygon geometry (vertex count, area, self-intersection) | **Reject** | Blocks submission in ODK Collect | ODK "Launch" button |
| Plot overlap (>= 20% of smaller area) | **Reject** | Blocks submission in ODK Collect | ODK "Launch" button |
| Extended rules (W1–W5) | **Warning** | Flags for review, does not block | Post-sync processing |
