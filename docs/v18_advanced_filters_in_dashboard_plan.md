# Advanced Filters in Dashboard — Implementation Summary

**Status:** Implemented

**Goal:** Move filter field configuration from Forms > Configure into the Advanced Filters dialog, connect filters between Dashboard and Map pages via shared state, add searchable dropdowns for lists with 15+ items, and sort all filter options alphabetically.

**Architecture:** Replaced Dashboard-local filter state with the existing `MapStateProvider` context (already used by Map page) so both pages share one filter state. Enhanced the `FilterBar` component's Advanced Filters dialog to include a "Manage Filters" section where users toggle which dynamic fields are active — changes reflect instantly without page refresh. Added a `SearchableSelect` component (using `cmdk` / shadcn `Command`) for dropdowns with 15+ options. Backend `filter_options` endpoint now sorts options alphabetically, supports `all_eligible=true` to return all eligible filter fields, and fixes label resolution for multi-field specs where some fields are empty.

**Tech Stack:** Next.js 15, React 19, shadcn/ui (Command component via cmdk@1.0.4), Django 4.2, DRF

---

## Files Created

| File | Responsibility |
|------|---------------|
| `frontend/src/components/ui/command.jsx` | shadcn Command component wrapping cmdk — provides `Command`, `CommandInput`, `CommandList`, `CommandEmpty`, `CommandGroup`, `CommandItem` |
| `frontend/src/components/searchable-select.js` | Reusable `SearchableSelect` — renders a searchable combobox (via Command/Popover) when options >= 15, otherwise a plain `<Select>`. Always sorts options alphabetically by label. |
| `frontend/__tests__/searchable-select.test.js` | Tests: plain select for < 15 options, search input for 15+ options, alphabetical sorting |
| `backend/api/v1/v1_odk/tests/tests_filter_options_all_eligible.py` | Tests: `all_eligible=true` returns extra select fields, excludes region/sub_region/text fields, options sorted alphabetically |

## Files Modified

| File | Changes |
|------|---------|
| `frontend/package.json` | Added `cmdk@1.0.4` dependency |
| `frontend/src/components/filter-bar.js` | Replaced inline Select dropdowns with `SearchableSelect`. Added `visibleDynamicFilters` memo that derives visible filters from `availableFilters` + `activeFilterFields` (instant toggle, no refresh needed). Added "Manage Filters" section with `Switch` toggles. New props: `availableFilters`, `activeFilterFields`, `onActiveFilterFieldsChange`. |
| `frontend/__tests__/filter-bar.test.js` | Added 4 tests: manage-filters section visibility, toggle switches rendering, hidden when no available filters, advanced filters button with only availableFilters |
| `frontend/src/hooks/useFilterOptions.js` | Added `allEligible` param. When true, passes `all_eligible=true` to API. Returns `available_filters` alongside existing fields. |
| `frontend/src/hooks/useMapState.js` | Added `activeFilterFields` state initialized from `activeForm.filter_fields` on form change. Added debounced (1s) PATCH to `/v1/odk/forms/{id}/` to persist changes to backend (skips initial load). Exposed `activeFilterFields` and `setActiveFilterFields` in context. |
| `frontend/src/app/dashboard/page.js` | Removed local filter state (`region`, `subRegion`, `startDate`, `endDate`, `dynamicValues`). Now destructures these from `useMapState()`. Passes `availableFilters`, `activeFilterFields`, `onActiveFilterFieldsChange` to FilterBar. Uses `handleResetFilters` from context. |
| `frontend/src/app/dashboard/map/page.js` | Updated `useFilterOptions` call to pass `allEligible: true`. Passes `availableFilters`, `activeFilterFields`, `onActiveFilterFieldsChange` to FilterBar. |
| `frontend/src/app/dashboard/forms/page.js` | Removed filter_fields UI from Configure dialog (the `filterSelectFields` state, `toggleFilterField` function, filter fields dropdown, and `filter_fields` in save payload). Filter configuration now lives in FilterBar's "Manage Filters" section. |
| `backend/api/v1/v1_odk/views.py` | **filter_options endpoint:** (1) Sort `regions`, `sub_regions`, and `dynamic_filters` options alphabetically by label. (2) Added `all_eligible=true` query param — returns `available_filters` containing all `select_*` questions excluding region/sub_region/plot_name fields. (3) Fixed `_resolve_label` — when positional field lookup fails (due to empty fields being skipped in multi-field specs like `"woreda_specify,woreda"`), falls back to searching all fields' options for a match. |

---

## Requirement → Implementation Mapping

| Requirement | Implementation |
|------------|---------------|
| **Move filter fields from Configure to Advanced Filter** | Removed filter_fields UI from `forms/page.js` Configure dialog. Added "Manage Filters" section with Switch toggles in `filter-bar.js`. Toggles update `activeFilterFields` in shared context, debounce-saved to backend. |
| **Dashboard and Map filters connected** | Dashboard now uses `useMapState` context (shared with Map) for `region`, `subRegion`, `startDate`, `endDate`, `dynamicValues`, `activeFilterFields`. Changing filters on either page is reflected on the other. |
| **Search bar in dropdowns with 15+ items** | `SearchableSelect` component auto-renders a cmdk-powered searchable combobox when options >= 15, plain `<Select>` otherwise. Used for all filter dropdowns (regions, sub-regions, dynamic filters). |
| **All filters alphabetically aligned** | Backend sorts `regions`, `sub_regions`, `dynamic_filters` options, and `available_filters` by label. Frontend also sorts via `localeCompare` as safety net. |

## Key Design Decisions

1. **Instant toggle (no refresh):** `FilterBar` derives `visibleDynamicFilters` from `availableFilters` filtered by `activeFilterFields` client-side. The backend `dynamic_filters` response is not the source of truth for which filters to show — the local `activeFilterFields` is. This means toggling a filter in "Manage Filters" instantly shows/hides the dropdown.

2. **Backend-only persistence:** `activeFilterFields` initializes from `activeForm.filter_fields` (already fetched by `useForms()`). User changes are debounce-saved (1s) via PATCH to `/v1/odk/forms/{id}/`. No localStorage — the backend is the single source of truth, avoiding namespacing/validation/stale-data complexity.

3. **Label resolution fallback:** The `_resolve_label` function now searches all fields in a multi-field spec when positional lookup fails. This fixes cases where `sub_region_field="woreda_specify,woreda"` and the submission only has `woreda` filled — the stored value `ET0407` is now correctly resolved via the `woreda` field's options.

## Test Coverage

- **Backend:** 25 filter_options tests pass (21 existing + 4 new)
- **Frontend:** 18 filter-bar tests pass (15 existing + 3 new), 3 searchable-select tests pass
- **Full suite:** 561 backend tests OK, 58 frontend tests OK