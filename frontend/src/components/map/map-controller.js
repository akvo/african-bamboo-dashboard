"use client";

import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import { parseWktPolygon } from "@/lib/wkt-parser";

export default function MapController({ selectedPlot, allPlots }) {
  const map = useMap();
  const hasFittedInitial = useRef(false);

  useEffect(() => {
    if (selectedPlot) {
      const coords = parseWktPolygon(selectedPlot.polygon_wkt);
      if (coords.length > 0) {
        map.fitBounds(L.latLngBounds(coords), { padding: [50, 50] });
      }
    } else if (!hasFittedInitial.current && allPlots.length > 0) {
      const allCoords = allPlots.flatMap((p) => parseWktPolygon(p.polygon_wkt));
      if (allCoords.length > 0) {
        map.fitBounds(L.latLngBounds(allCoords), { padding: [30, 30] });
        hasFittedInitial.current = true;
      }
    }
  }, [selectedPlot, allPlots, map]);

  return null;
}
