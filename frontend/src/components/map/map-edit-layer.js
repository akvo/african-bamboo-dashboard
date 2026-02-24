"use client";

import L from "leaflet";
import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import { parseWktPolygon } from "@/lib/wkt-parser";

const EDIT_STYLE = { color: "#F97316", weight: 3, fillOpacity: 0.25 };
const MIN_VERTICES = 3;

export default function MapEditLayer({ plot, setEditedGeo, onNotify }) {
  const map = useMap();
  const polygonRef = useRef(null);
  const setEditedGeoRef = useRef(setEditedGeo);
  const onNotifyRef = useRef(onNotify);

  // Keep callback refs current without re-running the effect
  useEffect(() => {
    setEditedGeoRef.current = setEditedGeo;
  }, [setEditedGeo]);
  useEffect(() => {
    onNotifyRef.current = onNotify;
  }, [onNotify]);

  useEffect(() => {
    if (!plot || !map) return;

    const coords = plot.coords || parseWktPolygon(plot.polygon_wkt);
    if (coords.length === 0) return;

    // Create polygon imperatively so react-leaflet re-renders
    // cannot reset latLngs and fight with leaflet-editable drag state
    const polygon = L.polygon(coords, EDIT_STYLE).addTo(map);
    polygonRef.current = polygon;

    let dragged = false;

    polygon.enableEdit();

    polygon.on("editable:vertex:dragstart", () => {
      dragged = true;
    });

    polygon.on("editable:editing", () => {
      const latlngs = polygon.getLatLngs()[0];
      setEditedGeoRef.current(latlngs.map((l) => [l.lat, l.lng]));
    });

    polygon.on("editable:vertex:click", (e) => {
      if (dragged) {
        dragged = false;
        return;
      }
      const latlngs = polygon.getLatLngs()[0];
      if (latlngs.length <= MIN_VERTICES) {
        onNotifyRef.current?.({
          message: `Cannot delete vertex — a polygon requires at least ${MIN_VERTICES} vertices`,
          type: "warning",
        });
        return;
      }
      e.vertex.delete();
    });

    return () => {
      polygon.disableEdit();
      polygon.off();
      polygon.remove();
      polygonRef.current = null;
    };
  }, [plot?.uuid, plot?.polygon_wkt, map]); // eslint-disable-line react-hooks/exhaustive-deps

  return null;
}
