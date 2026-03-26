# v14 — Dashboard Table Sorting

## Goal

Add server-side column sorting to the submissions table on the dashboard page. Priority columns: **Plot ID**, **Reviewed by**, **Start date**, **End date**, **Area (ha)**.

---

## Do We Need a Materialized View?

**No.** A materialized view is unnecessary for this use case. Here is why:

| Concern | Analysis |
|---|---|
| **kobo_id (Plot ID)** | `Submission.kobo_id` — regular model field, directly sortable. Already indexed via `unique_together`. |
| **reviewed_by** | `Submission.updated_by` — ForeignKey to User. Sortable via `updated_by__name` (annotation or join). |
| **start / end** | Stored in `Submission.raw_data` (JSONField) as `raw_data.start` / `raw_data.end`. These are ISO-8601 strings — sortable via JSON key lookups on PostgreSQL. |
| **area_ha** | `Plot.area_ha` — FloatField on the related Plot model. Sortable via `plot__area_ha`. |
| **Dataset size** | Submissions are paginated (10/page) and scoped to a single form. Typical forms have hundreds to low thousands of submissions — well within PostgreSQL's ability to sort on-the-fly. |

**Conclusion:** All priority columns are sortable via standard Django ORM ordering with no materialized views, no denormalization, and no schema changes. PostgreSQL handles JSON key sorting natively (`->>`), and the related-model fields (`updated_by__name`, `plot__area_ha`) are simple joins.

If performance becomes an issue later (unlikely at current scale), adding a GIN index on `raw_data` or extracting `start`/`end` into model fields would be the appropriate next step — still not a materialized view.

---

## Implementation Plan

### Phase 1: Backend — Add `ordering` Query Parameter

**File:** `backend/api/v1/v1_odk/views.py` — `SubmissionViewSet`

1. Accept an `ordering` query parameter in `get_queryset()`.
2. Validate against an allowlist of sortable fields.
3. Apply the ordering to the queryset.

**Allowed ordering fields:**

| Query value | ORM ordering expression |
|---|---|
| `kobo_id` | `kobo_id` |
| `reviewed_by` | `updated_by__name` (with `NULLS LAST`) |
| `start` | `KeyTextTransform("start", "raw_data")` (annotated) |
| `end` | `KeyTextTransform("end", "raw_data")` (annotated) |
| `area_ha` | `plot__area_ha` (with `NULLS LAST`) |

**Sorting convention:** Prefix with `-` for descending (DRF standard). Example: `?ordering=-start`.

**Default ordering:** Keep existing `-submission_time` when no `ordering` param is provided.

**Implementation detail for JSON fields (`start`, `end`):**

```python
from django.contrib.postgres.fields.jsonb import KeyTextTransform

# Annotate for sorting
qs = qs.annotate(
    sort_start=KeyTextTransform("start", "raw_data"),
    sort_end=KeyTextTransform("end", "raw_data"),
)
# Then order_by("sort_start") or order_by("-sort_start")
```

Since `start`/`end` are ISO-8601 datetime strings (e.g., `"2025-01-15T08:30:00.000+03:00"`), lexicographic sorting on the text value works correctly for ordering.

**Null handling:** Use `F(...).asc(nulls_last=True)` / `F(...).desc(nulls_last=True)` to push null values to the end regardless of sort direction.

**Skeleton code:**

```python
ALLOWED_ORDERINGS = {
    "kobo_id": "kobo_id",
    "reviewed_by": "updated_by__name",
    "start": "sort_start",       # annotated
    "end": "sort_end",           # annotated
    "area_ha": "plot__area_ha",
}

def get_queryset(self):
    qs = super().get_queryset()
    # ... existing filters ...

    # Annotate JSON fields for sorting
    qs = qs.annotate(
        sort_start=KeyTextTransform(
            "start", "raw_data"
        ),
        sort_end=KeyTextTransform(
            "end", "raw_data"
        ),
    )

    ordering = self.request.query_params.get(
        "ordering"
    )
    if ordering:
        desc = ordering.startswith("-")
        field = ordering.lstrip("-")
        orm_field = ALLOWED_ORDERINGS.get(field)
        if orm_field:
            expr = F(orm_field)
            if desc:
                expr = expr.desc(nulls_last=True)
            else:
                expr = expr.asc(nulls_last=True)
            qs = qs.order_by(expr)

    return qs
```

### Phase 2: Backend — Tests

**File:** `backend/api/v1/v1_odk/tests/tests_submissions_sorting_endpoint.py`

Test cases:
- Sort by each allowed field (ascending and descending)
- Default ordering when no `ordering` param
- Invalid `ordering` value is ignored (falls back to default)
- Null values sort last in both directions
- Sorting works correctly with pagination (offset/limit)
- Sorting combined with existing filters (status, region, search)

### Phase 3: Frontend — `useSubmissions` Hook

**File:** `frontend/src/hooks/useSubmissions.js`

1. Add `ordering` to the hook's input parameters.
2. Pass `ordering` as a query parameter to the API call.
3. Include `ordering` in the `filterKey` so offset resets when sort changes.

```js
export function useSubmissions({
  assetUid,
  // ...existing params...
  ordering,        // e.g. "kobo_id", "-start"
  limit = 10,
} = {}) {
  // ...

  const filterKey = `${assetUid}-${status}-...-${ordering}`;

  const fetchSubmissions = useCallback(async () => {
    // ...
    const params = { asset_uid: assetUid, limit, offset };
    if (ordering) params.ordering = ordering;
    // ...
  }, [/* ...existing deps..., */ ordering]);
}
```

### Phase 4: Frontend — `SortableHeader` Component Enhancement

**File:** `frontend/src/components/table-view.js`

Enhance `SortableHeader` to be interactive with icon changes reflecting sort direction:

- **No active sort on this column:** Show `ArrowUpDown` icon (subtle, muted) — indicates column is sortable
- **Ascending sort active (value sent: `"field"`):** Show `ArrowUp` icon — click requests ascending order
- **Descending sort active (value sent: `"-field"`):** Show `ArrowDown` icon — click requests descending order

**Click cycle:** inactive -> ascending (`ArrowUp`) -> descending (`ArrowDown`) -> clear (back to `ArrowUpDown`)

```jsx
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

export function SortableHeader({ children, columnKey, currentSort, onSort }) {
  const isActive = currentSort?.replace("-", "") === columnKey;
  const isDesc = isActive && currentSort?.startsWith("-");
  const isAsc = isActive && !isDesc;

  const handleClick = () => {
    if (!isActive) {
      onSort(columnKey);           // first click: ascending (ArrowUp)
    } else if (isAsc) {
      onSort(`-${columnKey}`);     // second click: descending (ArrowDown)
    } else {
      onSort(null);                // third click: clear sort
    }
  };

  let Icon = ArrowUpDown;          // default: not sorted
  let iconClass = "size-3.5 text-muted-foreground/50";
  if (isAsc) {
    Icon = ArrowUp;                // ascending
    iconClass = "size-3.5";
  } else if (isDesc) {
    Icon = ArrowDown;              // descending
    iconClass = "size-3.5";
  }

  return (
    <button
      type="button"
      className="flex items-center gap-1 hover:text-foreground"
      onClick={handleClick}
    >
      <span>{children}</span>
      <Icon className={iconClass} />
    </button>
  );
}
```

**Icon summary:**

| State | Icon | Meaning |
|---|---|---|
| Not sorted | `ArrowUpDown` (muted) | Column is sortable, click to sort |
| Ascending | `ArrowUp` | Currently sorted A-Z / oldest-first / smallest-first |
| Descending | `ArrowDown` | Currently sorted Z-A / newest-first / largest-first |

### Phase 5: Frontend — Wire Up Dashboard Page

**File:** `frontend/src/app/dashboard/page.js`

1. Add `ordering` state: `const [ordering, setOrdering] = useState(null);`
2. Pass `ordering` to `useSubmissions()`.
3. Pass `ordering` and `setOrdering` (as `onSort`) to `SubmissionsTable`.

**File:** `frontend/src/components/submissions-table.js`

1. Accept `ordering` and `onSort` props.
2. Use `SortableHeader` for the five priority columns:

```jsx
{
  key: "kobo_id",
  header: (
    <SortableHeader
      columnKey="kobo_id"
      currentSort={ordering}
      onSort={onSort}
    >
      Plot ID
    </SortableHeader>
  ),
  sticky: true,
  // ...cell unchanged
},
{
  key: "reviewed_by",
  header: (
    <SortableHeader columnKey="reviewed_by" currentSort={ordering} onSort={onSort}>
      Reviewed by
    </SortableHeader>
  ),
  // ...
},
{
  key: "start",
  header: (
    <SortableHeader columnKey="start" currentSort={ordering} onSort={onSort}>
      Start date
    </SortableHeader>
  ),
  // ...
},
{
  key: "end",
  header: (
    <SortableHeader columnKey="end" currentSort={ordering} onSort={onSort}>
      End date
    </SortableHeader>
  ),
  // ...
},
{
  key: "area_ha",
  header: (
    <SortableHeader columnKey="area_ha" currentSort={ordering} onSort={onSort}>
      Area (ha)
    </SortableHeader>
  ),
  // ...
},
```

3. Non-sortable columns (status, region, sub_region, dynamic) keep plain text headers — no sort indicator.

### Phase 6: Frontend — Tests

**File:** `frontend/__tests__/submissions-table-sorting.test.js`

Test cases:
- SortableHeader renders `ArrowUpDown` when inactive
- SortableHeader renders `ArrowUp` when ascending
- SortableHeader renders `ArrowDown` when descending
- Clicking cycles through: asc (`ArrowUp`) -> desc (`ArrowDown`) -> clear (`ArrowUpDown`)
- `useSubmissions` includes `ordering` in API calls
- Sort state resets pagination to page 1

---

## Files to Modify

| File | Change |
|---|---|
| `backend/api/v1/v1_odk/views.py` | Add `ordering` param handling in `get_queryset()` |
| `backend/api/v1/v1_odk/tests/tests_submissions_sorting_endpoint.py` | New test file |
| `frontend/src/hooks/useSubmissions.js` | Add `ordering` param |
| `frontend/src/components/table-view.js` | Enhance `SortableHeader` with interactive icons |
| `frontend/src/components/submissions-table.js` | Use `SortableHeader` on priority columns |
| `frontend/src/app/dashboard/page.js` | Add `ordering` state, pass to hook and table |
| `frontend/__tests__/submissions-table-sorting.test.js` | New test file |

---

## UX Behavior

- **Click column header** -> sort ascending (shows `ArrowUp`)
- **Click again** -> sort descending (shows `ArrowDown`)
- **Click again** -> clear sort, revert to default order (shows `ArrowUpDown`)
- **Non-sortable columns** (status, region, sub_region, dynamic) have no sort indicator
- **Changing sort resets to page 1**

---

## No Schema Changes Required

- No new models
- No migrations
- No materialized views
- No new database indexes (existing indexes and joins are sufficient at current scale)
