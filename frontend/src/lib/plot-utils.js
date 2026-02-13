export function getPlotStatus(plot) {
  if (plot.status) return plot.status;
  return plot.is_draft ? "on_hold" : "approved";
}

export function calculateBbox(coords) {
  const lats = coords.map(([lat]) => lat);
  const lons = coords.map(([, lon]) => lon);
  return {
    min_lat: Math.min(...lats),
    max_lat: Math.max(...lats),
    min_lon: Math.min(...lons),
    max_lon: Math.max(...lons),
  };
}
