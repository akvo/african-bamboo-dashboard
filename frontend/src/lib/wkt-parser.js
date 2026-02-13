/**
 * WKT uses (longitude latitude) order.
 * Leaflet uses [latitude, longitude].
 */

export function parseWktPolygon(wkt) {
  if (!wkt) return [];
  const match = wkt.match(/POLYGON\s*\(\((.+)\)\)/i);
  if (!match) return [];
  return match[1].split(",").map((pair) => {
    const [lon, lat] = pair.trim().split(/\s+/).map(Number);
    return [lat, lon];
  });
}

export function toWktPolygon(coords) {
  if (!coords || coords.length === 0) return "";
  const ring = coords.map(([lat, lon]) => `${lon} ${lat}`).join(", ");
  return `POLYGON((${ring}))`;
}
