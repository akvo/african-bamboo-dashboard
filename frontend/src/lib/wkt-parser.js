/**
 * WKT uses (longitude latitude) order.
 * Leaflet uses [latitude, longitude].
 */

export function parseWktPolygon(wkt) {
  if (!wkt) return [];
  const match = wkt.match(/POLYGON\s*\(\((.+)\)\)/i);
  if (!match) return [];
  return match[1].split(",").reduce((acc, pair) => {
    const [lon, lat] = pair.trim().split(/\s+/).map(Number);
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      acc.push([lat, lon]);
    }
    return acc;
  }, []);
}

export function toWktPolygon(coords) {
  if (!coords || coords.length === 0) return "";
  const ring = coords.map(([lat, lon]) => `${lon} ${lat}`).join(", ");
  return `POLYGON((${ring}))`;
}
