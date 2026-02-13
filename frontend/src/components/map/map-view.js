"use client";

import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";

import L from "leaflet";
import {
  MapContainer,
  TileLayer,
  Polygon,
  Popup,
  ZoomControl,
} from "react-leaflet";
import { useMemo } from "react";
import { parseWktPolygon } from "@/lib/wkt-parser";
import { getPlotStatus } from "@/lib/plot-utils";
import MapController from "@/components/map/map-controller";
import MapEditLayer from "@/components/map/map-edit-layer";
import MapEditToolbar from "@/components/map/map-edit-toolbar";
import MapPopupCard from "@/components/map/map-popup-card";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const POLYGON_STYLES = {
  on_hold: { color: "#EAB308", weight: 2, fillOpacity: 0.2 },
  approved: { color: "#16A34A", weight: 2, fillOpacity: 0.2 },
  rejected: { color: "#DC2626", weight: 2, fillOpacity: 0.2 },
  selected: { color: "#22D3EE", weight: 3, fillOpacity: 0.3 },
  editing: { color: "#F97316", weight: 3, fillOpacity: 0.25 },
};

const ESRI_TILE_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const ESRI_ATTRIBUTION =
  "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community";

const DEFAULT_CENTER = [7.05, 38.47];
const DEFAULT_ZOOM = 6;

export default function MapView({
  plots,
  selectedPlot,
  editingPlotId,
  editedGeo,
  setEditedGeo,
  onSelectPlot,
  onSaveEdit,
  onCancelEdit,
}) {
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
    <div className="relative h-full w-full">
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        className="h-full w-full"
        zoomControl={false}
      >
        <ZoomControl position="bottomright" />
        <TileLayer url={ESRI_TILE_URL} attribution={ESRI_ATTRIBUTION} />

        <MapController selectedPlot={selectedPlot} allPlots={plots} />

        {plotsWithCoords.map((plot) => {
          if (plot.coords.length === 0) return null;
          if (plot.uuid === editingPlotId) return null;

          const isSelected = selectedPlot?.uuid === plot.uuid;
          const style = isSelected
            ? POLYGON_STYLES.selected
            : POLYGON_STYLES[plot.status] || POLYGON_STYLES.on_hold;

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
            editedGeo={editedGeo}
            setEditedGeo={setEditedGeo}
          />
        )}
      </MapContainer>

      {editingPlotId && (
        <MapEditToolbar
          plotName={
            plotsWithCoords.find((p) => p.uuid === editingPlotId)?.plot_name
          }
          onSave={onSaveEdit}
          onCancel={onCancelEdit}
          hasChanges={editedGeo !== null}
        />
      )}
    </div>
  );
}
