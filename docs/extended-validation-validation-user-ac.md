## Description

To improve plot boundary data quality, several additional validation checks should be implemented. These checks should not reject plots, but instead generate warning flags to support Helen's data quality assessment in the DCU app.

These rules were discussed and confirmed with African Bamboo in January 2026.

When a rule is triggered, the plot should still be accepted but a warning flag should be attached to the plot so it can be reviewed more easily.

## Validation Checks

- Average GPS accuracy > 15m
- Gap between consecutive polygon points > 50m
- Uneven point spacing (Coefficient of Variation of point spacing > 0.5)
- Plot area > 20 ha
- Polygon contains only 6–10 vertices (boundary may be too rough)

> GPS accuracy should be calculated using the accuracy values recorded for the GPS points captured during boundary collection (if available).

## Expected Behaviour

Plots that trigger these rules should receive warning flags, but should not be rejected or blocked. Multiple warnings can apply to the same plot.

## Acceptance Criteria

- [ ] The checks run automatically when a plot is processed.
- [ ] Plots triggering a rule receive a warning flag.
- [ ] Plots are not rejected or blocked due to these warnings.
- [ ] Warnings are visible in the DCU app review interface.
- [ ] Multiple warnings can be attached to a single plot.


## Actual DCU Warning in _notes and predefined question field name called `dcu_validation_warnings` (_notes fallback)

```json
{
  "_id": 757910942,
  "end": "2026-03-17T10:37:31.533+07:00",
  "_tags": [],
  "_uuid": "5c104646-c7d6-4fb1-ab10-3948d57dd18f",
  "index": "0",
  "start": "2026-03-17T10:33:31.072+07:00",
  "_notes": [
    {
      "id": 29557,
      "note": "[DCU Warning] Gap of 671.3m between points 1-2 (threshold: 50m)",
      "date_created": "2026-03-17T05:18:33",
      "date_modified": "2026-03-17T05:18:33"
    },
    {
      "id": 29558,
      "note": "[DCU Warning] Gap of 651.7m between points 2-3 (threshold: 50m)",
      "date_created": "2026-03-17T05:18:34",
      "date_modified": "2026-03-17T05:18:34"
    },
    {
      "id": 29559,
      "note": "[DCU Warning] Gap of 907.0m between points 3-4 (threshold: 50m)",
      "date_created": "2026-03-17T05:18:35",
      "date_modified": "2026-03-17T05:18:35"
    },
    {
      "id": 29560,
      "note": "[DCU Warning] Gap of 536.4m between points 4-5 (threshold: 50m)",
      "date_created": "2026-03-17T05:18:36",
      "date_modified": "2026-03-17T05:18:36"
    },
    {
      "id": 29561,
      "note": "[DCU Warning] Plot area is 44.7ha (threshold: 20ha)",
      "date_created": "2026-03-17T05:18:37",
      "date_modified": "2026-03-17T05:18:37"
    },
    {
      "id": 29562,
      "note": "[DCU Warning] Gap of 671.3m between points 1-2 (threshold: 50m)",
      "date_created": "2026-03-17T05:26:36",
      "date_modified": "2026-03-17T05:26:36"
    },
    {
      "id": 29563,
      "note": "[DCU Warning] Gap of 651.7m between points 2-3 (threshold: 50m)",
      "date_created": "2026-03-17T05:26:37",
      "date_modified": "2026-03-17T05:26:37"
    },
    {
      "id": 29564,
      "note": "[DCU Warning] Gap of 907.0m between points 3-4 (threshold: 50m)",
      "date_created": "2026-03-17T05:26:37",
      "date_modified": "2026-03-17T05:26:37"
    },
    {
      "id": 29565,
      "note": "[DCU Warning] Gap of 536.4m between points 4-5 (threshold: 50m)",
      "date_created": "2026-03-17T05:26:38",
      "date_modified": "2026-03-17T05:26:38"
    },
    {
      "id": 29566,
      "note": "[DCU Warning] Plot area is 44.7ha (threshold: 20ha)",
      "date_created": "2026-03-17T05:26:38",
      "date_modified": "2026-03-17T05:26:38"
    }
  ],
  "kebele": "ET040707",
  "region": "ET04",
  "woreda": "ET0407",
  "_status": "submitted_via_web",
  "know_age": "yes",
  "full_name": "Warningone Warningtwo Warningthree",
  "numpoints": "5",
  "First_Name": "Warningone",
  "__version__": "vEnMwubiA2NakyxicD8UtM",
  "Phone_Number": "0964946401",
  "_attachments": [
    {
      "uid": "attoct77F2SPxgZZaqsBSsKB",
      "filename": "thenewcancer/attachments/c1e75e860fce4f4aa03bfa88d59f54f6/5c104646-c7d6-4fb1-ab10-3948d57dd18f/1773718541019.jpg",
      "mimetype": "image/jpeg",
      "is_deleted": false,
      "download_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/757910942/attachments/attoct77F2SPxgZZaqsBSsKB/",
      "question_xpath": "Title_Deed_Second_Page",
      "download_large_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/757910942/attachments/attoct77F2SPxgZZaqsBSsKB/large/",
      "download_small_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/757910942/attachments/attoct77F2SPxgZZaqsBSsKB/small/",
      "download_medium_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/757910942/attachments/attoct77F2SPxgZZaqsBSsKB/medium/",
      "media_file_basename": "1773718541019.jpg"
    },
    {
      "uid": "attn8m5WNPLRFusZBYRqpADK",
      "filename": "thenewcancer/attachments/c1e75e860fce4f4aa03bfa88d59f54f6/5c104646-c7d6-4fb1-ab10-3948d57dd18f/1773718527115.jpg",
      "mimetype": "image/jpeg",
      "is_deleted": false,
      "download_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/757910942/attachments/attn8m5WNPLRFusZBYRqpADK/",
      "question_xpath": "Title_Deed_First_Page",
      "download_large_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/757910942/attachments/attn8m5WNPLRFusZBYRqpADK/large/",
      "download_small_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/757910942/attachments/attn8m5WNPLRFusZBYRqpADK/small/",
      "download_medium_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/757910942/attachments/attn8m5WNPLRFusZBYRqpADK/medium/",
      "media_file_basename": "1773718527115.jpg"
    }
  ],
  "_geolocation": [
    -7.3912086,
    109.465156
  ],
  "current_year": "2026",
  "formhub/uuid": "c1e75e860fce4f4aa03bfa88d59f54f6",
  "Father_s_Name": "Warningtwo",
  "_submitted_by": "thenewcancer",
  "age_of_farmer": "32",
  "enumerator_id": "enum_006",
  "instance_name": "enum_006-ET0407-2026-03-17",
  "meta/rootUuid": "uuid:9663c44e-288d-4fad-a156-f2bd7440683a",
  "meta/instanceID": "uuid:5c104646-c7d6-4fb1-ab10-3948d57dd18f",
  "_submission_time": "2026-03-17T03:37:43",
  "_xform_id_string": "aYRqYXmmPLFfbcwC2KAULa",
  "farmer_owns_phone": "yes",
  "geoshape_accuracy": "0.0",
  "meta/deprecatedID": "uuid:9663c44e-288d-4fad-a156-f2bd7440683a",
  "meta/instanceName": "enum_006-ET0407-2026-03-17",
  "Grandfather_s_Name": "Warningthree",
  "_validation_status": {},
  "Title_Deed_First_Page": "1773718527115.jpg",
  "geoshape_accuracy_raw": "0.0;-7.393671008672161",
  "geoshape_input_method": "tapping",
  "Title_Deed_Second_Page": "1773718541019.jpg",
  "dcu_validation_warnings": "POINT_GAP_LARGE: 671.3m seg 1-2 (>50m) | POINT_GAP_LARGE: 651.7m seg 2-3 (>50m) | POINT_GAP_LARGE: 907.0m seg 3-4 (>50m) | POINT_GAP_LARGE: 536.4m seg 4-5 (>50m) | AREA_TOO_LARGE: 44.7ha (>20ha)",
  "validate_polygon_manual": "-7.391717302309732 109.36848241835833 0.0 0.0;-7.393671008672161 109.37424279749393 0.0 0.0;-7.399527088621828 109.37449023127556 0.0 0.0;-7.396292007220207 109.36693947762251 0.0 0.0;-7.391717302309732 109.36848241835833 0.0 0.0",
  "boundary_mapping/boundary_method": "manual",
  "boundary_mapping/manual_boundary": "-7.391717302309732 109.36848241835833 0.0 0.0;-7.393671008672161 109.37424279749393 0.0 0.0;-7.399527088621828 109.37449023127556 0.0 0.0;-7.396292007220207 109.36693947762251 0.0 0.0;-7.391717302309732 109.36848241835833 0.0 0.0",
  "boundary_mapping/gps_accuracy_test/retry_1": "no",
  "boundary_mapping/gps_accuracy_test/accuracy_1": "20",
  "boundary_mapping/gps_accuracy_test/gps_attempt_1": "-7.3912086 109.465156 0.0 20.0",
  "boundary_mapping/gps_accuracy_test/final_accuracy": "20",
  "boundary_mapping/gps_accuracy_test/accuracy_rating": "Poor",
  "boundary_mapping/gps_accuracy_test/final_gps_point": "-7.3912086 109.465156 0.0 20.0"
}
```