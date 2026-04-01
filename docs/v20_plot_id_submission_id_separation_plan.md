# V20 — Plot ID & Submission ID Separation

**Issue**: #37  
**Date**: 2026-03-31  
**Status**: Implemented  
**Depends on**: AC1 (Rename "Plot ID" → "Submission ID" in ODK app) — DONE

---

## Overview

Previously `plot_id` in the API was `submission.kobo_id` (the Kobo submission number). This conflated two concepts: a **submission** (a single data collection event) and a **plot** (a long-lived physical entity that can have multiple submissions over time).

This feature implements **AC2** (generate Plot ID on approval) and **AC3** (both IDs visible & searchable) using `MainPlot` and `MainPlotSubmission` models.

---

## Data Model

### MainPlot

```python
class MainPlot(models.Model):
    form = models.ForeignKey(
        FormMetadata, on_delete=CASCADE,
        related_name="main_plots",
    )
    uid = models.CharField(
        max_length=255, db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("form", "uid")
```

- `uid` is sequential per form (e.g. `PLT00001`, `PLT00351`)
- Uniqueness is scoped to `(form, uid)` — different forms can each have `PLT00001`
- `FormMetadata.plot_uid_start` controls the minimum UID number

### MainPlotSubmission

```python
class MainPlotSubmission(models.Model):
    main_plot = models.ForeignKey(
        MainPlot, on_delete=CASCADE,
        related_name="submissions",
    )
    submission = models.OneToOneField(
        Submission, on_delete=CASCADE,
        related_name="main_plot_submission",
    )
```

- `OneToOneField` on submission ensures each submission links to at most one MainPlot (race-safe)
- `ForeignKey` on main_plot allows future linking of multiple submissions to one plot (out of scope for now)
- Reverse accessor: `submission.main_plot_submission` (singular, raises `RelatedObjectDoesNotExist` if absent)

---

## Implementation Details

### Plot ID Generation (`utils/plot_id.py`)

**`generate_next_plot_uid(form)`**:
- Scoped per form via `MainPlot.objects.filter(form=form)`
- Uses `Cast(Substr("uid", 4), IntegerField())` + `Max` to find highest numeric suffix
- Respects `form.plot_uid_start` as floor
- Returns format: `PLT00001`, zero-padded to 5 digits

**`create_main_plot_for_submission(submission)`**:
- Returns `None` if submission has no associated `Plot`
- Idempotent: checks `MainPlotSubmission.objects.filter(submission=...)` first
- Both creates wrapped in `transaction.atomic()` — no orphaned `MainPlot` rows on failure
- Retries up to 3 times on `IntegrityError` (concurrent UID race)

**`unlink_main_plot_submission(submission)`**:
- Deletes the `MainPlotSubmission` link
- Retains the `MainPlot` itself (prevents UID gaps, supports future resubmission linking)

### Approval Flow Hook (`views.py` — `perform_update`)

| Transition | Action |
|-----------|--------|
| Pending → Approved | `create_main_plot_for_submission()` |
| Pending → Rejected | No action |
| Approved → Pending (revert) | `unlink_main_plot_submission()` |
| Approved → Rejected | `unlink_main_plot_submission()` |
| Rejected → Pending | No action |

### Serializers

`main_plot_uid` field added to three serializers via `SerializerMethodField`:
- `SubmissionListSerializer` — uses `getattr(obj, "main_plot_submission", None)`
- `SubmissionDetailSerializer` — same pattern
- `PlotSerializer` — traverses `obj.submission.main_plot_submission`

Query optimization: `prefetch_related("main_plot_submission__main_plot")` on both ViewSet querysets.

### Search (`views.py`)

Both `PlotViewSet` and `SubmissionViewSet` search by Plot ID using `Exists` subquery (avoids PostgreSQL `DISTINCT + ORDER BY` conflicts):

```python
plot_uid_match = Exists(
    MainPlotSubmission.objects.filter(
        submission=OuterRef("pk"),
        main_plot__uid__icontains=stripped,
    )
)
```

`_strip_id_prefix` handles `PLT`, `#`, and `AB` prefixes. Returns original value when stripping would produce an empty string.

### Frontend

| Location | Change |
|----------|--------|
| `submissions-table.js` | "Plot ID" column after Submission ID |
| `plot-card-item.js` | Plot ID row below Submission ID (when approved) |
| `plot-header-card.js` | `mainPlotUid` prop, displayed below Submission ID |
| `plot-detail-panel.js` | Passes `mainPlotUid={plot?.main_plot_uid}` to header |
| `map-popup-card.js` | Plot ID shown when available |

### Backfill Command

`python manage.py backfill_plot_ids` — generates Plot IDs for submissions approved before this feature.

Options: `--dry-run`, `--form-id`. Processes in `submission_time` order.

---

## API Response Changes

### `GET /v1/odk/plots/`

```json
{
  "plot_id": "12345",
  "main_plot_uid": "PLT00351",
  "uuid": "...",
  ...
}
```

### `GET /v1/odk/submissions/`

```json
{
  "kobo_id": "12345",
  "main_plot_uid": "PLT00351",
  ...
}
```

`main_plot_uid` is `null` when the submission is not approved.

---

## Files Changed

| File | Change |
|------|--------|
| `models.py` | `MainPlot` (form FK, uid per-form unique), `MainPlotSubmission` (OneToOneField) |
| `admin.py` | Register `MainPlot`, `MainPlotSubmission` |
| `utils/plot_id.py` | `generate_next_plot_uid`, `create_main_plot_for_submission`, `unlink_main_plot_submission` |
| `views.py` | Approval hook, Exists subquery search, prefetch, `_strip_id_prefix` PLT support |
| `serializers.py` | `main_plot_uid` on 3 serializers |
| `management/commands/backfill_plot_ids.py` | Backfill command |
| `migrations/0014_*.py` | Create tables with constraints |
| `tests/tests_plot_id_generation.py` | 13 endpoint tests |
| `tests/tests_plot_id_utils.py` | 7 unit tests |
| `submissions-table.js` | Plot ID column |
| `plot-card-item.js` | Plot ID in card |
| `plot-header-card.js` | Plot ID in header |
| `plot-detail-panel.js` | Pass mainPlotUid prop |
| `map-popup-card.js` | Plot ID in popup |

---

## Test Coverage (20 tests)

| Test | Description |
|------|-------------|
| `test_approve_creates_main_plot` | Approval creates MainPlot with PLT00001 |
| `test_approve_respects_uid_start` | Respects `plot_uid_start=351` |
| `test_approve_sequential` | Sequential UID increment |
| `test_approve_idempotent` | Double-approve doesn't duplicate |
| `test_revert_deletes_link_keeps_main_plot` | Revert unlinks, retains MainPlot |
| `test_reject_no_main_plot` | Rejection creates nothing |
| `test_reject_after_approve_unlinks` | Approve then reject unlinks |
| `test_approve_without_plot_no_error` | No crash without Plot |
| `test_search_by_plot_id` | Search matches MainPlot.uid |
| `test_plot_serializer_includes_main_plot_uid` | PlotSerializer returns field |
| `test_submission_list_includes_main_plot_uid` | List serializer returns field |
| `test_pending_submission_main_plot_uid_null` | Pending → null |
| `test_first_uid_empty_form` | First UID → PLT00001 |
| `test_respects_plot_uid_start` | Floor from config |
| `test_sequential_increment` | Increments after existing |
| `test_max_wins_over_start` | max+1 > start |
| `test_start_wins_over_max` | start > max+1 |
| `test_scoped_per_form` | Other form's plots don't affect |
| `test_two_forms_same_uid_allowed` | Two forms can share PLT00001 |

---

## Out of Scope

- Linking resubmissions to existing Plot ID (separate task — model already supports it)
- Plot ID in export (XLSX/Shapefile) — follow-up
- Plot ID in Telegram notifications — follow-up
- Renaming `plot_id` API field to `submission_id` — breaking change, defer
