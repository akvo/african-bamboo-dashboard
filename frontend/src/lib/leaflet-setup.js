// Single place that pulls Leaflet and its side effects in, so
// the order is explicit and the CSS cannot be imported twice
// from different components.
//
// The default-marker-icon patch that used to live here was
// removed: nothing renders a Marker, so it only added three
// unpkg.com requests to the map's critical path.
import L from "leaflet";

import "leaflet/dist/leaflet.css";
import "leaflet-editable";

export default L;
