export function getPlotStatus(plot) {
  if (plot.approval_status === 1) return "approved";
  if (plot.approval_status === 2) return "rejected";
  return "pending";
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
