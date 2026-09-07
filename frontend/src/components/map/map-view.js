"use client";

// Side-effect imports (Leaflet CSS, leaflet-editable) live in
// one module so their order is explicit and the CSS cannot be
// pulled in twice from different components.
import "@/lib/leaflet-setup";

import { MapContainer, TileLayer, ZoomControl } from "react-leaflet";
import { useMemo, useState } from "react";
import { Construction, Satellite } from "lucide-react";
import basemaps, { DEFAULT_BASEMAP } from "@/lib/basemap-config";
import { DEFAULT_CENTER, DEFAULT_ZOOM, MAX_ZOOM } from "@/lib/map-styles";
import usePlotFeatures from "@/hooks/usePlotFeatures";
import MapController from "@/components/map/map-controller";
import MapEditLayer from "@/components/map/map-edit-layer";
import MapEditToolbar from "@/components/map/map-edit-toolbar";
import PlotPolygons from "@/components/map/plot-polygons";
import { PREFIX_SUBM_ID } from "@/lib/constants";

export default function MapView({
  plots,
  selectedPlot,
  editingPlotId,
  editedGeo,
  setEditedGeo,
  onSelectPlot,
  onSaveEdit,
  onCancelEdit,
  onReset,
  isResetting,
  onNotify,
}) {
  const [basemap, setBasemap] = useState(DEFAULT_BASEMAP);
  const tile = useMemo(
    () => basemaps.find((b) => b.id === basemap) || basemaps[0],
    [basemap],
  );

  const features = usePlotFeatures(plots, selectedPlot);
  const editingFeature = useMemo(
    () => features.find((p) => p.uuid === editingPlotId),
    [features, editingPlotId],
  );

  return (
    <div className="relative h-full w-full isolate">
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        maxZoom={MAX_ZOOM}
        className="h-full w-full [&_.leaflet-bottom.leaflet-right]:!bottom-[6%]"
        zoomControl={false}
        editable={true}
      >
        <ZoomControl position="bottomright" />
        <TileLayer
          key={tile.id}
          url={tile.url}
          attribution={tile.attribution}
          tileSize={tile.tileSize}
          zoomOffset={tile.zoomOffset}
          maxNativeZoom={tile.maxNativeZoom}
          maxZoom={MAX_ZOOM}
        />

        <MapController selectedPlot={selectedPlot} allPlots={plots} />

        <PlotPolygons
          features={features}
          selectedUuid={selectedPlot?.uuid}
          editingPlotId={editingPlotId}
          onSelectPlot={onSelectPlot}
        />

        {editingPlotId && (
          <MapEditLayer
            plot={editingFeature}
            setEditedGeo={setEditedGeo}
            onNotify={onNotify}
          />
        )}
      </MapContainer>

      <div className="absolute top-3 right-3 z-[1000] flex flex-col gap-1">
        {basemaps.map((b) => (
          <button
            key={b.id}
            type="button"
            onClick={() => setBasemap(b.id)}
            className={`cursor-pointer flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium shadow-sm transition-colors ${
              basemap === b.id
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-background text-foreground hover:bg-accent"
            }`}
          >
            {b.id === "satellite" ? (
              <Satellite className="size-3.5" />
            ) : (
              <Construction className="size-3.5" />
            )}
            {b.label}
          </button>
        ))}
      </div>

      {editingPlotId && (
        <MapEditToolbar
          plotName={
            editingFeature?.plot_id
              ? `${PREFIX_SUBM_ID}${editingFeature.plot_id}`
              : "—"
          }
          onSave={onSaveEdit}
          onCancel={onCancelEdit}
          onReset={onReset}
          isResetting={isResetting}
          hasChanges={editedGeo !== null}
        />
      )}
    </div>
  );
}
