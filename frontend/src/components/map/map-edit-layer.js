"use client";

import L from "leaflet";
import { useCallback, useRef } from "react";
import { Polygon, FeatureGroup } from "react-leaflet";
import { parseWktPolygon } from "@/lib/wkt-parser";

const EDIT_STYLE = { color: "#F97316", weight: 3, fillOpacity: 0.25 };
const MIN_VERTICES = 3;
const EPSILON = 1e-9;

function cleanupVertexHandlers(polygon) {
  const handlers = polygon.editing?._verticesHandlers;
  if (!handlers?.length) return;
  const markerGroup = handlers[0]._markerGroup;
  if (!markerGroup) return;
  markerGroup.eachLayer((marker) => marker.off("contextmenu"));
}

function attachVertexDelete(polygon, setEditedGeo) {
  const handlers = polygon.editing?._verticesHandlers;
  if (!handlers?.length) return;

  const markerGroup = handlers[0]._markerGroup;
  if (!markerGroup) return;

  markerGroup.eachLayer((marker) => {
    // Only attach to real vertex markers, skip midpoint markers
    if (marker.options.opacity === 0) return;

    marker.on("contextmenu", (e) => {
      L.DomEvent.preventDefault(e);
      const latlngs = polygon.getLatLngs()[0];
      if (latlngs.length <= MIN_VERTICES) return;

      const markerLL = marker.getLatLng();
      const idx = latlngs.findIndex(
        (ll) =>
          Math.abs(ll.lat - markerLL.lat) < EPSILON &&
          Math.abs(ll.lng - markerLL.lng) < EPSILON,
      );
      if (idx === -1) return;

      latlngs.splice(idx, 1);
      polygon.setLatLngs([latlngs]);
      cleanupVertexHandlers(polygon);
      polygon.editing.disable();
      polygon.editing.enable();
      setEditedGeo(latlngs.map((l) => [l.lat, l.lng]));

      // Re-attach after editing handles are rebuilt
      attachVertexDelete(polygon, setEditedGeo);
    });
  });
}

export default function MapEditLayer({ plot, editedGeo, setEditedGeo }) {
  const prevRef = useRef(null);

  const polygonRef = useCallback(
    (polygon) => {
      // Cleanup previous instance
      if (prevRef.current) {
        cleanupVertexHandlers(prevRef.current);
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
      attachVertexDelete(polygon, setEditedGeo);
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
