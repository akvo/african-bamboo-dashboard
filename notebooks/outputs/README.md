# POC outputs (tracked)

Reviewable results from the V24–V27 geospatial POC notebooks. Everything here
is **committed on purpose**: it is the evidence cited by the plans in `docs/`,
small enough to read in a pull request, and contains no per-subject or locating
data.

| File | POC | Plan |
|------|-----|------|
| `v24_slope_summary.json` | Average slope over 30° | `docs/v24_average_slope_over_30_degrees.md` |
| `v25_elevation_summary.json` | Mean elevation outside 2,400–3,500 m | `docs/v25_elevation_under_2400_meters_or_above_3500.md` |
| `v26_road_summary.json` | Road overlap or within N metres | `docs/v26_road_within_n_meters_or_road_overlap.md` |
| `v27_tree_cover_summary.json` | Tree cover over 20% | `docs/v27_tree_cover_over_20.md` |

Each file carries the dataset provenance, the aggregate `summary`, and the
`boundary_demo` proving the strict-threshold contract. Regenerate by rerunning
the matching notebook; the files are overwritten in place.

## What is deliberately not here

The per-POC directories under `notebooks/data/` are fully ignored and stay that
way. They hold three categories of output that must not be committed:

| Kind | Example | Why it stays ignored |
|------|---------|----------------------|
| Per-plot rows | `elevation_results_private.json` | 166 per-subject records. No coordinates, but still one row per farm. |
| Georeferenced rasters | `cop30_subset.tif`, `worldcover_2021_subset.tif` | Their bounds **are** the padded plot bounding box. Opening one in QGIS pinpoints the collection area, even though the source datasets are public. |
| Road identity and geometry | `road_results_private.json`, `osm_roads_bbox_private.json`, `v24_django_aligned_sensitive.csv` | `nearest_osm_id` plus an exact distance pins a plot to a ring around a specific mappable OSM way. The aligned CSV contains exact polygon geometry. |

The split is enforced, not just documented: `poc_common.write_public_output`
screens every payload against `LOCATING_KEYS` and raises rather than writing a
locating field into this directory.

## If you add a new POC output

Write it through `write_public_output(name, payload)` and keep it aggregate. If
the guard rejects your payload, that is the intended answer — summarise the
field or leave it in `notebooks/data/`.
