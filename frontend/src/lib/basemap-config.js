const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

const basemaps = [
  {
    id: "satellite",
    label: "Satellite",
    url:
      "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{z}/{x}/{y}" +
      `?access_token=${MAPBOX_TOKEN}`,
    attribution:
      '&copy; <a href="https://www.mapbox.com/">Mapbox</a> &copy; Maxar',
    tileSize: 512,
    zoomOffset: -1,
    maxNativeZoom: 21,
  },
  {
    id: "street",
    label: "Street",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    tileSize: 256,
    zoomOffset: 0,
    maxNativeZoom: 19,
  },
];

export const DEFAULT_BASEMAP = "satellite";

export default basemaps;
