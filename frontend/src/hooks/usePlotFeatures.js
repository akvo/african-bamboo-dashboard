import { useMemo } from "react";
import { parseWktPolygon } from "@/lib/wkt-parser";
import { getPlotStatus } from "@/lib/plot-utils";

/**
 * One source of truth for what the map draws.
 *
 * The map has two overlapping inputs: `plots`, which the status
 * tab filters, and `selectedPlot`, fetched on its own by uuid.
 * Approving, rejecting or reverting the open plot changes its
 * status, so the next refetch drops it from the filtered list
 * and its polygon used to vanish while the detail panel stayed
 * open. Merging both here, rather than in the component, keeps
 * "which features exist" in one place.
 *
 * `selectedPlot` wins on conflict: it is refetched on every
 * status change, so it is the fresher copy.
 *
 * The memo key is built from the fields that actually affect
 * rendering, not object identity. A refetch that returns
 * equal-but-new objects therefore does not re-parse any WKT or
 * hand Leaflet new coordinate arrays, which is what made
 * polygons visibly redraw on unrelated updates.
 */
export default function usePlotFeatures(plots, selectedPlot) {
  const signature = useMemo(() => {
    const parts = (plots || []).map(
      (p) => `${p.uuid}:${p.approval_status}:${p.polygon_wkt}`,
    );
    if (selectedPlot) {
      parts.push(
        `sel:${selectedPlot.uuid}:` +
          `${selectedPlot.approval_status}:` +
          `${selectedPlot.polygon_wkt}`,
      );
    }
    return parts.join("|");
  }, [plots, selectedPlot]);

  return useMemo(
    () => {
      const byUuid = new Map();
      for (const plot of plots || []) {
        byUuid.set(plot.uuid, plot);
      }
      if (selectedPlot?.uuid && selectedPlot.polygon_wkt) {
        byUuid.set(selectedPlot.uuid, selectedPlot);
      }

      return Array.from(byUuid.values())
        .map((plot) => ({
          ...plot,
          coords: parseWktPolygon(plot.polygon_wkt),
          status: getPlotStatus(plot),
        }))
        .filter((plot) => plot.coords.length > 0);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [signature],
  );
}
