// Google Maps Platform (Maps JS, Places, Geocoding), loaded once. Without VITE_GOOGLE_MAPS_API_KEY, or when Google fails
// to load, every map falls back to Leaflet + OpenStreetMap. Locations go browser -> Google only; our server never sees them.
import { useEffect, useState } from "react";
import { Loader } from "@googlemaps/js-api-loader";

const KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "";
let promise = null;

export function hasGoogleKey() { return Boolean(KEY); }

/** Resolves to the `google` namespace, or null (no key / blocked / failed). Never rejects. */
export function loadGoogle() {
  if (!KEY) return Promise.resolve(null);
  if (!promise) {
    const loader = new Loader({ apiKey: KEY, version: "weekly", libraries: ["places", "geocoding"], region: "IN" });
    promise = Promise.race([
      loader.load().then((g) => (g?.maps ? g : null)),
      new Promise((r) => setTimeout(() => r(null), 10000)),
    ]).catch(() => null);
  }
  return promise;
}

/** "loading" | "google" | "leaflet", plus the namespace when ready. */
export function useGoogleMaps() {
  const [state, setState] = useState(() => ({ status: KEY ? "loading" : "leaflet", google: null }));
  useEffect(() => {
    let live = true;
    if (KEY) loadGoogle().then((g) => live && setState(g ? { status: "google", google: g } : { status: "leaflet", google: null }));
    return () => { live = false; };
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
