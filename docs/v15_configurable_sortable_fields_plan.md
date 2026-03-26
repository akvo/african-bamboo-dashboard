# v15 — Configurable Sortable Fields for Submissions Table

## Goal

Allow admins to configure which dynamic columns in the submissions table are sortable, via a new `sortable_fields` setting on FormMetadata. These fields sort server-side via JSON key extraction (`->>`).

---

## SQL & Performance Considerations

### How JSON sorting works in PostgreSQL

```sql
ORDER BY ("submissions"."raw_data" ->> 'First_Name') ASC
LIMIT 10 OFFSET 0
```

The `->>` operator extracts a text value from the JSON column. There is **no index** on any specific JSON key, so PostgreSQL must:
1. Filter rows (by `form_id`, status, region, etc. — these use indexed columns)
2. Extract the JSON value from **every** filtered row
3. Sort **all** filtered rows in memory
4. Apply `LIMIT/OFFSET`

### Text-based sorting caveat

`->>` always returns **text**. This means:
- **ISO-8601 dates** (`start`, `end`): Sort correctly as text — lexicographic order matches chronological order
- **Strings** (`First_Name`, etc.): Sort correctly as text
- **Numbers**: Sort **incorrectly** as text (`"9" > "10"`). Must `Cast` to `FloatField` for numeric question types

### Risk assessment at current scale

| Metric | Value | Impact |
|---|---|---|
| Submissions per form | 13–19 | Negligible — microsecond sort |
| raw_data size per row | ~4 KB | Fits comfortably in memory |
| Form-scoped queries | Always filtered by `form__asset_uid` (indexed) | Small working set |

**Current risk: NONE.** PostgreSQL handles in-memory sort of <100 rows trivially.

### Risk at future scale

| Submissions per form | Risk | Symptom |
|---|---|---|
| < 1,000 | None | Sub-millisecond |
| 1,000–5,000 | Low | Acceptable latency (<50ms) |
| 5,000–50,000 | Moderate | Deep pagination slows (`OFFSET 49990` re-sorts all 50K) |
| 50,000+ | High | Visible latency, memory pressure |

### Mitigations (apply only when needed)

1. **Expression index** (per-field, best bang for buck):
   ```sql
   CREATE INDEX idx_submissions_raw_start
   ON submissions ((raw_data->>'start'));
   ```
   Helps `ORDER BY` on that specific key. Must be created per sortable field.

2. **Extract to model field**: Move heavily-sorted values out of JSON into real columns. Best performance but requires migration + sync logic changes.

3. **GIN index on raw_data**: Does NOT help `ORDER BY ->>`. Only helps containment queries (`@>`). Not useful here.

4. **Materialized view**: Overkill. Only consider at 100K+ rows with complex multi-table joins.

### Implementation safeguard

- Backend validates `ordering` against the form's `sortable_fields` allowlist — prevents arbitrary JSON key scanning
- Only admin-configured fields can be sorted — users cannot sort on random keys
- Max one `ORDER BY` expression per request

---

## Current State

- `FormMetadata.filter_fields` (JSONField) — configures raw_data fields as filter dropdowns
- The forms config page has an "Additional Filter fields" multi-select for `filter_fields`
- The submissions table has 5 hardcoded sortable base columns: Plot ID, Reviewed by, Start date, End date, Area (ha)
- Dynamic columns (from form questions) are NOT sortable

---

## Implementation Plan

### Phase 1: Backend — New Model Field + Migration

**File:** `backend/api/v1/v1_odk/models.py`

Add `sortable_fields` to `FormMetadata` (after `filter_fields`):

```python
sortable_fields = models.JSONField(
    null=True,
    blank=True,
    help_text=(
        "List of raw_data field names that "
        "can be used for sorting in the "
        "submissions table."
    ),
)
```

**Migration:** `python manage.py makemigrations v1_odk`

### Phase 2: Backend — Expose in Serializer

**File:** `backend/api/v1/v1_odk/serializers.py`

Add `"sortable_fields"` to `FormMetadataSerializer.Meta.fields`.

### Phase 3: Backend — Return sortable_fields in List Response

**File:** `backend/api/v1/v1_odk/views.py`

In `SubmissionViewSet.list()`, include `sortable_fields` alongside `questions`:

```python
def list(self, request, *args, **kwargs):
    response = super().list(
        request, *args, **kwargs
    )
    asset_uid = (
        request.query_params.get("asset_uid")
    )
    if asset_uid:
        response.data["questions"] = (
            self._get_form_questions(asset_uid)
        )
        try:
            form = FormMetadata.objects.get(
                asset_uid=asset_uid
            )
            response.data["sortable_fields"] = (
                form.sortable_fields or []
            )
        except FormMetadata.DoesNotExist:
            response.data["sortable_fields"] = []
    else:
        response.data["questions"] = []
        response.data["sortable_fields"] = []
    return response
```

### Phase 4: Backend — Allow Dynamic Field Sorting

**File:** `backend/api/v1/v1_odk/views.py`

Extend ordering logic in `get_queryset()`. When `ordering` doesn't match `ALLOWED_ORDERINGS`, check if it matches the form's `sortable_fields`:

```python
ordering = params.get("ordering")
if ordering:
    desc = ordering.startswith("-")
    field = ordering.lstrip("-")
    orm_field = self.ALLOWED_ORDERINGS.get(field)
    if orm_field:
        # Hardcoded sort (kobo_id, reviewed_by, etc.)
        expr = F(orm_field)
        if desc:
            expr = expr.desc(nulls_last=True)
        else:
            expr = expr.asc(nulls_last=True)
        qs = qs.order_by(expr)
    elif asset_uid:
        # Dynamic sortable field from raw_data
        try:
            form = FormMetadata.objects.get(
                asset_uid=asset_uid
            )
        except FormMetadata.DoesNotExist:
            form = None
        allowed = (
            form.sortable_fields or []
        ) if form else []
        if field in allowed:
            ann_key = f"sort_dyn_{field}"
            qs = qs.annotate(**{
                ann_key: KeyTextTransform(
                    field, "raw_data"
                )
            })
            expr = F(ann_key)
            if desc:
                expr = expr.desc(
                    nulls_last=True
                )
            else:
                expr = expr.asc(
                    nulls_last=True
                )
            qs = qs.order_by(expr)
```

**Note:** The `sort_start` and `sort_end` annotations from Phase 1 (v14) are always applied. Dynamic annotations use `sort_dyn_` prefix to avoid collisions.

**Note:** The `FormMetadata.objects.get()` call here is acceptable because it's already cached in Django's query layer for the same request (the `get_queryset` method already filters by `form__asset_uid` which loads the form). If needed, the form object can be cached on `self` during the request.

### Phase 5: Frontend — useSubmissions Returns sortableFields

**File:** `frontend/src/hooks/useSubmissions.js`

```js
const [sortableFields, setSortableFields] = useState([]);

// In fetchSubmissions:
setSortableFields(res.data.sortable_fields || []);

// In return:
return { ..., sortableFields };
```

### Phase 6: Frontend — SubmissionsTable Uses sortableFields

**File:** `frontend/src/components/submissions-table.js`

Accept `sortableFields` prop. When building dynamic columns, check if the question name is in `sortableFields`:

```jsx
const dynamic = dynamicQuestions.map((q) => ({
  key: q.name,
  header: sortableFields.includes(q.name) ? (
    <SortableHeader
      columnKey={q.name}
      currentSort={ordering}
      onSort={onSort}
    >
      {q.label}
    </SortableHeader>
  ) : (
    q.label
  ),
  // ...cell rendering unchanged
}));
```

### Phase 7: Frontend — Dashboard Page Passes sortableFields

**File:** `frontend/src/app/dashboard/page.js`

```jsx
const {
  data, questions, count, isLoading,
  page, totalPages, setPage, sortableFields,
} = useSubmissions({ ... });

<SubmissionsTable
  ...
  sortableFields={sortableFields}
/>
```

### Phase 8: Frontend — Form Config UI

**File:** `frontend/src/app/dashboard/forms/page.js`

Add a new multi-select dropdown after "Additional Filter fields":

1. **State:** `const [sortableFields, setSortableFields] = useState([]);`
2. **Pre-populate** from `form.sortable_fields` in `handleConfigureClick()`:
   ```js
   setSortableFields(
     Array.isArray(form.sortable_fields) ? form.sortable_fields : [],
   );
   ```
3. **Toggle function:**
   ```js
   function toggleSortableField(name) {
     setSortableFields((prev) =>
       prev.includes(name)
         ? prev.filter((f) => f !== name)
         : [...prev, name],
     );
   }
   ```
4. **Save** in `handleSaveMapping()`:
   ```js
   sortable_fields: sortableFields.length > 0
     ? sortableFields : null,
   ```
5. **UI:** Multi-select dropdown using `formFields` (all question types, not limited to selects). Label: "Sortable fields". Helper text explaining these fields will have sort buttons in the submissions table.

---

## Files to Modify

| File | Change |
|---|---|
| `backend/api/v1/v1_odk/models.py` | Add `sortable_fields` JSONField to FormMetadata |
| `backend/api/v1/v1_odk/migrations/` | New migration |
| `backend/api/v1/v1_odk/serializers.py` | Add to FormMetadataSerializer fields |
| `backend/api/v1/v1_odk/views.py` | Return `sortable_fields` in list response; allow dynamic ordering |
| `frontend/src/hooks/useSubmissions.js` | Return `sortableFields` from API response |
| `frontend/src/components/submissions-table.js` | Accept `sortableFields`, use `SortableHeader` on matching dynamic columns |
| `frontend/src/app/dashboard/page.js` | Pass `sortableFields` to SubmissionsTable |
| `frontend/src/app/dashboard/forms/page.js` | Add "Sortable fields" config UI |

---

## No Breaking Changes

- Existing forms without `sortable_fields` → no dynamic sortable columns (current behavior)
- Hardcoded base column sorting (Plot ID, Reviewed by, Start/End date, Area) is unaffected
- `filter_fields` and `plot_name_field` remain unchanged
- No data migration needed — new field defaults to `null`
