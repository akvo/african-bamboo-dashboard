# V8: Dashboard & Map Server-Side Filters

## Overview

Implement server-side filtering for both the Dashboard (`/dashboard`) and Map (`/dashboard/map`) pages. This includes:

1. **Static filters**: region, woreda, status, search, date range — derived from Plot model fields
2. **Dynamic filters**: configurable fields from `Submission.raw_data` (e.g. `enumerator_id`) — select_one/select_multiple question types become filter dropdowns
3. **Field mapping configuration**: extend existing Configure Field Mappings to let admins select which raw_data fields are "filterable"

---

## Current State

### What Exists

**Backend models:**
- `FormMetadata` has field mapping configs: `polygon_field`, `region_field`, `sub_region_field`, `plot_name_field`
- `FormQuestion` stores all form questions with `name`, `label`, `type`
- `FormOption` stores select_one/select_multiple options with `name`, `label`
- `Submission.raw_data` (JSONField) holds all dynamic form values
- `Plot` has denormalized `region` and `sub_region` (populated during sync)

**Backend endpoints:**
- `GET /v1/odk/submissions/` — filters: `asset_uid`, `status` only
- `GET /v1/odk/plots/` — filters: `form_id`, `status`, `search` only
- `POST /v1/odk/plots/export/` — filters: `form_id`, `status`, `search` only

**Frontend:**
- Dashboard `FilterBar` — Form selector works. Region dropdown is empty shell. Date range is static placeholder.
- Map `MapFilterBar` — Form + basemap selectors only
- Map `PlotListPanel` — Search input exists but not wired. Status/sort are client-side.
- Forms page — Has Configure Field Mappings dialog for polygon, region, sub_region, plot_name fields

### Key Architecture Insights

- `Plot.region` and `Plot.sub_region` are denormalized from raw_data during sync — can filter directly
- `FormQuestion` + `FormOption` already store all question metadata — can use for dynamic filter dropdowns
- select_one/select_multiple questions have finite option sets → natural filter candidates
- `enumerator_id` and similar fields live in raw_data → need JSONField filtering on backend

---

## Implementation Plan

### Phase 1: Backend — FormMetadata Filter Fields Configuration

**Goal**: Let admins configure which raw_data fields are used as filters (beyond the existing region/sub_region mapping).

#### 1.1 Add `filter_fields` to FormMetadata model

**File**: `backend/api/v1/v1_odk/models.py`

```python
class FormMetadata(models.Model):
    # ... existing fields ...
    filter_fields = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "List of field names from raw_data "
            "to use as filter dropdowns. Only "
            "select_one/select_multiple types "
            "are supported."
        ),
    )
```

The value will be a simple list of question names, e.g.:
```json
["enumerator_id", "bamboo_species"]
```

#### 1.2 Create migration

```bash
python manage.py makemigrations v1_odk
python manage.py migrate
```

#### 1.3 Update FormMetadataSerializer

**File**: `backend/api/v1/v1_odk/serializers.py`

Add `filter_fields` to the `fields` list in `FormMetadataSerializer.Meta`.

#### 1.4 Update Forms page Configure dialog

**File**: `frontend/src/app/dashboard/forms/page.js`

Add a new multi-select section "Filter fields" in the Configure Field Mappings dialog. Only show questions of type `select_one` or `select_multiple` as options. Store selected field names in `filter_fields`.

---

### Phase 2: Backend — Filter Options Endpoint

**Goal**: Provide distinct values for all filter dropdowns (regions, sub_regions, and dynamic filter fields).

#### 2.1 New endpoint: `GET /v1/odk/plots/filter_options/`

**File**: `backend/api/v1/v1_odk/views.py` — add `@action` on `PlotViewSet`

**Query params**:
- `form_id` (required)
- `region` (optional) — cascade sub_regions to selected region

**Response**:
```json
{
  "regions": ["Amhara", "Oromia", "SNNPR"],
  "sub_regions": ["Bahir Dar", "Gondar"],
  "dynamic_filters": [
    {
      "name": "enumerator_id",
      "label": "Enumerator",
      "type": "select_one",
      "options": [
        { "name": "enum_01", "label": "John Doe" },
        { "name": "enum_02", "label": "Jane Smith" }
      ]
    }
  ]
}
```

**Implementation**:
```python
@action(detail=False, methods=["get"])
def filter_options(self, request):
    form_id = request.query_params.get("form_id")
    if not form_id:
        return Response(
            {"detail": "form_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    form = FormMetadata.objects.get(
        asset_uid=form_id
    )
    qs = Plot.objects.filter(
        form__asset_uid=form_id
    )

    # Static: regions
    regions = list(
        qs.exclude(region="")
        .values_list("region", flat=True)
        .distinct()
        .order_by("region")
    )

    # Static: sub_regions (cascaded by region)
    woreda_qs = qs.exclude(sub_region="")
    region = request.query_params.get("region")
    if region:
        woreda_qs = woreda_qs.filter(region=region)
    sub_regions = list(
        woreda_qs.values_list(
            "sub_region", flat=True
        )
        .distinct()
        .order_by("sub_region")
    )

    # Dynamic: configured filter fields
    dynamic_filters = []
    filter_field_names = form.filter_fields or []
    if filter_field_names:
        questions = FormQuestion.objects.filter(
            form=form,
            name__in=filter_field_names,
        ).prefetch_related("options")
        for q in questions:
            dynamic_filters.append({
                "name": q.name,
                "label": q.label,
                "type": q.type,
                "options": [
                    {
                        "name": opt.name,
                        "label": opt.label,
                    }
                    for opt in q.options.all()
                ],
            })

    return Response({
        "regions": regions,
        "sub_regions": sub_regions,
        "dynamic_filters": dynamic_filters,
    })
```

---

### Phase 3: Backend — Add Filter Params to Existing Endpoints

#### 3.1 SubmissionViewSet — new query params

**File**: `backend/api/v1/v1_odk/views.py` — `get_queryset()`

| Param | Filter | Notes |
|-------|--------|-------|
| `region` | `qs.filter(plot__region=region)` | Via reverse OneToOne |
| `woreda` | `qs.filter(plot__sub_region=woreda)` | Via reverse OneToOne |
| `search` | `Q(plot__plot_name__icontains=s) \| Q(instance_name__icontains=s)` | |
| `start_date` | `qs.filter(submission_time__gte=int(v))` | Epoch ms |
| `end_date` | `qs.filter(submission_time__lte=int(v))` | Epoch ms |
| `filter__<name>=<value>` | `qs.filter(raw_data__<name>=value)` | Dynamic raw_data filters |

**Dynamic filter implementation**:
```python
# Dynamic raw_data filters
# e.g. ?filter__enumerator_id=enum_01
for key, val in self.request.query_params.items():
    if key.startswith("filter__"):
        field_name = key[len("filter__"):]
        # Validate field_name is in form.filter_fields
        if (
            asset_uid
            and field_name in (
                form.filter_fields or []
            )
        ):
            qs = qs.filter(
                **{f"raw_data__{field_name}": val}
            )
```

#### 3.2 PlotViewSet — new query params

**File**: `backend/api/v1/v1_odk/views.py` — `get_queryset()`

| Param | Filter | Notes |
|-------|--------|-------|
| `region` | `qs.filter(region=region)` | Direct field |
| `woreda` | `qs.filter(sub_region=woreda)` | Direct field |
| `start_date` | `qs.filter(submission__submission_time__gte=int(v))` | Via Submission |
| `end_date` | `qs.filter(submission__submission_time__lte=int(v))` | Via Submission |
| `sort` | `name` → `order_by("plot_name")`, `date` → `order_by("-created_at")` | |
| `filter__<name>=<value>` | `qs.filter(submission__raw_data__<name>=val)` | Dynamic |

#### 3.3 Export endpoint — pass new filters

**File**: `backend/api/v1/v1_odk/views.py` — `PlotViewSet.export()`

Add `region`, `woreda`, `start_date`, `end_date`, and dynamic `filters` to the job info dict.

**File**: `backend/api/v1/v1_odk/tasks.py`

Apply the new filters in the export task queryset.

---

### Phase 4: Frontend — Filter Options Hook

#### 4.1 New hook: `useFilterOptions`

**New file**: `frontend/src/hooks/useFilterOptions.js`

```javascript
export function useFilterOptions({ formId, region }) {
  const [options, setOptions] = useState({
    regions: [],
    sub_regions: [],
    dynamic_filters: [],
  });

  useEffect(() => {
    if (!formId) return;
    const params = { form_id: formId };
    if (region) params.region = region;
    api
      .get("/v1/odk/plots/filter_options/", { params })
      .then((res) => setOptions(res.data));
  }, [formId, region]);

  return options;
}
```

---

### Phase 5: Frontend — Dashboard Page Filters

#### 5.1 Update `FilterBar` component

**File**: `frontend/src/components/filter-bar.js`

New props:
```javascript
export function FilterBar({
  regions, sub_regions, dynamicFilters,
  region, woreda, datePreset, dynamicValues,
  onRegionChange, onWoredaChange,
  onDatePresetChange, onDynamicFilterChange,
  onReset,
})
```

UI changes:
- **Region dropdown**: Populate with `regions` array, call `onRegionChange`
- **Woreda dropdown**: Add new, populate with `sub_regions` array (cascaded), call `onWoredaChange`
- **Dynamic filter dropdowns**: For each item in `dynamicFilters`, render a `Select` with the item's `options`. The value maps to `filter__<name>=<option.name>` query param.
- **Date preset**: Wire existing Select (7d/30d/90d) to `onDatePresetChange`
- **Date display**: Compute and show actual date range based on preset
- **Reset button**: Wire to `onReset`

#### 5.2 Update Dashboard page state

**File**: `frontend/src/app/dashboard/page.js`

```javascript
const [region, setRegion] = useState("");
const [woreda, setWoreda] = useState("");
const [datePreset, setDatePreset] = useState("");
const [dynamicValues, setDynamicValues] = useState({});
// e.g. { enumerator_id: "enum_01" }

const { regions, sub_regions, dynamic_filters } = useFilterOptions({
  formId: activeForm?.asset_uid,
  region,
});
```

Compute `startDate`/`endDate` from `datePreset`. Pass all to `useSubmissions`.

#### 5.3 Update `useSubmissions` hook

**File**: `frontend/src/hooks/useSubmissions.js`

Accept and pass new params:
```javascript
export function useSubmissions({
  assetUid, status, search,
  region, woreda,
  startDate, endDate,
  dynamicFilters, // { enumerator_id: "enum_01" }
  limit = 10,
} = {}) {
  // Build params
  const params = { asset_uid: assetUid, limit, offset };
  if (status && status !== "all") params.status = status;
  if (search) params.search = search;
  if (region) params.region = region;
  if (woreda) params.woreda = woreda;
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  // Dynamic filters
  if (dynamicFilters) {
    for (const [key, val] of Object.entries(dynamicFilters)) {
      if (val) params[`filter__${key}`] = val;
    }
  }
}
```

Reset offset when any filter changes.

#### 5.4 Update `useExport` hook

**File**: `frontend/src/hooks/useExport.js`

Pass `region`, `woreda`, `start_date`, `end_date`, and dynamic filters in export request body.

---

### Phase 6: Frontend — Map Page Filters

#### 6.1 Update `MapFilterBar` — add date range

**File**: `frontend/src/components/map/map-filter-bar.js`

Add between form selector and basemap selector:
- **Date preset dropdown** (7 days / 30 days / 90 days) — same UI pattern as dashboard FilterBar
- **Date display** showing computed range
- **Reset button**

New props:
```javascript
export default function MapFilterBar({
  basemap, onBasemapChange,
  datePreset, onDatePresetChange,
  onReset,
})
```

#### 6.2 Wire search in `PlotListPanel`

**File**: `frontend/src/components/map/plot-list-panel.js`

New props: `search`, `onSearchChange`

Wire the existing `<Input>`:
```javascript
<Input
  type="search"
  placeholder="Search"
  value={search}
  onChange={(e) => onSearchChange(e.target.value)}
  className="pl-9"
/>
```

#### 6.3 Update `useMapState` hook — server-side filters

**File**: `frontend/src/hooks/useMapState.js`

Add state:
```javascript
const [datePreset, setDatePreset] = useState("");
```

Compute `startDate`/`endDate` from `datePreset`.

Update `fetchPlots` to pass all filter params to backend:
```javascript
const params = { form_id: formId, limit: 200 };
if (activeTab && activeTab !== "all") params.status = activeTab;
if (search) params.search = search;
if (sortBy) params.sort = sortBy;
if (startDate) params.start_date = startDate;
if (endDate) params.end_date = endDate;
```

Move status/sort/search from client-side filtering in `PlotListPanel` to server-side by including them as fetch params.

#### 6.4 Update `PlotListPanel` — remove client-side filtering

**File**: `frontend/src/components/map/plot-list-panel.js`

Since backend now handles status/sort/search filtering, simplify `filteredPlots` to only add `_status` for display (used by `PlotCardItem`) without filtering:
```javascript
const enrichedPlots = useMemo(() => {
  return plots.map((p) => ({
    ...p,
    _status: getPlotStatus(p),
  }));
}, [plots]);
```

#### 6.5 Update Map page

**File**: `frontend/src/app/dashboard/map/page.js`

Pass `datePreset`/`onDatePresetChange` from `useMapState` to `MapFilterBar`. Pass `search`/`onSearchChange` to `PlotListPanel`.

---

### Phase 7: Frontend — Forms Page Configure Dialog

#### 7.1 Add "Filter fields" section

**File**: `frontend/src/app/dashboard/forms/page.js`

In the Configure Field Mappings dialog, add a new multi-select dropdown after the existing field mappings:

```
Filter fields
[Select filter fields...]
```

Only show questions where `type` starts with `select_` (select_one, select_multiple). These are the only types that produce finite option lists suitable for dropdowns.

State:
```javascript
const [filterFields, setFilterFields] = useState([]);
```

Pre-populate from `form.filter_fields` (array). Save via `updateForm` with `filter_fields: filterFields`.

---

## File Change Summary

### Backend (5 files)

| File | Change |
|------|--------|
| `backend/api/v1/v1_odk/models.py` | Add `filter_fields` JSONField to FormMetadata |
| `backend/api/v1/v1_odk/serializers.py` | Add `filter_fields` to FormMetadataSerializer |
| `backend/api/v1/v1_odk/views.py` | Add `filter_options` action. Add region/woreda/search/date/dynamic filters to SubmissionViewSet and PlotViewSet. Update export action. |
| `backend/api/v1/v1_odk/tasks.py` | Apply new filters in export task queryset |
| `backend/api/v1/v1_odk/tests/` | Tests for new filter params, filter_options endpoint, dynamic filters |

### Frontend (9 files)

| File | Change |
|------|--------|
| `frontend/src/hooks/useFilterOptions.js` | **New** — fetch regions, sub_regions, and dynamic filter options |
| `frontend/src/hooks/useSubmissions.js` | Accept and pass region, woreda, search, dates, dynamic filters |
| `frontend/src/hooks/useMapState.js` | Add datePreset state. Pass status/search/sort/date to fetch. |
| `frontend/src/hooks/useExport.js` | Pass new filters in export body |
| `frontend/src/components/filter-bar.js` | Wire Region/Woreda/dynamic dropdowns, date preset, reset |
| `frontend/src/app/dashboard/page.js` | Add filter state, pass to FilterBar + hooks |
| `frontend/src/components/map/map-filter-bar.js` | Add date preset dropdown + date display + reset |
| `frontend/src/components/map/plot-list-panel.js` | Wire search input. Remove client-side filtering. |
| `frontend/src/app/dashboard/forms/page.js` | Add "Filter fields" multi-select in Configure dialog |

### Migration (1 file)

| File | Change |
|------|--------|
| `backend/api/v1/v1_odk/migrations/00XX_*.py` | Add `filter_fields` to FormMetadata |

---

## Implementation Order

```
Phase 1 → FormMetadata.filter_fields model + migration + serializer
Phase 2 → Backend filter_options endpoint
Phase 3 → Backend filter params on submissions + plots + export
Phase 4 → Frontend useFilterOptions hook
Phase 5 → Dashboard FilterBar + page + useSubmissions + useExport
Phase 6 → Map MapFilterBar + PlotListPanel + useMapState + page
Phase 7 → Forms page Configure dialog (filter fields selector)
```

**Dependencies:**
- Phases 1-3 (backend) have no frontend dependency
- Phases 4-6 (frontend filters) depend on phases 1-3
- Phase 7 (forms config UI) depends on phase 1 only
- Phase 5 and 6 are independent of each other

---

## API Contract Summary

### New: `GET /v1/odk/plots/filter_options/?form_id=<uid>[&region=<region>]`

```json
{
  "regions": ["Amhara", "Oromia"],
  "sub_regions": ["Bahir Dar", "Gondar"],
  "dynamic_filters": [
    {
      "name": "enumerator_id",
      "label": "Enumerator",
      "type": "select_one",
      "options": [
        { "name": "enum_01", "label": "John Doe" }
      ]
    }
  ]
}
```

### Updated: `GET /v1/odk/submissions/`

New query params: `region`, `woreda`, `search`, `start_date` (epoch ms), `end_date` (epoch ms), `filter__<field_name>=<value>`

### Updated: `GET /v1/odk/plots/`

New query params: `region`, `woreda`, `start_date` (epoch ms), `end_date` (epoch ms), `sort` (`name`, `date`), `filter__<field_name>=<value>`

### Updated: `POST /v1/odk/plots/export/`

New body fields: `region`, `woreda`, `start_date`, `end_date`, `dynamic_filters` (object)

### Updated: `PATCH /v1/odk/forms/<asset_uid>/`

New body field: `filter_fields` (array of question names)
