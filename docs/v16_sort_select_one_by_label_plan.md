# v16 — Sort select_one Sortable Fields by Option Label

## Problem

When a `select_one` field (e.g., `enumerator_id`) is configured as a sortable field via `FormMetadata.sortable_fields`, clicking the sort button in the submissions table produces an order that doesn't match what users see.

**Why:** The backend sorts by the raw option **name** stored in `Submission.raw_data` (e.g., `"enum_z"`, `"enum_a"`), but the frontend displays the resolved option **label** (e.g., `"Alice"`, `"Zara"`) via `resolved_data`. The raw name order and label order can be completely different.

### Example

| raw_data value | FormOption.label | Raw sort (current) | Label sort (expected) |
|---|---|---|---|
| `enum_z` | Alice | 1st (a < z) → wrong | 1st ✓ |
| `enum_m` | Bob | 2nd | 2nd ✓ |
| `enum_a` | Zara | 3rd | 3rd ✓ |

Current behavior sorts: `enum_a` (Zara), `enum_m` (Bob), `enum_z` (Alice) — users see Zara first when expecting Alice.

---

## Root Cause

**File:** `backend/api/v1/v1_odk/views.py`, method `_apply_dynamic_ordering()` (lines 710–737)

```python
def _apply_dynamic_ordering(
    self, qs, asset_uid, field, desc
):
    # ...
    ann_key = f"sort_dyn_{field}"
    qs = qs.annotate(
        **{
            ann_key: KeyTextTransform(
                field, "raw_data"
            )
        }
    )
    expr = F(ann_key)          # ← sorts by RAW value
    # ...
```

`KeyTextTransform(field, "raw_data")` extracts `raw_data->>'enumerator_id'` which returns the raw option name. There is no lookup to `FormOption.label`.

---

## Data Model Recap

```
FormMetadata
  ├── sortable_fields: ["enumerator_id", ...]   (JSONField)
  └── questions (FK)
        └── FormQuestion (name="enumerator_id", type="select_one")
              └── options (FK)
                    ├── FormOption(name="enum_z", label="Alice")
                    ├── FormOption(name="enum_m", label="Bob")
                    └── FormOption(name="enum_a", label="Zara")

Submission
  └── raw_data: {"enumerator_id": "enum_z", ...}   (JSONField)
```

The frontend resolves `"enum_z"` → `"Alice"` via `build_option_lookup()` + `resolve_value()` in the serializer. The sort must match this resolution.

---

## Solution: Subquery Annotation

For `select_one` fields, add a `Subquery` annotation that resolves the raw option name to `FormOption.label`, then sort by the resolved label.

### Generated SQL

```sql
SELECT *,
  (raw_data ->> 'enumerator_id') AS sort_dyn_enumerator_id,
  (
    SELECT fo.label
    FROM form_options fo
    WHERE fo.question_id = 42
      AND fo.name = (submissions.raw_data ->> 'enumerator_id')
    LIMIT 1
  ) AS sort_label_enumerator_id
FROM submissions
WHERE form_id = ...
ORDER BY sort_label_enumerator_id ASC NULLS LAST,
         submission_time DESC,
         id ASC
```

### Why Subquery over Case/When

| Approach | Pros | Cons |
|---|---|---|
| **Subquery** | Data-driven, no Python loop, works with any option count | One correlated subquery per row |
| **Case/When** | Single expression | Must load all options into Python, SQL grows with option count |

At current scale (<100 rows per form), both are fine. Subquery is cleaner and doesn't require fetching all option rows into Python memory.

### Scope

- **`select_one` fields:** Sort by `FormOption.label` via Subquery
- **`select_multiple` fields:** Keep sorting by raw value (multiple space-separated values make label resolution ambiguous)
- **Non-select fields** (text, integer, etc.): Keep sorting by raw value (no options to resolve)

---

## Implementation Plan

### Phase 1: Backend — Update `_apply_dynamic_ordering()`

**File:** `backend/api/v1/v1_odk/views.py`

#### 1a. Add imports

```python
# Line 7: add Subquery and OuterRef
from django.db.models import (
    Count,
    F,
    OuterRef,
    Q,
    Subquery,
)

# Lines 34-36: add FormOption
from api.v1.v1_odk.models import (
    Farmer,
    FarmerFieldMapping,
    FieldMapping,
    FieldSettings,
    FormMetadata,
    FormOption,
    FormQuestion,
    Plot,
    RejectionAudit,
    Submission,
)
```

#### 1b. Modify `_apply_dynamic_ordering()`

```python
def _apply_dynamic_ordering(
    self, qs, asset_uid, field, desc
):
    try:
        form = FormMetadata.objects.get(
            asset_uid=asset_uid
        )
    except FormMetadata.DoesNotExist:
        return qs
    allowed = form.sortable_fields or []
    if field not in allowed:
        return qs
    ann_key = f"sort_dyn_{field}"
    qs = qs.annotate(
        **{
            ann_key: KeyTextTransform(
                field, "raw_data"
            )
        }
    )
    sort_key = ann_key
    # For select_one fields, resolve option
    # label and sort by that instead of raw
    # option name
    question = FormQuestion.objects.filter(
        form=form,
        name=field,
        type="select_one",
    ).first()
    if question:
        label_key = f"sort_label_{field}"
        qs = qs.annotate(
            **{
                label_key: Subquery(
                    FormOption.objects.filter(
                        question=question,
                        name=OuterRef(ann_key),
                    ).values("label")[:1]
                )
            }
        )
        sort_key = label_key
    expr = F(sort_key)
    if desc:
        expr = expr.desc(nulls_last=True)
    else:
        expr = expr.asc(nulls_last=True)
    return qs.order_by(
        expr, "-submission_time", "pk"
    )
```

### Phase 2: Backend — Tests

**File:** `backend/api/v1/v1_odk/tests/tests_submissions_sorting_endpoint.py`

#### 2a. Update existing test fixtures

Add a `select_one` question with options where raw names and labels sort in **opposite** order, to prove sorting uses labels:

```python
# In setUpTestData():
cls.q_enum = FormQuestion.objects.create(
    form=cls.form,
    name="enumerator_id",
    label="Enumerator",
    type="select_one",
)
FormOption.objects.create(
    question=cls.q_enum,
    name="enum_z",
    label="Alice",
)
FormOption.objects.create(
    question=cls.q_enum,
    name="enum_a",
    label="Zara",
)
FormOption.objects.create(
    question=cls.q_enum,
    name="enum_m",
    label="Bob",
)
```

Update `sortable_fields` to include `"enumerator_id"`:
```python
cls.form = FormMetadata.objects.create(
    asset_uid="sort-form",
    name="Sort Test",
    sortable_fields=[
        "First_Name",
        "Father_s_Name",
        "enumerator_id",
    ],
)
```

Update submission `raw_data` to include `enumerator_id` values:
```python
# sub_a: enumerator_id="enum_z" → label "Alice"
# sub_b: enumerator_id="enum_a" → label "Zara"
# sub_c: enumerator_id=None (missing) → null last
```

#### 2b. New test methods

```python
def test_sort_select_one_by_label_asc(self):
    """select_one field sorts by option label,
    not raw value. ASC: Alice < Zara, null last.
    """
    res = self.client.get(
        self.url,
        {"asset_uid": "sort-form",
         "ordering": "enumerator_id"},
        **self.auth,
    )
    uuids = [r["uuid"] for r in res.data["results"]]
    # Alice (sub_a) < Zara (sub_b), null (sub_c) last
    self.assertEqual(
        uuids, ["sort-a", "sort-b", "sort-c"]
    )

def test_sort_select_one_by_label_desc(self):
    """DESC: Zara > Alice, null last."""
    res = self.client.get(
        self.url,
        {"asset_uid": "sort-form",
         "ordering": "-enumerator_id"},
        **self.auth,
    )
    uuids = [r["uuid"] for r in res.data["results"]]
    # Zara (sub_b) > Alice (sub_a), null (sub_c) last
    self.assertEqual(
        uuids, ["sort-b", "sort-a", "sort-c"]
    )

def test_sort_non_select_field_still_uses_raw(self):
    """Text fields still sort by raw value
    (regression guard).
    """
    res = self.client.get(
        self.url,
        {"asset_uid": "sort-form",
         "ordering": "First_Name"},
        **self.auth,
    )
    uuids = [r["uuid"] for r in res.data["results"]]
    # Alpha (sub_b) < Charlie (sub_a), null (sub_c)
    self.assertEqual(
        uuids, ["sort-b", "sort-a", "sort-c"]
    )
```

---

## Files to Modify

| File | Change |
|---|---|
| `backend/api/v1/v1_odk/views.py` | Add `Subquery`, `OuterRef`, `FormOption` imports; update `_apply_dynamic_ordering()` |
| `backend/api/v1/v1_odk/tests/tests_submissions_sorting_endpoint.py` | Add `select_one` fixtures and test methods |

---

## What Stays Unchanged

- `select_multiple` fields: continue sorting by raw value
- Non-select fields (text, integer, etc.): continue sorting by raw value
- Hardcoded `ALLOWED_ORDERINGS` (kobo_id, reviewed_by, start, end, area_ha, region, sub_region): untouched
- Frontend: no changes needed (already displays resolved labels correctly)
- `FormMetadata.sortable_fields` config UI: no changes needed
- Serializer label resolution (`build_option_lookup`, `resolve_value`): untouched

---

## Performance

- Extra `FormQuestion` query: single indexed lookup (`form_id` + `name` + `type`)
- `Subquery` per row: correlated subquery on `form_options` table (`question_id` + `name`), typically <50 options per question
- At current scale (13–19 submissions/form): negligible impact
- At future scale: same mitigations from v15 plan apply (expression index on `raw_data->>'field'` if needed)

---

## Verification

```bash
# Run existing + new sorting tests
docker-compose exec backend python manage.py test \
  api.v1.v1_odk.tests.tests_submissions_sorting_endpoint

# Lint
docker-compose exec backend bash -c "black . && isort . && flake8"
```

Manual test:
1. Configure a `select_one` field as sortable in the forms config page
2. Go to submissions table, click sort on that column
3. Verify order matches the displayed labels, not the raw option names