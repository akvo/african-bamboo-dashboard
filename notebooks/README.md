# Notebooks — data-quality analysis

Ad-hoc analysis notebooks for the African Bamboo dashboard. **No data is
committed** — the `data/` folder and all spreadsheets/exports are gitignored
because they contain private farmer and plot geometry. You supply the data
locally (see [Getting the data](#getting-the-data)).

## Notebooks

| Notebook | Purpose |
|---|---|
| [`gap_platform_vs_validation.ipynb`](gap_platform_vs_validation.ipynb) | Explains why the GIS validation report flags an overlap (e.g. 795099854 ↔ 796376139 at 88%) that the platform does **not** show. Proves it's a boundary-version mismatch, not a bug. |

## The finding (gap: validation report vs. platform)

The validation report and the platform are **correct** — they measure two
different boundaries of the same plot:

| | Boundary | Raw Kobo field | Overlap 795099854 ↔ 796376139 |
|---|---|---|---|
| Report `step4_*` (as captured) | what the enumerator drew in the field | `validate_polygon` | **88% / 65%** |
| Platform / report `step6_*` (final) | boundary after adjustment | `Open_Area_GeoMapping` | **0% / 0%** |

The plot was redrawn after capture (area grew ~0.057/0.077 ha → ~0.167/0.163 ha),
which removed the overlap. The report already agrees with the platform in its
`step6_final_max_overlap_pct = 0` column; the apparent contradiction only
appears if you read the `step4` (captured) number and compare it to the
platform map.

### What "step4" / "step6" mean

These are **stages in the `ab_polygon_checks.py` validation script**, not
platform terms. They follow the data-quality check plan, and the
`8_quality_checks` sheet footnote states it directly:

> Step 4 uses the boundary **as captured** (`validate_polygon`); step 6 compares
> it with the boundary **now in Kobo** (`Open_Area_GeoMapping`).

So a colleague checks the definition in their own script's step numbering and in
that sheet footnote.

### Why the platform uses `Open_Area_GeoMapping`

Confirmed against the live local DB
([`backend/api/v1/v1_odk/models.py`](../backend/api/v1/v1_odk/models.py)):

- `Submission.raw_data` (JSON) holds **both** `validate_polygon` (captured) and
  `Open_Area_GeoMapping` (final).
- The displayed/exported polygon is extracted into `Plot.polygon_wkt` from the
  **one** field named by `FormMetadata.polygon_field`. For the parcel-boundary
  form that field is `…/Open_Area_GeoMapping`, and `Plot.polygon_source_field`
  on both submissions confirms it.
- `Plot.area_ha` (0.17 / 0.16) is the adjusted area, not the captured one.

**Conclusion: no platform change needed.** To align the script's overlap figures
with the platform, compare on `step6_*` (`Open_Area_GeoMapping`), and keep
`step4_*` (`validate_polygon`) as a separate "field-capture quality" metric.

## Getting the data

Place these files under `notebooks/data/` (gitignored). Ask the team for the
current exports:

```
notebooks/
  data/
    reports/
      ab_platform_data.xlsx      # platform export: Plot Table (Entire Area Polygon KML URLs)
      ab_validation_data.xlsx    # ab_polygon_checks.py output (sheet 8_quality_checks)
    2026-08-14_ab_realdata.csv   # raw Kobo export (;-separated); 'Validate Boundary' = captured
```

The notebook also fetches the platform's **final** polygons live from the KML
endpoint in `ab_platform_data.xlsx`, so it needs network access to the platform.

## Running

```bash
pip install pandas openpyxl shapely nbclient nbformat
# open in Jupyter/VS Code and Run All, or:
python -m nbclient gap_platform_vs_validation.ipynb
```

Notebook outputs are stripped before committing (they embed plot coordinates and
submission IDs). Re-run locally to regenerate; **clear outputs again before
committing**.
