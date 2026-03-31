# V20 — Plot ID & Submission ID Separation

**Issue**: #37  
**Date**: 2026-03-31  
**Status**: Planning  
**Depends on**: AC1 (Rename "Plot ID" → "Submission ID" in ODK app) — DONE

---

## Overview

Currently `plot_id` in the API is `submission.kobo_id` (the Kobo submission number). This conflates two concepts: a **submission** (a single data collection event) and a **plot** (a long-lived physical entity that can have multiple submissions over time).

This plan implements **AC2** (generate Plot ID on approval) and **AC3** (both IDs visible & searchable) using the already-created `MainPlot` and `MainPlotSubmission` models.

---

## Current State Analysis

### Models (already created, no migrations yet)

```python
# models.py:510-527
class MainPlot(models.Model):
    form = models.ForeignKey(FormMetadata, ..., related_name="main_plots")
    uid = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

# models.py:530-544
class MainPlotSubmission(models.Model):
    main_plot = models.ForeignKey(MainPlot, ..., related_name="submissions")
    submission = models.ForeignKey(Submission, ..., related_name="main_plot_submissions")
    # unique_together = ("main_plot", "submission")
```

### Key reference points

| Item | Location | Notes |
|------|----------|-------|
| Approval endpoint | `views.py:856-912` (`perform_update`) | `PATCH /v1/odk/submissions/{uuid}/` |
| PlotSerializer `plot_id` | `serializers.py:712-713` | Currently `source="submission.kobo_id"` |
| Farmer UID generation | `utils/farmer_sync.py:87-116` | Reference pattern: `generate_next_farmer_uid()` |
| `FormMetadata.plot_uid_start` | `models.py:86-96` | Exists but unused — controls minimum UID |
| `PREFIX_PLOT_ID` | `constants.py:107` / `constants.js:1` | `"PLT"` |
| `PREFIX_SUBM_ID` | `constants.py:109` / `constants.js:3` | `"#"` |
| Frontend approval | `map/page.js:72-138` | `handleApprove`, `handleReject`, `handleRevertToPending` |
| Plot card | `plot-card-item.js:40-43` | Shows `Submission ID: #{kobo_id}` |
| Plot detail header | `plot-detail-panel.js:382` | Passes `plotId={plot?.plot_id}` |
| Submissions table | `submissions-table.js:57-77` | Column "Submission ID", shows `#{kobo_id}` |

---

## Implementation Plan

### Phase 1 — Backend: Migration

#### 1.1 Create migration for MainPlot & MainPlotSubmission

Models are already defined. Generate and apply migration:

```bash
python manage.py makemigrations v1_odk
python manage.py migrate
```

#### 1.2 Register in admin

**File**: `backend/api/v1/v1_odk/admin.py`

Add `MainPlot` and `MainPlotSubmission` to admin registrations.

---

### Phase 2 — Backend: Plot ID Generation Utility

#### 2.1 Create `utils/plot_id.py`

Follow the farmer UID pattern from `utils/farmer_sync.py:87-116`:

- `generate_next_plot_uid(form)` — scoped per form, returns `"PLT00001"` format
  - Uses `Cast` + `Max` on numeric suffix (same pattern as farmer UID)
  - Respects `form.plot_uid_start` as floor
  - Zero-pads to 5 digits
- `create_main_plot_for_submission(submission)` — creates `MainPlot` + `MainPlotSubmission` link
  - Returns `None` if submission has no associated `Plot`
  - Handles `IntegrityError` race with retry (same as farmer pattern)

**Key design decisions**:
- UIDs scoped per form — each form counts independently
- `form.plot_uid_start` acts as floor (e.g. 351 → first plot is `PLT00351`)
- Once a `MainPlot.uid` is generated, it is **never deleted or recycled**

---

### Phase 3 — Backend: Hook into Approval Flow

#### 3.1 Modify `perform_update` in `SubmissionViewSet`

**File**: `backend/api/v1/v1_odk/views.py` (line 856)

Insert Plot ID generation after `serializer.save()`:

**Behavior matrix**:

| Transition | Action |
|-----------|--------|
| Pending → Approved | Create `MainPlot` + `MainPlotSubmission` (if not already linked) |
| Pending → Rejected | No action |
| Approved → Pending (revert) | Delete `MainPlotSubmission` link (keep `MainPlot`) |
| Approved → Rejected | Delete `MainPlotSubmission` link (keep `MainPlot`) |
| Rejected → Pending | No action |

**Idempotency**: Check `MainPlotSubmission.objects.filter(submission=instance).exists()` before creating.

**MainPlot retention**: A generated `MainPlot` is never deleted — only the link is removed on revert. This prevents UID gaps and supports future resubmission linking.

---

### Phase 4 — Backend: Serializer Updates

#### 4.1 Add `main_plot_uid` to `PlotSerializer`

**File**: `serializers.py:711`

Add `SerializerMethodField` that traverses `submission.main_plot_submissions.first().main_plot.uid`.

#### 4.2 Add `main_plot_uid` to `SubmissionListSerializer`

**File**: `serializers.py:89`

Same pattern: `obj.main_plot_submissions.first().main_plot.uid`.

#### 4.3 Add `main_plot_uid` to `SubmissionDetailSerializer`

Same pattern for the detail view.

#### 4.4 Optimize queries

Add `prefetch_related("main_plot_submissions__main_plot")` to relevant ViewSet querysets to avoid N+1.

---

### Phase 5 — Backend: Search & Filter Support

#### 5.1 Extend search to match Plot ID

**Files**: `views.py` — `PlotViewSet` and `SubmissionViewSet` list methods

For PlotViewSet search:
```python
Q(submission__main_plot_submissions__main_plot__uid__icontains=search)
```

For SubmissionViewSet search:
```python
Q(main_plot_submissions__main_plot__uid__icontains=search)
```

Add `.distinct()` to avoid duplicate rows from the join.

---

### Phase 6 — Frontend: Display Both IDs

#### 6.1 Plot card (`plot-card-item.js`)

Add Plot ID row below Submission ID when `plot.main_plot_uid` is present:

```
Submission ID: #12345
Plot ID: PLT00351          ← only shown when approved
```

#### 6.2 Plot detail panel header (`plot-detail-panel.js`)

Pass `mainPlotUid={plot?.main_plot_uid}` to `PlotHeaderCard`. Display alongside Submission ID.

#### 6.3 Map popup card (`map-popup-card.js`)

Show Plot ID when available.

#### 6.4 Submissions table (`submissions-table.js`)

Add "Plot ID" column after "Submission ID":

```jsx
{
  key: "main_plot_uid",
  header: "Plot ID",
  cell: (row) => <TextCell>{row.main_plot_uid || "—"}</TextCell>,
}
```

---

### Phase 7 — Backend Tests

#### 7.1 New file: `tests/tests_plot_id_generation.py`

| Test | Description |
|------|-------------|
| `test_approve_creates_main_plot` | Approval creates `MainPlot` with `PLT00001` format |
| `test_approve_respects_uid_start` | With `plot_uid_start=351`, first plot is `PLT00351` |
| `test_approve_sequential` | Second approval increments UID |
| `test_approve_idempotent` | Approving same submission twice → no duplicate |
| `test_revert_deletes_link` | Revert deletes `MainPlotSubmission`, keeps `MainPlot` |
| `test_reject_no_main_plot` | Rejection creates no `MainPlot` |
| `test_search_by_plot_id` | Search matches `MainPlot.uid` |
| `test_serializer_includes_main_plot_uid` | Both serializers return `main_plot_uid` |

#### 7.2 New file: `tests/tests_plot_id_utils.py`

| Test | Description |
|------|-------------|
| `test_generate_next_plot_uid_empty` | First UID → `PLT00001` |
| `test_generate_next_plot_uid_with_start` | Respects `plot_uid_start` floor |
| `test_generate_next_plot_uid_sequential` | Increments correctly |

---

### Phase 8 — Frontend Tests

- Submissions table: "Plot ID" column renders `main_plot_uid` or "—"
- Plot card: Plot ID row appears only when `main_plot_uid` is truthy

---

## Data Migration: Backfill Existing Approved Submissions

### Management command: `backfill_plot_ids`

Submissions approved **before** this feature have no `MainPlot`. Create a management command:

1. Find all submissions with `approval_status=APPROVED` and no `MainPlotSubmission`
2. Order by `submission_time` (earliest first)
3. Generate `MainPlot` UIDs per form, respecting `plot_uid_start`

This ensures all approved plots show a Plot ID in the UI consistently.

---

## API Response Changes

### `GET /v1/odk/plots/`

```diff
 {
   "plot_id": "12345",           // Kobo submission ID (unchanged)
+  "main_plot_uid": "PLT00351",  // null if not yet approved
   "uuid": "...",
   ...
 }
```

### `GET /v1/odk/submissions/`

```diff
 {
   "kobo_id": "12345",
+  "main_plot_uid": "PLT00351",  // null if not yet approved
   ...
 }
```

---

## File Change Summary

| File | Change | Phase |
|------|--------|-------|
| Migration (new) | Create `main_plots` and `main_plot_submissions` tables | 1 |
| `admin.py` | Register `MainPlot`, `MainPlotSubmission` | 1 |
| `utils/plot_id.py` (new) | `generate_next_plot_uid`, `create_main_plot_for_submission` | 2 |
| `views.py` | Hook `perform_update` for approval/revert; extend search | 3, 5 |
| `serializers.py` | Add `main_plot_uid` to 3 serializers; add prefetch | 4 |
| `plot-card-item.js` | Show Plot ID when approved | 6 |
| `plot-detail-panel.js` | Show Plot ID in header | 6 |
| `map-popup-card.js` | Show Plot ID in popup | 6 |
| `submissions-table.js` | Add "Plot ID" column | 6 |
| `tests_plot_id_generation.py` (new) | Approval flow tests | 7 |
| `tests_plot_id_utils.py` (new) | UID generation unit tests | 7 |
| Management command (new) | `backfill_plot_ids` | Backfill |

---

## Execution Order

```
Phase 1 (Migration + Admin)
    ↓
Phase 2 (UID Generation Utility)
    ↓
Phase 3 (Approval Flow Hook)
    ↓
Phase 4 (Serializers)  ←→  Phase 5 (Search/Filter)
    ↓
Phase 6 (Frontend Display)
    ↓
Phase 7 (Backend Tests)  ←→  Phase 8 (Frontend Tests)
    ↓
Backfill (Management Command)
```

---

## Out of Scope

- Linking resubmissions to existing Plot ID (separate task)
- Plot ID in export (XLSX/Shapefile) — follow-up
- Plot ID in Telegram notifications — follow-up
- Renaming `plot_id` API field to `submission_id` — breaking change, defer
