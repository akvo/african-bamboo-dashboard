"use client";

import { useCallback, useRef } from "react";
import { Polygon, FeatureGroup } from "react-leaflet";
import { parseWktPolygon } from "@/lib/wkt-parser";

const EDIT_STYLE = { color: "#F97316", weight: 3, fillOpacity: 0.25 };

export default function MapEditLayer({ plot, editedGeo, setEditedGeo }) {
  const prevRef = useRef(null);

  const polygonRef = useCallback(
    (polygon) => {
      // Cleanup previous instance
      if (prevRef.current) {
        prevRef.current.editing?.disable();
        prevRef.current.off("edit");
        prevRef.current = null;
      }

      if (!polygon) return;
      polygon.editing?.enable();

      const handleEdit = () => {
        const latlngs = polygon.getLatLngs()[0];
        const newGeo = latlngs.map((l) => [l.lat, l.lng]);
        setEditedGeo(newGeo);
      };

      polygon.on("edit", handleEdit);
      prevRef.current = polygon;
    },
    [setEditedGeo],
  );

  if (!plot) return null;

  const coords = editedGeo || plot.coords || parseWktPolygon(plot.polygon_wkt);
  if (coords.length === 0) return null;

  return (
    <FeatureGroup>
      <Polygon ref={polygonRef} positions={coords} pathOptions={EDIT_STYLE} />
    </FeatureGroup>
  );
}
