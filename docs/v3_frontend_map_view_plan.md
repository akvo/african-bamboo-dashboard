# Technical Execution Plan: Frontend Map View

> **Status: PENDING**
> **Prerequisite:** [v2.1 Backend PK Refactor](./v2.1_backend_pk_refactor_plan.md) must be completed first.

## Context

The map page at `frontend/src/app/dashboard/map/page.js` is a stub (`<div>Map Page</div>`). This plan transforms it into an interactive split-panel map interface for reviewing, approving, and editing geospatial plot data.

**Design references:**
- `docs/assets/dashboard-map-view/Map.png` — Plot list with satellite map
- `docs/assets/dashboard-map-view/Map-details.png` — Plot detail panel
- `docs/assets/dashboard-map-view/Approve-modal.png` — Approval confirmation dialog

**POC reference:** `docs/assets/dashboard-map-view/example-poc/` — Vite+React+Leaflet proof-of-concept demonstrating core map interactions, geometry editing, and rejection flow.

---

## Phase 1: Dependencies & Configuration

### 1.1 NPM Packages

```bash
docker-compose exec frontend yarn add leaflet react-leaflet @react-leaflet/core react-leaflet-draw
```

| Package | Version | Purpose |
|---------|---------|---------|
| `leaflet` | `^1.9.4` | Core map library |
| `react-leaflet` | `^5.0.0` | React 19 bindings |
| `@react-leaflet/core` | `^3.0.0` | Core hooks (peer dep) |
| `react-leaflet-draw` | `^0.21.0` | Geometry editing tools |

### 1.2 shadcn/ui Components

```bash
docker-compose exec frontend npx shadcn@latest add dialog textarea scroll-area
```

Generates:
- `frontend/src/components/ui/dialog.jsx`
- `frontend/src/components/ui/textarea.jsx`
- `frontend/src/components/ui/scroll-area.jsx`

### 1.3 Satellite Tile Provider

**Esri World Imagery** — free, no API key, high-resolution:

```
https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}
```

Attribution: `Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community`

### 1.4 CSS Strategy

Leaflet CSS is imported **inside** the dynamically-loaded component (not in `globals.css`) to avoid loading on non-map pages:

```javascript
// Inside map-view.js (loaded via next/dynamic with ssr: false)
import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";
```

---

## Phase 2: Utilities & Data Hooks

### 2.1 WKT Parser

**File:** `frontend/src/lib/wkt-parser.js`

Converts between WKT polygon strings and Leaflet coordinate arrays.

WKT uses `(longitude latitude)` order. Leaflet uses `[latitude, longitude]`.

```javascript
export function parseWktPolygon(wkt) {
  if (!wkt) return [];
  const match = wkt.match(/POLYGON\s*\(\((.+)\)\)/i);
  if (!match) return [];
  return match[1].split(",").map((pair) => {
    const [lon, lat] = pair.trim().split(/\s+/).map(Number);
    return [lat, lon];
  });
}

export function toWktPolygon(coords) {
  if (!coords || coords.length === 0) return "";
  const ring = coords.map(([lat, lon]) => `${lon} ${lat}`).join(", ");
  return `POLYGON((${ring}))`;
}
```

### 2.2 Plot Status Helper

**File:** `frontend/src/lib/plot-utils.js`

```javascript
export function getPlotStatus(plot) {
  if (plot.status) return plot.status; // future-proofed
  return plot.is_draft ? "on_hold" : "approved";
}

export function calculateBbox(coords) {
  const lats = coords.map(([lat]) => lat);
  const lons = coords.map(([, lon]) => lon);
  return {
    min_lat: Math.min(...lats),
    max_lat: Math.max(...lats),
    min_lon: Math.min(...lons),
    max_lon: Math.max(...lons),
  };
}
```

### 2.3 usePlots Hook

**File:** `frontend/src/hooks/usePlots.js`

Follows the pattern from `frontend/src/hooks/useSubmissions.js`. Fetches all plots for the active form.

```javascript
"use client";
import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";

export function usePlots({ formId, limit = 200 } = {}) {
  const [plots, setPlots] = useState([]);
  const [count, setCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPlots = useCallback(async () => {
    if (!formId) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.get("/v1/odk/plots/", {
        params: { form_id: formId, limit },
      });
      setPlots(res.data.results || []);
      setCount(res.data.count || 0);
    } catch (err) {
      setError(
        err.response?.data?.message || "Failed to fetch plots"
      );
    } finally {
      setIsLoading(false);
    }
  }, [formId, limit]);

  useEffect(() => { fetchPlots(); }, [fetchPlots]);

  return { plots, setPlots, count, isLoading, error, refetch: fetchPlots };
}
```

**API response format** (LimitOffsetPagination, default page_size=10 — overridden with `limit=200`):
```json
{
  "count": 128,
  "next": null,
  "previous": null,
  "results": [
    {
      "uuid": "550e8400-...",
      "plot_name": "Alda Aldb Aldc",
      "instance_name": "enum_003-ET1600-2026-02-03",
      "polygon_wkt": "POLYGON((109.465... -7.391..., ...))",
      "min_lat": -7.3913, "max_lat": -7.3911,
      "min_lon": 109.4651, "max_lon": 109.4652,
      "is_draft": true,
      "form_id": "aYRqYXmmPLFfbcwC2KAULa",
      "region": "ET16",
      "sub_region": "ET1600",
      "created_at": 1738571570000,
      "submission_uuid": "1da1623d-6b3c-..."
    }
  ]
}
```

### 2.4 useMapState Hook

**File:** `frontend/src/hooks/useMapState.js`

Centralized UI state management for the map page.

```javascript
"use client";
import { useState, useCallback, useMemo } from "react";

export function useMapState({ plots }) {
  const [selectedPlotId, setSelectedPlotId] = useState(null);
  const [panelMode, setPanelMode] = useState("list"); // "list" | "detail"
  const [editingPlotId, setEditingPlotId] = useState(null);
  const [approvalDialogOpen, setApprovalDialogOpen] = useState(false);
  const [rejectionDialogOpen, setRejectionDialogOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("all");
  const [sortBy, setSortBy] = useState("priority");
  const [search, setSearch] = useState("");
  const [toastMessage, setToastMessage] = useState(null);

  const selectedPlot = useMemo(
    () => plots.find((p) => p.uuid === selectedPlotId) || null,
    [plots, selectedPlotId]
  );

  const handleSelectPlot = useCallback((plotUuid) => {
    if (editingPlotId && plotUuid !== editingPlotId) return;
    setSelectedPlotId(plotUuid);
    if (plotUuid) setPanelMode("detail");
  }, [editingPlotId]);

  const handleBackToList = useCallback(() => {
    setSelectedPlotId(null);
    setPanelMode("list");
    setEditingPlotId(null);
  }, []);

  const handleStartEditing = useCallback(() => {
    if (selectedPlotId) setEditingPlotId(selectedPlotId);
  }, [selectedPlotId]);

  const handleCancelEditing = useCallback(() => {
    setEditingPlotId(null);
  }, []);

  return {
    selectedPlotId, selectedPlot, panelMode,
    editingPlotId, approvalDialogOpen, rejectionDialogOpen,
    activeTab, sortBy, search, toastMessage,
    setActiveTab, setSortBy, setSearch, setToastMessage,
    setApprovalDialogOpen, setRejectionDialogOpen,
    handleSelectPlot, handleBackToList,
    handleStartEditing, handleCancelEditing,
    setEditingPlotId,
  };
}
```

---

## Phase 3: Basic Map Rendering

### 3.1 Dynamic Import Wrapper

**File:** `frontend/src/components/map/map-container-dynamic.js`

Leaflet accesses `window`/`document` which break during Next.js SSR. Use `next/dynamic` with `ssr: false`.

```javascript
"use client";
import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/skeleton";

const MapView = dynamic(
  () => import("@/components/map/map-view"),
  {
    ssr: false,
    loading: () => <Skeleton className="h-full w-full" />,
  }
);

export default MapView;
```

### 3.2 MapView Component

**File:** `frontend/src/components/map/map-view.js`

Core map component. Imported CSS here since this file is only loaded client-side.

Key elements:
- `MapContainer` with Esri satellite `TileLayer`
- Polygon layer for each plot, color-coded by status
- `MapController` for auto-fitting bounds
- `MapEditLayer` when editing (Phase 7)
- `MapPopupCard` for selected plot info (Phase 5)

**Polygon styles (matching existing theme variables):**
```javascript
const STYLES = {
  default:       { color: "#EAB308", weight: 2, fillOpacity: 0.2 },  // on_hold (yellow)
  selected:      { color: "#22D3EE", weight: 3, fillOpacity: 0.3 },  // selected (cyan)
  approved:      { color: "#16A34A", weight: 2, fillOpacity: 0.2 },  // approved (green)
  rejected:      { color: "#DC2626", weight: 2, fillOpacity: 0.2 },  // rejected (red)
  editing:       { color: "#F97316", weight: 3 },                     // editing (orange)
};
```

**Leaflet icon fix** (adapted from POC):
```javascript
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});
```

**Default center:** Ethiopia `[7.05, 38.47]` (from POC). On initial load with plots, auto-fit bounds to all loaded plots using `L.latLngBounds`.

### 3.3 MapController Component

**File:** `frontend/src/components/map/map-controller.js`

Uses `useMap()` from react-leaflet to `fitBounds` when a plot is selected. Adapted from POC's `MapController`.

```javascript
const MapController = ({ selectedPlot, allPlots }) => {
  const map = useMap();
  useEffect(() => {
    if (selectedPlot) {
      const coords = parseWktPolygon(selectedPlot.polygon_wkt);
      if (coords.length > 0) {
        map.fitBounds(L.latLngBounds(coords), { padding: [50, 50] });
      }
    } else if (allPlots.length > 0) {
      // Fit to all plots on initial load
      const allCoords = allPlots.flatMap((p) => parseWktPolygon(p.polygon_wkt));
      if (allCoords.length > 0) {
        map.fitBounds(L.latLngBounds(allCoords), { padding: [30, 30] });
      }
    }
  }, [selectedPlot, allPlots, map]);
  return null;
};
```

### 3.4 Full-Bleed Layout

The dashboard layout at `frontend/src/app/dashboard/layout.js` applies `p-6` to `<main>`. The map page needs edge-to-edge rendering.

```jsx
// In page.js
<div className="-m-6 h-[calc(100%+3rem)] overflow-hidden flex">
  {/* Left panel + Map fill the entire main area */}
</div>
```

---

## Phase 4: Left Panel — Plot List

### 4.1 PlotListPanel

**File:** `frontend/src/components/map/plot-list-panel.js`

Matches `Map.png` design. Structure:

```
PlotListPanel
├── Header: "{count} plots detected" + MoreVertical icon
├── Sort dropdown: "Sort: Priority"
├── Status Tabs: View all | Approved | On hold | Rejected
│   (reuse: Tabs, TabsList, TabsTrigger from @/components/ui/tabs)
└── ScrollArea (vertical scroll)
    └── PlotCardItem[] (filtered by activeTab, sorted by sortBy)
```

**Reuses:**
- `Tabs`, `TabsList`, `TabsTrigger` from `frontend/src/components/ui/tabs.jsx`
- `Select`, `SelectContent`, `SelectItem`, `SelectTrigger` from `frontend/src/components/ui/select.jsx`
- `ScrollArea` from `frontend/src/components/ui/scroll-area.jsx` (new, Phase 1)

### 4.2 PlotCardItem

**File:** `frontend/src/components/map/plot-card-item.js`

Each row in the plot list. Matches `Map.png` design:

```
┌──────────────────────────────────────────┐
│ Plot SID-A-1                 On hold  →  │
│ #23434242                                │
└──────────────────────────────────────────┘
```

- Plot name: `plot.plot_name` (font-medium)
- Subtitle: `plot.instance_name` or `plot.region` (text-muted-foreground, text-sm)
- Status badge: `StatusBadge` from `frontend/src/components/status-badge.js` (reused)
- Arrow: `ChevronRight` from lucide-react
- Click: `handleSelectPlot(plot.uuid)`
- Hover: `transition-colors duration-200` (150-300ms per UX guidelines)
- Selected: `bg-accent` highlight
- `cursor-pointer` on all rows

### 4.3 MapFilterBar

**File:** `frontend/src/components/map/map-filter-bar.js`

Compact filter bar above the map (right side). Matches `Map.png` top bar: Region dropdown, "Last 7 days", date range, Reset button.

Adapted from `frontend/src/components/filter-bar.js` — shares `useForms()` context but uses a horizontal compact layout.

---

## Phase 5: Left Panel — Plot Detail

### 5.1 PlotDetailPanel

**File:** `frontend/src/components/map/plot-detail-panel.js`

Matches `Map-details.png` design. Shown when `panelMode === "detail"`.

```
PlotDetailPanel
├── Back button (ArrowLeft icon + "Plot data")
├── Plot name (h2, bold)
│   Instance name subtitle
├── Metadata grid (2 columns)
│   ├── Region: {plot.region} (code, e.g. "ET16")
│   ├── Area (ha): {calculated from polygon}
│   ├── Enumerator: {raw_data.enumerator_id}
│   └── Boundary method: {raw_data.boundary_mapping/boundary_method}
├── Date row
│   ├── Start Date: {raw_data.start}
│   └── End Date: {raw_data.end}
├── Coordinates display
│   "lat, lng" from plot bounding box center
├── Notes section
│   └── Textarea (plain text initially)
└── Action buttons (full width, flex row)
    ├── Approve (green, flex-1)
    └── Reject (destructive, flex-1)
```

**Data enrichment:** When a plot is selected, fetch linked submission detail to populate extra fields:

```javascript
const fetchSubmissionDetail = async (submissionUuid) => {
  const res = await api.get(`/v1/odk/submissions/${submissionUuid}/`);
  return res.data;
};
```

**Submission `raw_data` key fields:**
| raw_data key | Display label | Example |
|-------------|---------------|---------|
| `full_name` | Farmer name | "Alda Aldb Aldc" |
| `region` | Region | "ET16" |
| `woreda` | Woreda | "ET1600" |
| `kebele` | Kebele | "ET160005" |
| `enumerator_id` | Enumerator | "enum_003" |
| `age_of_farmer` | Farmer age | "31" |
| `Phone_Number` | Phone | "0963487512" |
| `boundary_mapping/boundary_method` | Boundary method | "manual" |
| `geoshape_accuracy` | GPS accuracy | "0.0" |
| `numpoints` | Polygon points | "4" |
| `start` | Start time | "2026-02-03T17:38:52..." |
| `end` | End time | "2026-02-03T17:45:08..." |
| `Title_Deed_First_Page` | Title deed photo | Filename |
| `_attachments[].download_medium_url` | Photo URL | Kobo URL |

### 5.2 MapPopupCard

**File:** `frontend/src/components/map/map-popup-card.js`

Floating info card on the map for the selected plot. Uses Leaflet's `Popup` component from react-leaflet, positioned at polygon center.

Shows: Status badge, plot name, ID, region, area, enumerator, "Fix Geometry" button.

---

## Phase 6: Approval & Rejection Dialogs

### 6.1 ApprovalDialog

**File:** `frontend/src/components/map/approval-dialog.js`

Matches `Approve-modal.png` design. Uses shadcn Dialog components.

```jsx
<Dialog open={open} onOpenChange={onOpenChange}>
  <DialogContent className="sm:max-w-md">
    <DialogHeader>
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-status-approved/15">
        <CheckCircle2 className="h-6 w-6 text-status-approved" />
      </div>
      <DialogTitle>Confirm Approvement</DialogTitle>
      <DialogDescription>
        Approve this plot to confirm the boundary mapping is valid.
      </DialogDescription>
    </DialogHeader>
    <div className="space-y-2">
      <Label htmlFor="notes">Notes to enumerator</Label>
      <Textarea id="notes" value={notes} onChange={...} />
    </div>
    <DialogFooter>
      <Button variant="outline" onClick={onCancel}>Cancel</Button>
      <Button
        className="bg-status-approved text-white hover:bg-status-approved/90"
        onClick={onConfirm}
      >
        Confirm
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

**On confirm:** `PATCH /api/v1/odk/plots/{uuid}/` with `{ is_draft: false }` → refetch plots → show toast.

### 6.2 RejectionDialog

**File:** `frontend/src/components/map/rejection-dialog.js`

Same Dialog pattern but with destructive styling. Required reason textarea. Adapted from POC's `RejectionDialog.tsx`.

**On confirm:** `PATCH /api/v1/odk/plots/{uuid}/` with rejection data → return to list → refetch → toast.

### 6.3 ToastNotification

**File:** `frontend/src/components/map/toast-notification.js`

Ported from POC's `Toast.tsx`. Simple fixed-position notification with auto-dismiss (3s).

```jsx
<div
  className="fixed top-5 right-5 z-[99999] bg-status-approved text-white py-3 px-5 rounded-lg shadow-lg flex items-center"
  role="alert"
  aria-live="assertive"
>
  <CheckCircle2 className="h-5 w-5 mr-3" />
  <span className="font-medium">{message}</span>
</div>
```

---

## Phase 7: Geometry Editing

### 7.1 MapEditLayer

**File:** `frontend/src/components/map/map-edit-layer.js`

Adapted from POC `MapView.tsx` lines 56-185. Uses `FeatureGroup` + `EditControl` from react-leaflet-draw.

Capabilities:
- **Vertex drag editing** — move polygon vertices
- **Polygon redraw** — delete existing and draw new shape
- **Delete** — remove polygon entirely

```javascript
// Enable programmatic editing via callback ref
const polygonRef = useCallback((polygon) => {
  if (polygon) {
    polygon.editing.enable();
    polygon.on("edit", () => {
      const latlngs = polygon.getLatLngs()[0];
      const newGeometry = latlngs.map((l) => [l.lat, l.lng]);
      setEditedGeo(newGeometry);
    });
  }
}, []);
```

### 7.2 MapEditToolbar

**File:** `frontend/src/components/map/map-edit-toolbar.js`

Floating bar over the map during edit mode. Adapted from POC.

```
┌──────────────────────────────────────────┐
│ ● Editing: Plot SID-A-1   [Save] [Cancel]│
└──────────────────────────────────────────┘
```

Position: `absolute top-2 left-1/2 -translate-x-1/2 z-[1000]`

### 7.3 Save Flow

1. Convert edited coordinates to WKT via `toWktPolygon()`
2. Calculate new bounding box via `calculateBbox()`
3. `PATCH /api/v1/odk/plots/{uuid}/` with:
   ```json
   {
     "polygon_wkt": "POLYGON((..., ...))",
     "min_lat": -7.39, "max_lat": -7.38,
     "min_lon": 109.46, "max_lon": 109.47
   }
   ```
4. Exit editing mode, show toast, refetch plots

---

## Phase 8: Page Orchestrator

### 8.1 Map Page

**File:** `frontend/src/app/dashboard/map/page.js`

Rewrites the stub into the full map page. Client component (`"use client"`).

### 8.2 Component Hierarchy

```
MapPage ("use client")
├── Full-bleed wrapper (-m-6)
├── Split layout (flex row, h-full)
│   ├── Left Panel (w-[380px], border-r, bg-card, flex-col)
│   │   ├── PlotListPanel (when panelMode === "list")
│   │   │   ├── Header: count + menu
│   │   │   ├── Sort Select
│   │   │   ├── Status Tabs
│   │   │   └── ScrollArea > PlotCardItem[]
│   │   └── PlotDetailPanel (when panelMode === "detail")
│   │       ├── Back button
│   │       ├── Metadata grid
│   │       ├── Notes Textarea
│   │       └── Approve + Reject buttons
│   └── Right Panel (flex-1, relative)
│       ├── MapFilterBar (absolute, top, z-10)
│       └── MapContainerDynamic (h-full)
│           ├── Esri Satellite TileLayer
│           ├── Plot Polygons (color-coded)
│           ├── MapController (fitBounds)
│           ├── MapEditLayer (when editing)
│           ├── MapEditToolbar (when editing)
│           └── MapPopupCard (when selected)
├── ApprovalDialog (modal, via Radix portal)
├── RejectionDialog (modal, via Radix portal)
└── ToastNotification (fixed position)
```

### 8.3 Data Flow

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
  PATCH /plots/{uuid}/       PATCH /plots/{uuid}/
         │                           │
         └───────────┬───────────────┘
                     ▼
              refetch() → re-render
```

---

## Styling & UX Guidelines

### Theme Integration

Use existing Tailwind CSS 4 theme variables from `frontend/src/app/globals.css`:
- `bg-card`, `text-card-foreground` for panel backgrounds
- `bg-background`, `text-foreground` for general surfaces
- `border-border` for dividers
- `text-muted-foreground` for secondary text
- `--status-approved`, `--status-on-hold`, `--status-rejected` for status colors

### Z-Index Scale

| Element | Z-Index | Reason |
|---------|---------|--------|
| Map container | default | Base layer |
| Left panel | `z-10` | Above map edge |
| Map filter bar | `z-10` | Above map |
| Leaflet controls | `z-[400]` | Leaflet default |
| Edit toolbar | `z-[1000]` | Above all Leaflet UI |
| Dialog (Radix portal) | `z-50` | shadcn default, via portal |
| Toast | `z-[99999]` | Always on top |

### Interaction Guidelines

- **Transitions:** 150-300ms for hover/focus states (`transition-colors duration-200`)
- **Touch targets:** Minimum 44x44px for all interactive elements
- **Focus rings:** Radix UI handles ARIA; don't override
- **Cursor:** `cursor-pointer` on all clickable elements (plot cards, buttons, polygons)
- **Loading:** Skeleton screens via existing `Skeleton` component
- **Empty state:** Centered message with `text-muted-foreground` when no plots
- **Motion:** Respect `prefers-reduced-motion` media query
- **Icons:** lucide-react only — no emojis (per project convention)

### Responsive Behavior

| Breakpoint | Layout |
|------------|--------|
| Desktop (>=768px) | Fixed left panel `w-[380px]` + flex-1 map side-by-side |
| Mobile (<768px) | Panel full-width above, map below (or Sheet drawer from left) |

---

## Backend API Reference

### Table Relationships (After v2.1 Refactor)

```
FormMetadata (1) ──CASCADE──→ (N) Submission (1) ──SET_NULL──→ (1) Plot
                                                   Plot also has FK to FormMetadata
```

### Endpoints Used by Map View

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/odk/plots/?form_id={asset_uid}&limit=200` | List all plots for a form |
| GET | `/api/v1/odk/plots/{uuid}/` | Plot detail |
| PATCH | `/api/v1/odk/plots/{uuid}/` | Update plot (geometry, is_draft) |
| GET | `/api/v1/odk/submissions/{uuid}/` | Submission detail (raw_data) |
| POST | `/api/v1/odk/plots/overlap_candidates/` | Find overlapping plots (bbox) |

### Plot API Response Shape

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "plot_name": "Alda Aldb Aldc",
  "instance_name": "enum_003-ET1600-2026-02-03",
  "polygon_wkt": "POLYGON((109.46519... -7.39118..., ...))",
  "min_lat": -7.3913,
  "max_lat": -7.3911,
  "min_lon": 109.4651,
  "max_lon": 109.4652,
  "is_draft": true,
  "form_id": "aYRqYXmmPLFfbcwC2KAULa",
  "region": "ET16",
  "sub_region": "ET1600",
  "created_at": 1738571570000,
  "submission_uuid": "1da1623d-6b3c-4633-aaa3-c49761e2a8de"
}
```

### Submission raw_data Key Fields

| Key | Label | Example |
|-----|-------|---------|
| `full_name` | Farmer | "Alda Aldb Aldc" |
| `region` | Region code | "ET16" |
| `woreda` | Woreda code | "ET1600" |
| `kebele` | Kebele code | "ET160005" |
| `enumerator_id` | Enumerator | "enum_003" |
| `age_of_farmer` | Age | "31" |
| `Phone_Number` | Phone | "0963487512" |
| `boundary_mapping/boundary_method` | Method | "manual" |
| `geoshape_accuracy` | Accuracy | "0.0" |
| `numpoints` | Points | "4" |
| `validate_polygon_manual` | Raw polygon | "lat lon alt acc;..." |
| `start`, `end` | Form fill times | ISO 8601 |
| `_attachments[].download_medium_url` | Photo URL | Kobo URL |

### Backend Status Gap

The current `Plot` model has `is_draft` (boolean) but no explicit `status` field. Mapping:
- `is_draft: true` → "on_hold"
- `is_draft: false` → "approved"
- No `rejected` state exists yet

**Future backend work needed:** Add `status` CharField with choices `('on_hold', 'approved', 'rejected')` and a `reviewer_notes` TextField.

---

## File Summary

### New Files (14)

| File | Purpose |
|------|---------|
| `frontend/src/lib/wkt-parser.js` | WKT ↔ Leaflet coordinate conversion |
| `frontend/src/lib/plot-utils.js` | Plot status helper, bbox calculator |
| `frontend/src/hooks/usePlots.js` | Plot data fetching hook |
| `frontend/src/hooks/useMapState.js` | Map page UI state management |
| `frontend/src/components/map/map-container-dynamic.js` | SSR-safe dynamic import |
| `frontend/src/components/map/map-view.js` | Core Leaflet map with satellite tiles |
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

### Modified Files (1)

| File | Change |
|------|--------|
| `frontend/src/app/dashboard/map/page.js` | Rewrite from stub to full page orchestrator |

### Generated Files (3)

| File | Source |
|------|--------|
| `frontend/src/components/ui/dialog.jsx` | `npx shadcn@latest add dialog` |
| `frontend/src/components/ui/textarea.jsx` | `npx shadcn@latest add textarea` |
| `frontend/src/components/ui/scroll-area.jsx` | `npx shadcn@latest add scroll-area` |

### Existing Components Reused

| Component | Path |
|-----------|------|
| `StatusBadge` | `frontend/src/components/status-badge.js` |
| `Tabs/TabsList/TabsTrigger` | `frontend/src/components/ui/tabs.jsx` |
| `Button` | `frontend/src/components/ui/button.jsx` |
| `Card` | `frontend/src/components/ui/card.jsx` |
| `Select` | `frontend/src/components/ui/select.jsx` |
| `Badge` | `frontend/src/components/ui/badge.jsx` |
| `Skeleton` | `frontend/src/components/ui/skeleton.jsx` |
| `Input` | `frontend/src/components/ui/input.jsx` |
| `Label` | `frontend/src/components/ui/label.jsx` |
| `useForms` context | `frontend/src/hooks/useForms.js` |
| `api` client | `frontend/src/lib/api.js` |
| `cn()` | `frontend/src/lib/utils.js` |

---

## Implementation Sequence

Execute in order — each step maintains a working state:

| Step | Phase | Key Deliverable |
|------|-------|-----------------|
| 1 | Dependencies | `yarn add` + shadcn components + WKT parser + usePlots hook |
| 2 | Basic map | Satellite tiles render, plots show as polygons |
| 3 | Left panel list | Plot cards, status tabs, sort, search, click → select |
| 4 | Left panel detail | Metadata grid, submission enrichment, approve/reject buttons |
| 5 | Dialogs | Approval modal, rejection modal, toast notifications, API calls |
| 6 | Geometry editing | Edit layer, vertex drag, save/cancel toolbar |
| 7 | Polish | Loading skeletons, empty states, error handling, responsive |

---

## Verification

### Automated
```bash
docker-compose exec frontend yarn build    # Production build succeeds
docker-compose exec frontend yarn lint     # ESLint passes
docker-compose exec frontend yarn test     # Tests pass
```

### Manual Checklist
1. Navigate to `/dashboard/map` — map renders with satellite imagery
2. Plot polygons visible on map, color-coded by status
3. Left panel shows plot list with count, tabs, sort dropdown
4. Click "On hold" tab — filters to on_hold plots only
5. Click a plot card — left panel switches to detail view, map zooms to plot
6. Detail panel shows metadata (farmer name, region, enumerator, dates)
7. Click "Approve" → dialog opens matching `Approve-modal.png` design
8. Confirm approval → plot updates to approved, toast notification shown
9. Click "Reject" → dialog opens with reason textarea
10. Click back arrow → returns to plot list
11. Click "Fix Geometry" → edit mode activates, vertices draggable
12. Drag vertex → save → polygon updates, toast shown
13. Resize browser to mobile → layout stacks or drawer appears
14. Navigate away and back → state resets cleanly
