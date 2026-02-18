# Technical Execution Plan: Polygon Editing Enhancements

> **Status: IMPLEMENTED**

## Context

The map page (`frontend/src/app/dashboard/map/page.js`) already supports basic polygon editing via Leaflet.Draw's `.editing.enable()` — users can drag vertices to reposition them. This plan extends that into a full polygon editing workflow: add/delete/move vertices, switch basemap layers, reset to original geometry, and confirm before overwriting.

The raw data in Kobo remains the source of truth. Edits overwrite `polygon_wkt` in the local database. The original geometry can always be re-derived from `Submission.raw_data`.

---

## Phase 1: Backend — Reset Polygon Endpoint

Add a `reset_polygon` action to `PlotViewSet` that re-derives the polygon from the linked submission's `raw_data`.

### Implementation

**`backend/api/v1/v1_odk/views.py`** — Add `reset_polygon` action to `PlotViewSet` with `@extend_schema` for Swagger docs:

```python
@extend_schema(
    tags=["ODK"],
    summary="Reset polygon to original from Kobo",
)
@action(detail=True, methods=["post"])
def reset_polygon(self, request, uuid=None):
    plot = self.get_object()
    if not plot.submission:
        return Response(
            {"message": "No linked submission"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    plot_data = extract_plot_data(
        plot.submission.raw_data, plot.form
    )
    plot.polygon_wkt = plot_data["polygon_wkt"]
    plot.min_lat = plot_data["min_lat"]
    plot.max_lat = plot_data["max_lat"]
    plot.min_lon = plot_data["min_lon"]
    plot.max_lon = plot_data["max_lon"]
    plot.save()
    return Response(PlotSerializer(plot).data)
```

This calls the existing `extract_plot_data()` utility from `utils/polygon.py` which handles ODK geoshape parsing, validation, WKT conversion, and bbox computation. No new utilities needed.

### Files changed

| File | Change |
|------|--------|
| `backend/api/v1/v1_odk/views.py` | Add `reset_polygon` action to `PlotViewSet` |

### New files

| File | Purpose |
|------|---------|
| `backend/api/v1/v1_odk/tests/tests_plots_reset_endpoint.py` | Tests for the reset endpoint |

### Test cases

1. **Happy path** — Reset restores original polygon from submission raw_data
2. **No linked submission** — Returns 400 with error message
3. **Submission with no polygon data** — Resets to null geometry fields (valid behavior — plots are always kept)
4. **Authentication required** — Unauthenticated request returns 401

---

## Phase 2: Frontend — Save Confirmation Dialog

Add an "Are you sure?" confirmation dialog before saving edited polygons.

### Implementation

**New component:** `frontend/src/components/map/save-edit-dialog.js`

Follow the existing pattern from `approval-dialog.js`:
- Radix `Dialog` with `DialogContent`, `DialogHeader`, `DialogFooter`
- Save icon from lucide-react in a circular header
- Title: "Save polygon changes?"
- Description: "This will overwrite the current polygon geometry. The original data in Kobo remains unchanged."
- Two buttons: "Cancel" and "Confirm Save"
- Loading state while saving (`isSubmitting`)

**Wire into map page:**

```
MapEditToolbar "Save" button
    → calls handleSaveClick() which sets saveDialogOpen = true
        → "Confirm Save" calls handleSaveEdit() then closes dialog
        → "Cancel" closes dialog (stays in edit mode)
```

### Files changed

| File | Change |
|------|--------|
| `frontend/src/app/dashboard/map/page.js` | Add `saveDialogOpen` state, `handleSaveClick` opens dialog, dialog confirm calls `handleSaveEdit` |

### New files

| File | Purpose |
|------|---------|
| `frontend/src/components/map/save-edit-dialog.js` | "Are you sure?" confirmation dialog before saving polygon edits |

---

## Phase 3: Frontend — Basemap Toggle (Dropdown)

Add a dropdown control to switch between satellite imagery and street map tiles, driven by a configurable basemap array.

### Implementation

**Basemap configuration:** `frontend/src/lib/basemap-config.js`

Tile layer options are defined as a configurable array, each entry containing `id`, `label`, `url`, `attribution`, `tileSize`, `zoomOffset`, and `maxNativeZoom`. New basemaps can be added without touching component code.

```javascript
const basemaps = [
  {
    id: "satellite",
    label: "Satellite",
    url: "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{z}/{x}/{y}?access_token=...",
    attribution: '... Mapbox ... Maxar',
    tileSize: 512,
    zoomOffset: -1,
    maxNativeZoom: 21,
  },
  {
    id: "street",
    label: "Street",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: '... OpenStreetMap contributors',
    tileSize: 256,
    zoomOffset: 0,
    maxNativeZoom: 19,
  },
];
export const DEFAULT_BASEMAP = "satellite";
```

Using OSM for the street layer avoids consuming Mapbox quota. No additional API keys needed.

**`map-view.js`** — Resolves the active tile config via `useMemo` from the basemaps array. A single `<TileLayer>` renders with a `key` prop to force re-mount on switch. Passes `maxNativeZoom` to prevent tile bounce at high zoom levels. The map wrapper div uses `isolate` class to create a stacking context so Leaflet's internal z-indices don't interfere with the filter bar or dropdowns.

```jsx
const tile = useMemo(
  () => basemaps.find((b) => b.id === basemap) || basemaps[0],
  [basemap],
);

<TileLayer
  key={tile.id}
  url={tile.url}
  attribution={tile.attribution}
  tileSize={tile.tileSize}
  zoomOffset={tile.zoomOffset}
  maxNativeZoom={tile.maxNativeZoom}
  maxZoom={MAX_ZOOM}
/>
```

**`map-filter-bar.js`** — Uses the existing shadcn `Select` dropdown to render basemap options from the config array. Accepts `basemap` and `onBasemapChange` props. Removed the old `stopLeafletPropagation` helper — z-index layering with `isolate` handles event separation.

### Files changed

| File | Change |
|------|--------|
| `frontend/src/components/map/map-view.js` | Accept `basemap` prop, single `TileLayer` driven by config, `isolate` stacking context, `maxZoom` on `MapContainer` |
| `frontend/src/components/map/map-filter-bar.js` | Replace Reset button with basemap `Select` dropdown from config array |
| `frontend/src/app/dashboard/map/page.js` | Add `basemap` state, pass to `MapFilterBar` and `MapContainerDynamic` |
| `frontend/src/components/ui/select.jsx` | Bump `SelectContent` z-index from `z-50` to `z-[1000]` (Leaflet panes use 200-650+) |

### New files

| File | Purpose |
|------|---------|
| `frontend/src/lib/basemap-config.js` | Configurable array of tile layer options |

---

## Phase 4: Frontend — Enhanced Polygon Editing (Add / Delete Vertices)

Enhance `MapEditLayer` to support adding and deleting polygon vertices, in addition to the existing move (drag) capability.

### Critical discovery: missing leaflet-draw JS import

The original code only imported the CSS (`import "leaflet-draw/dist/leaflet.draw.css"`) but not the JavaScript. Without `import "leaflet-draw"`, the `L.Polyline.addInitHook` that patches `L.Polygon` with `.editing` never ran, so `polygon.editing` was always `undefined`. All editing features were silently broken.

**Fix in `map-view.js`:**
```javascript
import "leaflet-draw";  // JS — registers .editing on L.Polygon
import "leaflet-draw/dist/leaflet.draw.css";
```

### Adding vertices

Leaflet.Draw's editing mode renders midpoint ghost handles between vertices. Dragging a midpoint inserts a new vertex. This works automatically with `.editing.enable()` once the JS is properly imported.

### Deleting vertices

Right-click (context menu) on vertex markers deletes them. Implemented as a recursive `attachVertexDelete()` function in `map-edit-layer.js`:

```javascript
function attachVertexDelete(polygon, setEditedGeo) {
  const handlers = polygon.editing?._verticesHandlers;
  if (!handlers?.length) return;
  const markerGroup = handlers[0]._markerGroup;
  if (!markerGroup) return;

  markerGroup.eachLayer((marker) => {
    if (marker.options.opacity === 0) return; // skip midpoint markers
    marker.on("contextmenu", (e) => {
      L.DomEvent.preventDefault(e);
      const latlngs = polygon.getLatLngs()[0];
      if (latlngs.length <= MIN_VERTICES) return;
      // ... find and splice vertex, re-enable editing, re-attach
      attachVertexDelete(polygon, setEditedGeo);
    });
  });
}
```

Key differences from the original plan:
- **Vertex handler path**: `polygon.editing._verticesHandlers` (not `polygon.editing._poly.editing._verticesHandlers`)
- **Midpoint filter**: Uses `marker.options.opacity === 0` to skip ghost markers
- **Recursive re-attach**: After disabling/enabling editing, vertex handles are rebuilt — `attachVertexDelete` calls itself to re-bind context menu handlers

### Visual hint

`MapEditToolbar` shows helper text below the buttons: "Drag vertices to move · Drag midpoints to add · Right-click vertex to delete". Toolbar repositioned from `top-2` to `top-16` to avoid overlapping the filter bar.

### Files changed

| File | Change |
|------|--------|
| `frontend/src/components/map/map-view.js` | Add `import "leaflet-draw"` JS import |
| `frontend/src/components/map/map-edit-layer.js` | Add `attachVertexDelete()` with right-click vertex deletion |
| `frontend/src/components/map/map-edit-toolbar.js` | Add editing hint text, reposition to `top-16` |

---

## Phase 5: Frontend — Reset Polygon to Original

Add the ability to reset a polygon to its original geometry (as synced from Kobo) and continue editing.

### Implementation

**`map-edit-toolbar.js`** — Add a "Reset" button with `secondary` variant before Save/Cancel. Accept `onReset` and `isResetting` props. Shows "Resetting..." while in progress.

**`map/page.js`** — Add `handleResetPolygon` callback with `isResetting` loading state:

```javascript
const handleResetPolygon = useCallback(async () => {
  if (!mapState.editingPlotId) return;
  setIsResetting(true);
  try {
    await api.post(`/v1/odk/plots/${mapState.editingPlotId}/reset_polygon/`);
    setEditedGeo(null);    // clear local edits
    await refetch();       // fetch fresh plot data
    mapState.setToastMessage("Polygon reset to original");
  } catch {
    mapState.setToastMessage("Failed to reset polygon. Please try again.");
  } finally {
    setIsResetting(false);
  }
}, [mapState, refetch]);
```

The flow is:
1. User clicks "Reset" in the edit toolbar
2. `POST /v1/odk/plots/{uuid}/reset_polygon/` restores the original geometry
3. `editedGeo` is cleared so the map re-renders from the fresh `polygon_wkt`
4. User remains in edit mode and can continue editing or save

### Files changed

| File | Change |
|------|--------|
| `frontend/src/components/map/map-edit-toolbar.js` | Add "Reset" button with `onReset`/`isResetting` props |
| `frontend/src/app/dashboard/map/page.js` | Add `handleResetPolygon` callback with loading state, pass to toolbar |

---

## Additional Fixes (discovered during implementation)

### Fix: Dashboard table not loading on direct URL

**Problem:** `useSubmissions` used `isLoading` as a control-flow gate for fetching. On direct URL load, `activeForm` is null initially → hook sets `isLoading = false` → when form loads, the state gate prevents fetching due to React's async state updates.

**Fix in `useSubmissions.js`:** Removed `isLoading` as control gate. `isLoading` is now purely a UI indicator. Uses a ref (`prevAssetUid`) to detect form changes and reset offset. Fetches whenever `assetUid`/`offset` change — the standard React pattern.

### Fix: Dashboard table row click navigates to map

**Problem:** `submissions-table.js` created local `usePlots`/`useMapState` instances disconnected from the map page — clicking did nothing visible.

**Fix:** Removed local hooks. Table now accepts `plots` as a prop, uses `useRouter` to navigate to `/dashboard/map?plot=<plotUuid>` by matching submission UUID to plot's `submission_uuid`.

### Fix: Deep-link plot selection without map bounce

**Problem:** Navigating to `/dashboard/map?plot=<uuid>` caused the map to bounce — `MapController` first fit to all plots, then re-fit to the selected plot.

**Fix in `useMapState.js`:** Accept `initialPlotId` parameter. `selectedPlotId` and `panelMode` are initialized from the URL query param synchronously, so `MapController` never enters the fit-to-all branch.

**Fix in `map-controller.js`:** Added `fitWhenReady()` helper that checks `map.getSize().x > 0` before calling `fitBounds`. If the map container hasn't rendered yet (dynamic import), defers to `map.whenReady()`.

### Fix: Select dropdown hidden behind Leaflet map

**Problem:** Radix `SelectContent` portals to `<body>` with `z-50` (z-index: 50). Leaflet internal panes use z-indices 200-650+. Dropdowns rendered behind the map.

**Fix in `select.jsx`:** Bumped `SelectContent` from `z-50` to `z-[1000]`.

### Files changed (additional fixes)

| File | Change |
|------|--------|
| `frontend/src/hooks/useSubmissions.js` | Rewrite fetch logic to standard dependency-change pattern |
| `frontend/src/components/submissions-table.js` | Navigate to map page with plot UUID query param |
| `frontend/src/app/dashboard/page.js` | Pass `plots` to `SubmissionsTable` via `usePlots` hook |
| `frontend/src/hooks/useMapState.js` | Accept `initialPlotId` for deep-link support |
| `frontend/src/components/map/map-controller.js` | Add `fitWhenReady()` for async map mount |
| `frontend/src/components/ui/select.jsx` | Bump `SelectContent` z-index to `z-[1000]` |

---

## All Files Changed

### Backend

| File | Phase | Change |
|------|-------|--------|
| `backend/api/v1/v1_odk/views.py` | 1 | Add `reset_polygon` action to `PlotViewSet` |

### Backend — New Files

| File | Phase | Purpose |
|------|-------|---------|
| `backend/api/v1/v1_odk/tests/tests_plots_reset_endpoint.py` | 1 | Tests for reset polygon endpoint |

### Frontend — Modified Files

| File | Phase(s) | Change |
|------|----------|--------|
| `frontend/src/app/dashboard/map/page.js` | 2, 3, 5, fix | Save dialog, basemap state, reset handler, deep-link via `initialPlotId` |
| `frontend/src/app/dashboard/page.js` | fix | Pass `plots` to `SubmissionsTable` |
| `frontend/src/components/map/map-view.js` | 3, 4 | Basemap from config, `isolate` stacking, `maxZoom`/`maxNativeZoom`, `import "leaflet-draw"` |
| `frontend/src/components/map/map-filter-bar.js` | 3 | Basemap `Select` dropdown from config array |
| `frontend/src/components/map/map-edit-layer.js` | 4 | Vertex delete via right-click with recursive re-attach |
| `frontend/src/components/map/map-edit-toolbar.js` | 4, 5 | Editing hints, Reset button, repositioned to `top-16` |
| `frontend/src/components/map/map-controller.js` | fix | `fitWhenReady()` for async map mount |
| `frontend/src/components/submissions-table.js` | fix | Navigate to map with plot UUID |
| `frontend/src/components/ui/select.jsx` | fix | z-index `z-[1000]` for Leaflet compatibility |
| `frontend/src/hooks/useMapState.js` | fix | Accept `initialPlotId` for deep-link |
| `frontend/src/hooks/useSubmissions.js` | fix | Fix fetch logic for direct URL loading |

### Frontend — New Files

| File | Phase | Purpose |
|------|-------|---------|
| `frontend/src/components/map/save-edit-dialog.js` | 2 | Save confirmation dialog |
| `frontend/src/lib/basemap-config.js` | 3 | Configurable basemap tile layer array |

---

## Verification

### Automated

```bash
docker compose exec backend python manage.py test api.v1.v1_odk.tests.tests_plots_reset_endpoint
docker compose exec backend flake8
docker compose exec frontend yarn build
docker compose exec frontend yarn lint
```

### Manual Checklist

**Phase 1 — Reset endpoint:**
1. Edit a polygon and save → polygon_wkt changes in DB
2. Call `POST /api/v1/odk/plots/{uuid}/reset_polygon/` → polygon_wkt restored to original from Kobo data
3. Plot with no submission → returns 400

**Phase 2 — Save confirmation:**
4. Enter edit mode → drag vertex → click Save → confirmation dialog appears
5. Click Cancel in dialog → stays in edit mode, no save
6. Click Confirm → polygon saved, toast shown, edit mode exits

**Phase 3 — Basemap toggle:**
7. Default map loads with satellite imagery
8. Select "Street" from dropdown → street tiles render
9. Select "Satellite" from dropdown → satellite tiles render
10. Toggle preserves current zoom level and center position
11. No tile bounce at high zoom levels (maxNativeZoom upscaling)

**Phase 4 — Add/delete vertices:**
12. Enter edit mode → midpoint handles visible between vertices
13. Drag a midpoint → new vertex created at that position
14. Right-click a vertex → vertex removed, polygon updates
15. Try to delete when only 3 vertices remain → deletion prevented
16. Save after add/delete → updated polygon saved correctly

**Phase 5 — Reset to original:**
17. Edit a polygon → drag vertices → click Reset → polygon restores to original shape
18. After reset, still in edit mode → can continue editing
19. Save after reset → saves the original (unedited) geometry

**Additional fixes:**
20. Navigate to `/dashboard` directly (not via sidebar) → submissions table loads
21. Click a row in the submissions table → navigates to `/dashboard/map?plot=<uuid>` and map zooms to that plot
22. Open `/dashboard/map?plot=<uuid>` directly → map opens with plot selected (no bounce)
23. Click Back in plot detail → URL query param is cleared
24. Basemap dropdown and form selector are clickable on the map (not blocked by Leaflet)
