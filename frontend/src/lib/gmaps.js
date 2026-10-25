// Google Maps Platform (Maps JS, Places, Geocoding), loaded once. Without VITE_GOOGLE_MAPS_API_KEY, or when Google fails
// to load, every map falls back to Leaflet + OpenStreetMap. Locations go browser -> Google only; our server never sees them.
import { useEffect, useState } from "react";
import { Loader } from "@googlemaps/js-api-loader";

const KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "";
let promise = null;
// Google calls window.gm_authFailure when the key is rejected (billing off, API not enabled, referrer not allowed).
// The script still "loads", so without this the user would see Google's grey "can't load correctly" box.
let authFailed = false;
const listeners = new Set();
if (typeof window !== "undefined") {
  window.gm_authFailure = () => {
    authFailed = true;
    console.warn("Google Maps rejected the API key; using OpenStreetMap. See the Google Maps error above for the reason.");
    listeners.forEach((fn) => fn());
  };
}

export function hasGoogleKey() { return Boolean(KEY); }

// Billing off / API not enabled does not call gm_authFailure, so check the key once with a fixed point
// (central Delhi, never the user's location); REQUEST_DENIED means Google would show its error box.
async function probe(g) {
  if (!g?.maps || authFailed) return null;
  try {
    await new g.maps.Geocoder().geocode({ location: { lat: 28.6139, lng: 77.209 } });
    return g;
  } catch (e) {
    const denied = e?.code === "REQUEST_DENIED" || /denied|billing|not authorized|not activated/i.test(e?.message || "");
    if (denied) console.warn("Google Maps key not usable (check billing and enabled APIs); using OpenStreetMap.");
    return denied ? null : g;
  }
}

/** Resolves to the `google` namespace, or null (no key / blocked / failed). Never rejects. */
export function loadGoogle() {
  if (!KEY || authFailed) return Promise.resolve(null);
  if (!promise) {
    const loader = new Loader({ apiKey: KEY, version: "weekly", libraries: ["places", "geocoding"], region: "IN" });
    promise = Promise.race([
      loader.load().then(probe),
      new Promise((r) => setTimeout(() => r(null), 10000)),
    ]).catch(() => null);
  }
  return promise;
}

/** "loading" | "google" | "leaflet", plus the namespace when ready. */
export function useGoogleMaps() {
  const [state, setState] = useState(() => ({ status: KEY && !authFailed ? "loading" : "leaflet", google: null }));
  useEffect(() => {
    let live = true;
    const fallback = () => live && setState({ status: "leaflet", google: null });
    listeners.add(fallback);
    if (KEY) loadGoogle().then((g) => live && setState(g && !authFailed ? { status: "google", google: g } : { status: "leaflet", google: null }));
    return () => { live = false; listeners.delete(fallback); };
  }, []);
  return state;
}

/** Area name for a point ("Saket, New Delhi"), or "" when unknown. */
export async function reverseGeocode(g, lat, lng) {
  try {
    const { results } = await new g.maps.Geocoder().geocode({ location: { lat, lng } });
    const pick = (types) => results.flatMap((r) => r.address_components).find((c) => c.types.some((x) => types.includes(x)))?.long_name;
    const area = pick(["sublocality_level_1", "sublocality", "neighborhood"]);
    const city = pick(["locality", "administrative_area_level_2"]);
    return [area, city].filter(Boolean).filter((v, i, a) => a.indexOf(v) === i).join(", ") || results[0]?.formatted_address || "";
  } catch {
    return "";
  }
}
