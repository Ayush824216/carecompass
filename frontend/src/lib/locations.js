import FALLBACK from "./localities.json";
import { api } from "./api.js";
import { haversineKm } from "./format.js";

let cache = null;

/** Delhi NCR localities from the API (config/localities.json), with a bundled copy as fallback. */
export async function getLocalities() {
  if (cache) return cache;
  try {
    cache = await api.localities();
  } catch {
    cache = FALLBACK;
  }
  return cache;
}

export function nearestLocality(lat, lng, list = cache || FALLBACK) {
  if (lat == null) return null;
  let best = null;
  for (const l of list) {
    const km = haversineKm({ lat, lng }, l);
    if (!best || km < best.km) best = { ...l, km };
  }
  return best;
}

/** Human label for the current location, e.g. "Saket, South Delhi" or "near Saket". */
export function locationLabel(loc, t) {
  if (!loc || loc.lat == null) return "";
  if (loc.source === "locality" && loc.label) return loc.label;
  const n = nearestLocality(loc.lat, loc.lng);
  if (!n) return `${loc.lat.toFixed(3)}, ${loc.lng.toFixed(3)}`;
  return n.km < 2 ? `${n.name}, ${n.city}` : t("location.near", { name: `${n.name}, ${n.city}` });
}
