# Technical Execution Plan: Frontend Map View

> **Status: COMPLETED**

## Context

The map page at `frontend/src/app/dashboard/map/page.js` was a stub (`<div>Map Page</div>`). This plan transformed it into an interactive split-panel map interface for reviewing, approving, and editing geospatial plot data. Additionally, the backend was refactored to automate plot generation and move approval state to the Submission model.

**Design references:**
- `docs/assets/dashboard-map-view/Map.png` — Plot list with satellite map
- `docs/assets/dashboard-map-view/Map-details.png` — Plot detail panel
- `docs/assets/dashboard-map-view/Approve-modal.png` — Approval confirmation dialog

---

## What Was Implemented

### Backend Changes

- **Polygon utilities** (`backend/utils/polygon.py`) — ODK geoshape parsing, WKT conversion, bbox calculation, validation (vertex count, self-intersection via Shapely, area threshold)
- **Auto-plot generation** — Sync creates/updates Plot per Submission via `extract_plot_data()` with configurable field mappings
- **Approval on Submission** — `approval_status` (1=Approved, 2=Rejected, null=Pending) + `reviewer_notes` on Submission; `is_draft` removed from Plot
- **Field mapping config** — `polygon_field`, `region_field`, `sub_region_field`, `plot_name_field` on FormMetadata
- **KoboToolbox field proxy** — `GET /forms/{uid}/form_fields/` extracts `content.survey` fields
- **Plot creation disabled** — POST returns 405; plots only created via sync
- **115 tests passing**, 92% coverage

### Frontend — Map View

#### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `leaflet` | `^1.9.4` | Core map library |
| `react-leaflet` | `^5.0.0` | React 19 bindings |
| `@react-leaflet/core` | `^3.0.0` | Core hooks (peer dep) |
| `react-leaflet-draw` | `^0.21.0` | Geometry editing tools |

#### Satellite Tile Provider

**Google Satellite** — supports zoom level 20 for close-up plot inspection:

```
https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}
```

Subdomains: `mt0`, `mt1`, `mt2`, `mt3`

#### Component Hierarchy

```
MapPage ("use client")
├── Full-bleed wrapper (-m-6)
├── Split layout (flex row, h-full)
│   ├── Left Panel (w-[380px], border-r, bg-card, flex-col)
│   │   ├── PlotListPanel (when panelMode === "list")
│   │   │   ├── Header: count + menu
│   │   │   ├── Sort Select
│   │   │   ├── Status Tabs (View all | Approved | Pending | Rejected)
│   │   │   └── ScrollArea > PlotCardItem[]
│   │   └── PlotDetailPanel (when panelMode === "detail")
│   │       ├── Back button
│   │       ├── Metadata grid (region, enumerator, age, phone, etc.)
│   │       ├── Coordinates display (null-safe)
│   │       ├── Notes Textarea
│   │       └── Approve + Reject buttons
│   └── Right Panel (flex-1, relative)
│       ├── MapFilterBar (absolute, top, z-10)
│       └── MapContainerDynamic (h-full)
│           ├── Google Satellite TileLayer (maxZoom 20)
│           ├── Plot Polygons (color-coded by status)
│           ├── MapController (fitBounds)
│           ├── MapEditLayer (when editing)
│           ├── MapEditToolbar (when editing)
│           └── MapPopupCard (when selected)
├── ApprovalDialog (modal, via Radix portal)
├── RejectionDialog (modal, via Radix portal)
└── ToastNotification (fixed position)
```

#### Data Flow

```
useForms() ──→ activeForm.asset_uid
                     │
                     ▼
usePlots({ formId }) ──→ plots[], count, isLoading, refetch
                     │
                     ▼
useMapState({ plots }) ──→ selectedPlot, panelMode, editingPlotId, tabs, sort
                     │
         ┌───────────┴───────────────┐
         ▼                           ▼
  Left Panel                    Map View
  (list or detail)           (polygons, popup, edit)
         │                           │
         ▼                           ▼
  Approve/Reject             Save geometry
  PATCH /submissions/{uuid}/ PATCH /plots/{uuid}/
         │                           │
         └───────────┬───────────────┘
                     ▼
              refetch() → re-render
```

#### Status Mapping

| Backend `approval_status` | Frontend string | Label | Color |
|---------------------------|----------------|-------|-------|
| `null` | `"pending"` | "Pending" | yellow |
| `1` | `"approved"` | "Approved" | green |
| `2` | `"rejected"` | "Rejected" | red |

#### Polygon Styles

```javascript
const POLYGON_STYLES = {
  pending:  { color: "#EAB308", weight: 2, fillOpacity: 0.2 },
  approved: { color: "#16A34A", weight: 2, fillOpacity: 0.2 },
  rejected: { color: "#DC2626", weight: 2, fillOpacity: 0.2 },
  selected: { color: "#22D3EE", weight: 3, fillOpacity: 0.3 },
  editing:  { color: "#F97316", weight: 3, fillOpacity: 0.25 },
};
```

### Frontend — Field Mapping Configuration

The forms page (`/dashboard/forms`) includes a "Configure" dialog for each form:

- Fetches available fields via `GET /forms/{uid}/form_fields/`
- Multi-select dropdowns (DropdownMenu + CheckboxItem) for polygon and plot name fields
- Single-select (Radix Select) for region and sub-region fields
- Geoshape/geotrace fields sorted first in polygon selector
- Saves via `PATCH /forms/{uid}/` with comma-separated values
- Pre-populated from existing form field mapping values

### Frontend — Status Rename

All references to `on_hold` renamed to `pending` across:
- CSS variables (`--status-on-hold` → `--status-pending`)
- StatusBadge component
- PlotListPanel tabs and sort order
- Dashboard page tabs
- MapView polygon styles
- SubmissionsTable (maps `approval_status` integer → string)

---

## File Summary

### New Backend Files

| File | Purpose |
|------|---------|
| `backend/utils/polygon.py` | ODK geoshape parsing, WKT, bbox, validation |
| `backend/api/v1/v1_odk/tests/tests_polygon_utils.py` | Polygon utility tests |

### New Frontend Files (17)

| File | Purpose |
|------|---------|
| `frontend/src/lib/wkt-parser.js` | WKT ↔ Leaflet coordinate conversion |
| `frontend/src/lib/plot-utils.js` | Plot status helper, bbox calculator |
| `frontend/src/hooks/usePlots.js` | Plot data fetching hook |
| `frontend/src/hooks/useMapState.js` | Map page UI state management |
| `frontend/src/components/map/map-container-dynamic.js` | SSR-safe dynamic import |
| `frontend/src/components/map/map-view.js` | Core Leaflet map with Google Satellite tiles |
| `frontend/src/components/map/map-controller.js` | Auto-fit bounds on selection |
| `frontend/src/components/map/map-edit-layer.js` | Geometry editing (FeatureGroup + EditControl) |
| `frontend/src/components/map/map-edit-toolbar.js` | Floating Save/Cancel bar |
| `frontend/src/components/map/map-popup-card.js` | Selected plot info popup |
| `frontend/src/components/map/plot-list-panel.js` | Left panel list view |
| `frontend/src/components/map/plot-card-item.js` | Individual plot row |
| `frontend/src/components/map/plot-detail-panel.js` | Left panel detail view |
| `frontend/src/components/map/map-filter-bar.js` | Compact filter bar above map |
| `frontend/src/components/map/approval-dialog.js` | Approve confirmation modal |
| `frontend/src/components/map/rejection-dialog.js` | Reject confirmation modal |
| `frontend/src/components/map/toast-notification.js` | Success notification |

### Modified Frontend Files

| File | Change |
|------|--------|
| `frontend/src/app/dashboard/map/page.js` | Full map page with approve/reject via submission PATCH |
| `frontend/src/app/dashboard/forms/page.js` | Field mapping configuration dialog |
| `frontend/src/app/dashboard/page.js` | Tab rename: on_hold → pending |
| `frontend/src/app/globals.css` | CSS variable rename: --status-on-hold → --status-pending |
| `frontend/src/components/status-badge.js` | on_hold → pending |
| `frontend/src/components/submissions-table.js` | Maps approval_status integer to string |
| `frontend/src/hooks/useForms.js` | Added updateForm, fetchFormFields |

### Generated UI Components

| File | Source |
|------|--------|
| `frontend/src/components/ui/dialog.jsx` | `npx shadcn@latest add dialog` |
| `frontend/src/components/ui/textarea.jsx` | `npx shadcn@latest add textarea` |
| `frontend/src/components/ui/scroll-area.jsx` | `npx shadcn@latest add scroll-area` |

---

## Verification

### Automated
```bash
docker compose exec backend python manage.py test   # 115 tests pass
docker compose exec frontend yarn build              # Production build succeeds
docker compose exec frontend yarn lint               # ESLint passes
```

### Manual Checklist
1. Navigate to `/dashboard/forms` → Click "Configure" → field dropdowns load
2. Select polygon field (geoshape), region, sub-region, plot name fields → Save
3. Click "Sync" → plots created with geometry from field mappings
4. Navigate to `/dashboard/map` → map renders with Google Satellite imagery
5. Plot polygons visible on map, color-coded by status (yellow=pending, green=approved, red=rejected)
6. Click "Pending" tab → filters to pending plots only
7. Click a plot card → detail panel shows metadata, map zooms to plot
8. Click "Approve" → dialog with notes → PATCH submission → status updates, toast shown
9. Click "Reject" → dialog requires reason → PATCH submission → status changes
10. Click "Fix Geometry" → edit mode, drag vertices → save → polygon updates
11. Zoom to level 20 → satellite tiles render without blank areas
12. Plots with null geometry show "No geometry data" in detail panel
