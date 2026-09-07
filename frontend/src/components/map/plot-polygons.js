"use client";

import { Polygon, Popup } from "react-leaflet";
import { POLYGON_STYLES } from "@/lib/map-styles";
import MapPopupCard from "@/components/map/map-popup-card";

/**
 * Draws every plot feature the map knows about.
 *
 * Features arrive already parsed and de-duplicated from
 * usePlotFeatures, so this component only decides styling and
 * which one owns the popup.
 */
export default function PlotPolygons({
  features,
  selectedUuid,
  editingPlotId,
  onSelectPlot,
}) {
  return features.map((plot) => {
    // The plot being edited is drawn by MapEditLayer instead,
    // which owns its own editable geometry.
    if (plot.uuid === editingPlotId) {
      return null;
    }

    const isSelected = selectedUuid === plot.uuid;
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
  });
}
