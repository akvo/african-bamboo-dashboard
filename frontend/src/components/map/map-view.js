"use client";

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import "leaflet-editable";
import {
  MapContainer,
  TileLayer,
  Polygon,
  Popup,
  ZoomControl,
} from "react-leaflet";
import { useMemo, useState } from "react";
import { Construction, Satellite } from "lucide-react";
import { parseWktPolygon } from "@/lib/wkt-parser";
import { getPlotStatus } from "@/lib/plot-utils";
import basemaps, { DEFAULT_BASEMAP } from "@/lib/basemap-config";
import MapController from "@/components/map/map-controller";
import MapEditLayer from "@/components/map/map-edit-layer";
import MapEditToolbar from "@/components/map/map-edit-toolbar";
import MapPopupCard from "@/components/map/map-popup-card";
import { PREFIX_SUBM_ID } from "@/lib/constants";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const POLYGON_STYLES = {
  pending: { color: "#EAB308", weight: 2, fillOpacity: 0.2 },
  approved: { color: "#16A34A", weight: 2, fillOpacity: 0.2 },
  rejected: { color: "#DC2626", weight: 2, fillOpacity: 0.2 },
  flagged: { color: "#E97316", weight: 2, fillOpacity: 0.2 },
  selected: { color: "#22D3EE", weight: 3, fillOpacity: 0.3 },
  editing: { color: "#F97316", weight: 3, fillOpacity: 0.25 },
};

const DEFAULT_CENTER = [7.05, 38.47];
const DEFAULT_ZOOM = 6;
const MAX_ZOOM = 22;

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

  const plotsWithCoords = useMemo(
    () =>
      plots.map((p) => ({
        ...p,
        coords: parseWktPolygon(p.polygon_wkt),
        status: getPlotStatus(p),
      })),
    [plots],
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

        {plotsWithCoords.map((plot) => {
          if (plot.coords.length === 0) return null;
          if (plot.uuid === editingPlotId) return null;

          const isSelected = selectedPlot?.uuid === plot.uuid;
          const style = isSelected
            ? POLYGON_STYLES.selected
            : POLYGON_STYLES[plot.status] || POLYGON_STYLES.pending;

          return (
            <Polygon
              key={plot.uuid}
              positions={plot.coords}
              pathOptions={style}
              eventHandlers={{
                click: () => onSelectPlot(plot.uuid),
              }}
            >
              {isSelected && (
                <Popup>
                  <MapPopupCard plot={plot} />
                </Popup>
              )}
            </Polygon>
          );
        })}

        {editingPlotId && (
          <MapEditLayer
            plot={plotsWithCoords.find((p) => p.uuid === editingPlotId)}
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
          plotName={(() => {
            const pid = plotsWithCoords.find(
              (p) => p.uuid === editingPlotId,
            )?.plot_id;
            return pid ? `${PREFIX_SUBM_ID}${pid}` : "—";
          })()}
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
