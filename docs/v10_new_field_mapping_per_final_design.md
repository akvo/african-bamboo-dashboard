You are an expert Django/React developer. Refactor the `plot-detail-panel` to fetch and display plot details and attachments based on raw submission data.

## Objective
Wire up the following components to display plot information from `Submission.raw_data`:
- `plot-details-card` — plot details
- `plot-header-card` — plot header information
- `attachment-card` — title deed images

---

## Implementation Plan

### Phase 1: Backend — Models & Migration

#### Step 1.1: Extend Submission Model
Add fields to `Submission` in `backend/api/v1/v1_odk/models.py`:
- `updated_by` (ForeignKey to `SystemUser`, nullable, SET_NULL)
- `updated_at` (DateTimeField, nullable, blank=True) — **not** `auto_now`, set explicitly

**Set in `SubmissionViewSet.perform_update()`** — when a validator approves, rejects, or reverts a submission:
```python
serializer.save(
    updated_by=self.request.user,
    updated_at=timezone.now(),
)
```

This ensures `updated_by`/`updated_at` reflect the last **validator action**, not sync or other internal saves.

Generate migration: `python manage.py makemigrations v1_odk`

#### Step 1.2: Add `area_ha` to Plot Model
Add to `Plot` in `backend/api/v1/v1_odk/models.py`:
- `area_ha` (FloatField, nullable) — pre-computed area in hectares

**Computed at:**
- Sync time (when plots are created/updated from submissions)
- `reset_polygon` action (when polygon is re-derived from raw_data)
- Geometry edit save (when user edits polygon on the map)

This avoids expensive coordinate projection (pyproj) on every detail request.

#### Step 1.3: Create FieldSettings & FieldMapping Models
Add to `backend/api/v1/v1_odk/models.py`:

**`FieldSettings`**
| Field | Type | Notes |
|-------|------|-------|
| `id` | AutoField | Primary key |
| `name` | CharField(max_length=125, unique) | Standardized field name |

**`FieldMapping`**
| Field | Type | Notes |
|-------|------|-------|
| `id` | AutoField | Primary key |
| `field` | ForeignKey → `FieldSettings` | CASCADE, related_name=`mappings` |
| `form` | ForeignKey → `FormMetadata` | CASCADE, related_name=`field_mappings` |
| `form_question` | ForeignKey → `FormQuestion` | CASCADE |

**Unique constraint:** `(field, form)` — one mapping per field per form.

#### Step 1.4: Seed FieldSettings
Create management command `seed_field_settings.py` that seeds:
```
enumerator, farmer, age_of_farmer, phone_number
```

> **Note:** Region, sub-region, start/end dates, and other structural fields are handled via `FormMetadata` field specs (e.g. `region_field`, `sub_region_field`) and do not need `FieldSettings` entries. Only fields displayed in the plot detail panel's "Detail Fields" section are seeded here.

Add to Docker entrypoint or `docker-compose` startup so it runs after migrations.

---

### Phase 2: Backend — Serializer & API Changes

#### Step 2.1: Area Calculation Utility
Create `backend/api/v1/v1_odk/utils/area_calc.py`:
- Function `calculate_area_ha(polygon_string)`:
  - Parse `"lng lat alt accuracy;lng lat alt accuracy;..."` format
  - Extract (lon, lat) pairs
  - Use `shapely.Polygon` + `pyproj.Transformer` (WGS84 → UTM) to compute area  - Return area in hectares (m² / 10000), rounded to 2 decimals
  - Return `None` if parsing fails or < 3 points

Add `shapely` and `pyproj` to `requirements.txt`.

**Integration points** — call `calculate_area_ha()` and store result in `Plot.area_ha`:
1. In `FormMetadataViewSet.sync()` when creating/updating plots
2. In `PlotViewSet.reset_polygon()` after re-deriving polygon
3. In `PlotViewSet.partial_update()` after saving edited geometry

#### Step 2.2: Update SubmissionDetailSerializer
Modify `SubmissionDetailSerializer` in `serializers.py`:

1. **Add `field_mapped_data`** (SerializerMethodField):
   - Query `FieldMapping` for the submission's form
   - For each mapping, resolve `raw_data[form_question.name]` using option lookups
   - Return dict: `{ field_settings.name: { "value": resolved_value, "raw_value": original_raw_value, "label": question.label } }`
   - `value` = resolved label (e.g. `"John Doe"` for enumerator)
   - `raw_value` = original value from raw_data (e.g. `"enum_004"` for enumerator)
   - For non-select fields, `value` and `raw_value` are the same

2. **Add `area_ha`** (SerializerMethodField):
   - Read from `submission.plot.area_ha` (pre-computed, stored on Plot)
   - No on-the-fly calculation needed

3. **Add `attachments`** (SerializerMethodField):
   - Extract `raw_data._attachments` list
   - For each attachment, return:
     ```python
     {
         "question_xpath": str,
         "media_file_basename": str,
         "local_url": str,  # built from uid + extension
         "question_label": str,  # resolved from FormQuestion
     }
     ```
   - Match `question_xpath` to `FormQuestion.name` for label

4. **Add `rejection_reason`** (SerializerMethodField):
   - Already exists as `reviewer_notes` — rename to `rejection_reason` for clarity, or keep both

5. **Add `updated_by_name`** (SerializerMethodField):
   - Return `submission.updated_by.name` if set

Update `fields` list to include all new fields.

#### Step 2.3: FieldSettings & FieldMapping API
- Register `FieldSettings` and `FieldMapping` in Django admin
- `GET /api/v1/odk/field-settings/` — list all FieldSettings (used by the Detail Fields tab to render rows)
- `GET /api/v1/odk/field-mappings/?form_id={asset_uid}` — list current mappings for a form
- `PUT /api/v1/odk/field-mappings/{form_asset_uid}/` — bulk upsert mappings for a form (accepts `{ field_name: form_question_id }` dict, creates/updates/deletes as needed)

---

### Phase 3: Backend — Tests

#### Step 3.1: Model Tests
File: `backend/api/v1/v1_odk/tests/test_models.py` (extend existing)
- Test `FieldSettings` creation and `name` uniqueness constraint
- Test `FieldMapping` creation and `(field, form)` unique-together constraint
- Test `FieldMapping` CASCADE deletion when `FieldSettings` is deleted
- Test `FieldMapping` CASCADE deletion when `FormMetadata` is deleted
- Test `Submission.updated_by` / `updated_at` fields default to `None`
- Test `Plot.area_ha` field defaults to `None`

#### Step 3.2: Area Calculation Tests
File: `backend/api/v1/v1_odk/tests/tests_area_calc.py`
- Test valid polygon string → correct hectare value
- Test invalid/empty polygon string → `None`
- Test polygon with < 3 points → `None`
- Test real coordinates from sample data (expected ~0.12 ha)
- Test polygon string with trailing semicolon
- Test result is rounded to 2 decimal places

#### Step 3.3: Submission Detail Endpoint Tests
File: `backend/api/v1/v1_odk/tests/tests_submission_detail_endpoint.py`
- Test `field_mapped_data` returns mapped fields with correct resolved values and labels
- Test `field_mapped_data` resolves `select_one` options to labels
- Test `field_mapped_data` returns empty dict when no `FieldMapping` exists for a form
- Test `area_ha` is read from `Plot.area_ha` and returned in response
- Test `area_ha` is `None` when plot has no computed area
- Test `attachments` list contains `local_url`, `question_xpath`, `media_file_basename`, `question_label`
- Test `attachments` resolves `question_xpath` to `FormQuestion.label` for `question_label`
- Test `attachments` returns empty list when `raw_data` has no `_attachments`
- Test `rejection_reason` returns `reason_text` from latest `RejectionAudit`
- Test `rejection_reason` is `None` when no audits exist
- Test `updated_by_name` returns validator name after approval/rejection
- Test `updated_by_name` is `None` for submissions that have never been reviewed

#### Step 3.4: Submission Update Endpoint Tests (updated_by/updated_at)
File: `backend/api/v1/v1_odk/tests/tests_submission_update_endpoint.py` (extend existing or new)
- Test approve sets `updated_by` to current user and `updated_at` to current time
- Test reject sets `updated_by` to current user and `updated_at` to current time
- Test revert to pending sets `updated_by` to current user and `updated_at` to current time
- Test `updated_by`/`updated_at` are not modified during sync (internal save)

#### Step 3.5: Area Calculation Integration Tests
File: `backend/api/v1/v1_odk/tests/tests_area_ha_integration.py`
- Test `Plot.area_ha` is computed and stored during sync
- Test `Plot.area_ha` is recomputed on `reset_polygon` action
- Test `Plot.area_ha` is recomputed on geometry edit (`partial_update` with new `polygon_wkt`)
- Test `Plot.area_ha` is `None` when polygon string is invalid

#### Step 3.6: FieldSettings Endpoint Tests
File: `backend/api/v1/v1_odk/tests/tests_field_settings_endpoint.py`
- Test `GET /api/v1/odk/field-settings/` returns all seeded field settings
- Test list is read-only (POST/PUT/DELETE return 405)
- Test unauthenticated request returns 401

#### Step 3.7: FieldMapping Endpoint Tests
File: `backend/api/v1/v1_odk/tests/tests_field_mappings_endpoint.py`
- Test `GET /api/v1/odk/field-mappings/?form_id={asset_uid}` returns mappings for a form
- Test `GET` with no `form_id` returns 400 or empty list
- Test `GET` returns empty list when no mappings exist for a form
- Test `PUT /api/v1/odk/field-mappings/{asset_uid}/` creates new mappings
- Test `PUT` updates existing mappings (changes `form_question`)
- Test `PUT` deletes mappings when field is set to `null`
- Test `PUT` with invalid `form_question_id` returns 400
- Test `PUT` with field name not in `FieldSettings` returns 400
- Test unauthenticated request returns 401

#### Step 3.8: Seed Command Tests
File: `backend/api/v1/v1_odk/tests/tests_seed_field_settings_command.py`
- Test command creates all expected `FieldSettings` entries
- Test command is idempotent (running twice doesn't create duplicates)

---

## Frontend Changes

### Phase 4: Refactor PlotDetailPanel

#### Step 4.1: Restructure PlotDetailPanel Layout
**File:** `frontend/src/components/map/plot-detail-panel.js`

Replace the current flat layout with the card-based design:

```
PlotDetailPanel
├── PlotHeaderCard (sticky top)
│   ├── Back button
│   ├── Alert banner (flagged reason)
│   ├── Status badge + menu
│   ├── Plot ID + last checked info
│   └── Tabs: [Details] [Attachments]
├── ScrollArea (tab content)
│   ├── Tab: Details → PlotDetailsCard
│   └── Tab: Attachments → AttachmentCard[] (list)
└── Action buttons (sticky bottom)
```

**Changes:**
- Remove the existing duplicate header (back button at line 85-94)
- Remove the inline metadata grid (lines 100-160)
- Remove the inline rejection history section (lines 174-204)
- Wire `PlotHeaderCard` with real props from `plot` and `submission`
- Use `PlotHeaderCard`'s tab system to switch between Details and Attachments
- Move `PlotDetailsCard` and `AttachmentCard` rendering into tab content
- Lift `activeTab` state to `PlotDetailPanel` so tab switching controls content

#### Step 4.2: Wire PlotHeaderCard with Real Data
**File:** `frontend/src/components/card/plot-header-card.js`

**Current state:** All props have hardcoded defaults.

**Required prop wiring (from PlotDetailPanel):**
| Prop | Source |
|------|--------|
| `plotId` | `plot.plot_name` or `plot.instance_name` |
| `status` | `getPlotStatus(plot)` |
| `alertMessage` | Generic text `"Plot overlap detected"` when `plot.flagged_for_review` is `true` |
| `alertTooltip` | `plot.flagged_reason` — full detail shown on hover via `Tooltip` component |
| `lastCheckedBy` | `submission.updated_by_name` or latest `rejection_audits[0].validator_name` |
| `lastCheckedAt` | Format `submission.updated_at` or `rejection_audits[0].rejected_at` |
| `onBack` | `onBack` handler |
| `onMenuClick` | Future — no-op for now |
| `defaultTab` | `"details"` |

**Changes to component:**
- Remove hardcoded default prop values
- Accept `onTabChange` callback prop to lift tab state up
- Accept `children` for tab content rendering, OR accept `detailsContent` and `attachmentsContent` render props
- Update `AlertBanner` to wrap text in a `Tooltip` (from shadcn/ui) — shows `alertTooltip` on hover with the full `flagged_reason` detail, while the banner itself displays a short generic message like "Plot overlap detected"

**New prop signature:**
```jsx
PlotHeaderCard({
  plotId,
  status,
  alertMessage,
  alertTooltip,    // full flagged_reason shown on hover
  lastCheckedBy,
  lastCheckedAt,
  onBack,
  onMenuClick,
  activeTab,
  onTabChange,
  detailsContent,
  attachmentsContent,
})
```

#### Step 4.3: Wire PlotDetailsCard with Submission Data
**File:** `frontend/src/components/card/plot-details-card.js`

**Current state:** All props have hardcoded sample values.

**Required prop wiring (from submission response):**
| Prop | Source |
|------|--------|
| `region` | `plot.region` (denormalized on Plot model via `FormMetadata.region_field`) |
| `area` | `submission.area_ha` |
| `enumerator.name` | `fieldMappedData.enumerator.value` (resolved `FormOption.label`) |
| `enumerator.idNumber` | `fieldMappedData.enumerator.raw_value` (`FormOption.value`, e.g. `"enum_004"`) |
| `farmer.name` | `fieldMappedData.farmer.value` |
| `farmer.age` | `fieldMappedData.age_of_farmer.value` |
| `farmer.phone` | `fieldMappedData.phone_number.value` |
| `notes` | `submission.rejection_reason` or `submission.reviewer_notes` |
| `onEditPolygon` | `onStartEditing` handler from parent |
| `onSeeTitleDeed` | Switch to Attachments tab |

**Changes to component:**
- Remove all hardcoded default prop values
- Handle `null`/`undefined` gracefully — hide sections when data is missing
- Format date values (`start`, `end`) from ISO to locale display format
- `onSeeTitleDeed` should trigger tab switch to "attachments"

**New prop signature:**
```jsx
PlotDetailsCard({
  region,
  area,
  enumerator,      // { name, idNumber } — name from FormOption.label, idNumber from FormOption.value
  farmer,          // { name, age, phone } — from field_mapped_data
  notes,
  onEditPolygon,
  onSeeTitleDeed,
})
```

#### Step 4.4: Wire AttachmentCard with Real Attachments
**File:** `frontend/src/components/card/attachment-card.js`

**Current state:** Single card with hardcoded sample data.

**Required changes:**
- Remove hardcoded default prop values
- Render one `AttachmentCard` per attachment from `submission.attachments[]`
- Handle image loading states (skeleton while loading)
- Handle missing/broken images gracefully (fallback placeholder)

**Prop mapping per attachment:**
| Prop | Source |
|------|--------|
| `filename` | `attachment.media_file_basename` |
| `imageUrl` | `attachment.local_url` (proxied through Next.js) |
| `caption` | `attachment.question_label` (e.g., "Title Deed First Page") |
| `sourceUrl` | — (remove, not needed for local URLs) |

**New prop signature:**
```jsx
AttachmentCard({
  filename,
  imageUrl,
  caption,
  onEdit,       // optional, future use
})
```

**In PlotDetailPanel, render attachments tab:**
```jsx
{(submission?.attachments || []).map((att, i) => (
  <AttachmentCard
    key={att.question_xpath || i}
    filename={att.media_file_basename}
    imageUrl={att.local_url}
    caption={att.question_label}
  />
))}
```

#### Step 4.5: Data Mapping Helper
**File:** `frontend/src/lib/field-mapping.js` (new)

Create a helper to extract field-mapped values from the submission response:

```jsx
export function extractPlotDetails(submission) {
  const mapped = submission?.field_mapped_data || {};
  const getValue = (key) => mapped[key]?.value ?? null;
  const getRawValue = (key) => mapped[key]?.raw_value ?? null;

  return {
    region: submission?.plot?.region,
    area: submission?.area_ha,
    enumerator: {
      name: getValue("enumerator"),
      idNumber: getRawValue("enumerator"),
    },
    farmer: {
      name: getValue("farmer"),
      age: getValue("age_of_farmer"),
      phone: getValue("phone_number"),
    },
    notes: submission?.rejection_reason,
    attachments: submission?.attachments || [],
  };
}
```

#### Step 4.6: Add Tabs to Configure Dialog (Forms Page)
**File:** `frontend/src/app/dashboard/forms/page.js`

Add a `Tabs` component inside the existing "Configure Field Mappings" dialog to separate the two mapping concerns:

```
Dialog: "Configure Field Mappings — {form.name}"
├── Tab: "Plot Structure"
│   └── (existing fields: polygon, region, sub-region, plot name, filters)
└── Tab: "Detail Fields"
    └── (new: FieldSettings → FormQuestion mapping UI)
```

**Tab definitions:**

| Tab | Label | Description (shown below tab bar) |
|-----|-------|-------------|
| 1 | **Plot Structure** | Define how raw submissions are converted into plots — geometry source, location hierarchy, naming, and available filters. |
| 2 | **Detail Fields** | Map form questions to standardized display fields shown in the plot detail panel. |

**Plot Structure tab** — no changes to content, just wrap the existing field selectors (polygon, region, sub-region, plot name, filter fields) inside `TabsContent value="structure"`.

**Detail Fields tab** — new UI:
- Fetch available `FieldSettings` from backend: `GET /api/v1/odk/field-settings/`
- For each field setting, show a dropdown to select which `FormQuestion` maps to it
- Pre-populate with existing `FieldMapping` records for this form
- Save creates/updates `FieldMapping` records: `PUT /api/v1/odk/field-mappings/{form_asset_uid}/`

**Detail Fields tab layout:**
```
┌─────────────────────────────────────────┐
│ enumerator      [Select question...  ▼] │
│ farmer          [Select question...  ▼] │
│ age_of_farmer   [Select question...  ▼] │
│ phone_number    [Select question...  ▼] │
└─────────────────────────────────────────┘
```

Each row shows:
- Left: `FieldSettings.name` (human-readable label, e.g., "Region", "Woreda")
- Right: Dropdown of available `FormQuestion` entries for this form, showing `question.label (question.name)`
- Selecting "None" clears the mapping

**Save behavior:**
- The existing "Save Mappings" button in `DialogFooter` saves both tabs' data in a single request, or each tab saves independently — prefer single save for simplicity.

---

### Phase 5: Frontend — Edge Cases & Polish

#### Step 5.1: Loading & Error States
- Show `Skeleton` placeholders in all three cards while `isLoadingSub` is true
- Show inline error message if submission fetch fails
- Show "No field mappings configured" message if `field_mapped_data` is empty

#### Step 5.2: Empty State Handling
- **No attachments:** Show "No attachments" message in Attachments tab
- **No area_ha:** Hide or show "—" in the area field
- **No enumerator/farmer data:** Hide the respective `PersonSection` entirely
- **No notes:** Hide the Notes section
- **No rejection history:** Don't render the rejection audit trail

#### Step 5.3: Date Formatting
- Parse ISO date strings (`"2026-02-24T12:35:29.829+01:00"`) to `DD/MM/YYYY` format
- Use a consistent formatter (Intl.DateTimeFormat or simple utility)

#### Step 5.4: Attachment Count Badge
- Show attachment count on the Attachments tab trigger in `PlotHeaderCard`
- E.g., `Attachments (2)` instead of just `Attachments`

---

## API Contract

### `GET /api/v1/odk/submissions/{uuid}/`

Response (additions to existing `SubmissionDetailSerializer`):

```json
{
  "uuid": "...",
  "form": "aYRqYXmmPLFfbcwC2KAULa",
  "raw_data": { ... },
  "resolved_data": { ... },
  "questions": [ ... ],
  "rejection_audits": [ ... ],
  "reviewer_notes": "...",

  "updated_at": "2026-03-01T10:30:00Z",
  "updated_by_name": "Helen Thompson",

  "area_ha": 0.12,

  "field_mapped_data": {
    "enumerator": { "value": "John Doe", "raw_value": "enum_004", "label": "Enumerator" },
    "farmer": { "value": "Test Sjsus Uwhah", "label": "Full name" },
    "age_of_farmer": { "value": "32", "label": "Age of farmer" },
    "phone_number": { "value": "0909090909", "label": "Phone Number" }
  },

  "attachments": [
    {
      "question_xpath": "Title_Deed_First_Page",
      "question_label": "Title Deed First Page",
      "media_file_basename": "1771932981412.jpg",
      "local_url": "/storage/attachments/{uuid}/{uid}.jpg?key=..."
    },
    {
      "question_xpath": "Title_Deed_Second_Page",
      "question_label": "Title Deed Second Page",
      "media_file_basename": "1771932985899.jpg",
      "local_url": "/storage/attachments/{uuid}/{uid}.jpg?key=..."
    }
  ],

  "rejection_reason": "Polygon does not match title deed boundaries"
}
```

---

## Reference: Raw Submission Data

```json
{
    "_id": 751348950,
    "end": "2026-02-24T12:39:08.876+01:00",
    "_tags": [],
    "_uuid": "603390b5-18f4-4919-9623-f45781710448",
    "index": "0",
    "start": "2026-02-24T12:35:29.829+01:00",
    "_notes": [],
    "kebele": "ET041122",
    "region": "ET04",
    "woreda": "ET0411",
    "_status": "submitted_via_web",
    "know_age": "yes",
    "full_name": "Test Sjsus Uwhah",
    "numpoints": "5",
    "First_Name": "Test",
    "__version__": "vQSe8JuLZsfzYt6JBNcWXn",
    "Phone_Number": "0909090909",
    "_attachments": [
        {
            "uid": "attwJ2wCzEe5pYfp4y6tPcto",
            "filename": "thenewcancer/attachments/c1e75e860fce4f4aa03bfa88d59f54f6/603390b5-18f4-4919-9623-f45781710448/1771932981412.jpg",
            "mimetype": "image/jpeg",
            "is_deleted": false,
            "download_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/751348950/attachments/attwJ2wCzEe5pYfp4y6tPcto/",
            "question_xpath": "Title_Deed_First_Page",
            "download_large_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/751348950/attachments/attwJ2wCzEe5pYfp4y6tPcto/large/",
            "download_small_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/751348950/attachments/attwJ2wCzEe5pYfp4y6tPcto/small/",
            "download_medium_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/751348950/attachments/attwJ2wCzEe5pYfp4y6tPcto/medium/",
            "media_file_basename": "1771932981412.jpg"
        },
        {
            "uid": "attPRGNRVtz3SkKWugSfRuKT",
            "filename": "thenewcancer/attachments/c1e75e860fce4f4aa03bfa88d59f54f6/603390b5-18f4-4919-9623-f45781710448/1771932985899.jpg",
            "mimetype": "image/jpeg",
            "is_deleted": false,
            "download_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/751348950/attachments/attPRGNRVtz3SkKWugSfRuKT/",
            "question_xpath": "Title_Deed_Second_Page",
            "download_large_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/751348950/attachments/attPRGNRVtz3SkKWugSfRuKT/large/",
            "download_small_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/751348950/attachments/attPRGNRVtz3SkKWugSfRuKT/small/",
            "download_medium_url": "https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/data/751348950/attachments/attPRGNRVtz3SkKWugSfRuKT/medium/",
            "media_file_basename": "1771932985899.jpg"
        }
    ],
    "_geolocation": [39.4676995, -0.3301414],
    "current_year": "2026",
    "formhub/uuid": "c1e75e860fce4f4aa03bfa88d59f54f6",
    "Father_s_Name": "Sjsus",
    "_submitted_by": "thenewcancer",
    "age_of_farmer": "32",
    "enumerator_id": "enum_004",
    "instance_name": "enum_004-ET0411-2026-02-24",
    "meta/rootUuid": "uuid:603390b5-18f4-4919-9623-f45781710448",
    "meta/instanceID": "uuid:603390b5-18f4-4919-9623-f45781710448",
    "_submission_time": "2026-02-24T11:39:26",
    "_xform_id_string": "aYRqYXmmPLFfbcwC2KAULa",
    "farmer_owns_phone": "yes",
    "geoshape_accuracy": "0.0",
    "meta/instanceName": "enum_004-ET0411-2026-02-24",
    "Grandfather_s_Name": "Uwhah",
    "_validation_status": {},
    "Title_Deed_First_Page": "1771932981412.jpg",
    "geoshape_accuracy_raw": "0.0;39.4676399",
    "geoshape_input_method": "tapping",
    "Title_Deed_Second_Page": "1771932985899.jpg",
    "validate_polygon_manual": "39.46805687327031 -0.3300974518060684 0.0 0.0;39.4676399 -0.3301053 0.0 0.0;39.46765620922471 -0.3298141434788704 0.0 0.0;39.46803720247954 -0.3297269716858864 0.0 0.0;39.46805687327031 -0.3300974518060684 0.0 0.0",
    "boundary_mapping/boundary_method": "manual",
    "boundary_mapping/manual_boundary": "39.46805687327031 -0.3300974518060684 0.0 0.0;39.4676399 -0.3301053 0.0 0.0;39.46765620922471 -0.3298141434788704 0.0 0.0;39.46803720247954 -0.3297269716858864 0.0 0.0;39.46805687327031 -0.3300974518060684 0.0 0.0",
    "boundary_mapping/gps_accuracy_test/accuracy_1": "4.945",
    "boundary_mapping/gps_accuracy_test/gps_attempt_1": "39.4676995 -0.3301414 54.39999771118164 4.945",
    "boundary_mapping/gps_accuracy_test/final_accuracy": "4.945",
    "boundary_mapping/gps_accuracy_test/accuracy_rating": "Good",
    "boundary_mapping/gps_accuracy_test/final_gps_point": "39.4676995 -0.3301414 54.39999771118164 4.945"
}
```

---

## File Change Summary

### Backend (new/modified)
| File | Action | Description |
|------|--------|-------------|
| `v1_odk/models.py` | Modify | Add `updated_by`, `updated_at` to Submission; add `FieldSettings`, `FieldMapping` models |
| `v1_odk/admin.py` | Modify | Register `FieldSettings`, `FieldMapping` in admin |
| `v1_odk/serializers.py` | Modify | Add `field_mapped_data`, `area_ha`, `attachments`, `updated_by_name` to detail serializer; add `FieldSettingsSerializer`, `FieldMappingSerializer` |
| `v1_odk/views.py` | Modify | Add `FieldSettingsViewSet` (list-only), `FieldMappingViewSet` (list + bulk upsert) |
| `v1_odk/urls.py` | Modify | Register new viewsets |
| `v1_odk/utils/area_calc.py` | New | Polygon area calculation utility |
| `v1_odk/management/commands/seed_field_settings.py` | New | Seeder for default FieldSettings |
| `v1_odk/tests/test_models.py` | Modify | Tests for new model fields and constraints |
| `v1_odk/tests/tests_area_calc.py` | New | Unit tests for area calculation utility |
| `v1_odk/tests/tests_submission_detail_endpoint.py` | New | Tests for field_mapped_data, area_ha, attachments, rejection_reason, updated_by_name |
| `v1_odk/tests/tests_submission_update_endpoint.py` | Modify | Tests for updated_by/updated_at on approve/reject/revert |
| `v1_odk/tests/tests_area_ha_integration.py` | New | Tests for area_ha computation on sync, reset_polygon, geometry edit |
| `v1_odk/tests/tests_field_settings_endpoint.py` | New | Tests for field-settings list endpoint |
| `v1_odk/tests/tests_field_mappings_endpoint.py` | New | Tests for field-mappings CRUD endpoint |
| `v1_odk/tests/tests_seed_field_settings_command.py` | New | Tests for seed command idempotency |
| `requirements.txt` | Modify | Add `shapely`, `pyproj` |

### Frontend (new/modified)
| File | Action | Description |
|------|--------|-------------|
| `components/map/plot-detail-panel.js` | Modify | Restructure to use card components with tab layout |
| `components/card/plot-header-card.js` | Modify | Remove hardcoded defaults, accept real props, lift tab state |
| `components/card/plot-details-card.js` | Modify | Remove hardcoded defaults, accept real submission data |
| `components/card/attachment-card.js` | Modify | Remove hardcoded defaults, handle real attachment URLs |
| `lib/field-mapping.js` | New | Helper to extract field-mapped values from API response |
| `app/dashboard/forms/page.js` | Modify | Add tabs (Plot Structure / Detail Fields) to configure dialog |
