import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { translate } from "../i18n/index.js";
import { load, save } from "../lib/storage.js";
import { stopSpeaking } from "../lib/speech.js";

const SIZES = [16, 18, 20, 22, 24];
// No silent default: location stays "unset" until GPS, a locality pick or a map click provides it.
export const UNSET_LOC = { lat: null, lng: null, source: "unset", label: "" };

const Ctx = createContext(null);

export function AppProvider({ children }) {
  const [lang, setLang] = useState(() => load("cc.lang", "en"));
  const [sizeIdx, setSizeIdx] = useState(() => load("cc.size", 1));
  const [contrast, setContrast] = useState(() => load("cc.contrast", false));
  const [voice, setVoice] = useState(() => load("cc.voice", true));
  const [bookings, setBookings] = useState(() => load("cc.bookings", []));
  const [location, setLocationState] = useState(() => load("cc.location", UNSET_LOC));
  const [geoStatus, setGeoStatus] = useState("idle"); // idle | asking | denied | unavailable | ok
  const [toasts, setToasts] = useState([]);

  useEffect(() => { save("cc.lang", lang); document.documentElement.lang = lang; }, [lang]);
  useEffect(() => {
    save("cc.size", sizeIdx);
    document.documentElement.style.setProperty("--base-size", `${SIZES[sizeIdx]}px`);
  }, [sizeIdx]);
  useEffect(() => {
    save("cc.contrast", contrast);
    document.documentElement.dataset.contrast = contrast ? "high" : "normal";
  }, [contrast]);
  useEffect(() => { save("cc.voice", voice); if (!voice) stopSpeaking(); }, [voice]);
  useEffect(() => { save("cc.bookings", bookings); }, [bookings]);

  const setLocation = useCallback((loc) => { setLocationState(loc); save("cc.location", loc); }, []);

  /** Ask the browser for the current position; resolves to true on success. */
  const requestGps = useCallback(() => new Promise((resolve) => {
    if (!navigator.geolocation) { setGeoStatus("unavailable"); resolve(false); return; }
    setGeoStatus("asking");
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setGeoStatus("ok");
        setLocation({ lat: p.coords.latitude, lng: p.coords.longitude, source: "gps", label: "" });
        resolve(true);
      },
      (err) => { setGeoStatus(err && err.code === 1 ? "denied" : "unavailable"); resolve(false); },
      { timeout: 8000, maximumAge: 600000 }
    );
  }), [setLocation]);

  // first visit: try GPS once; if it fails the location picker is shown (no silent default)
  useEffect(() => { if (load("cc.location", UNSET_LOC).source === "unset") requestGps(); }, [requestGps]);

  const t = useCallback((key, vars) => translate(lang, key, vars), [lang]);

  const toast = useCallback((message, tone = "success") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((ts) => [...ts, { id, message, tone }]);
    setTimeout(() => setToasts((ts) => ts.filter((x) => x.id !== id)), 4500);
  }, []);
  const dismissToast = useCallback((id) => setToasts((ts) => ts.filter((x) => x.id !== id)), []);

  const addBooking = useCallback((b) => setBookings((bs) => [b, ...bs]), []);
  const updateBooking = useCallback((id, patch) => setBookings((bs) => bs.map((b) => (b.booking_id === id ? { ...b, ...patch } : b))), []);
  const removeBooking = useCallback((id) => setBookings((bs) => bs.filter((b) => b.booking_id !== id)), []);

  const value = useMemo(() => ({
    lang, setLang, t, voice, setVoice, contrast, setContrast,
    sizeIdx, basePx: SIZES[sizeIdx], canGrow: sizeIdx < SIZES.length - 1, canShrink: sizeIdx > 0,
    grow: () => setSizeIdx((i) => Math.min(SIZES.length - 1, i + 1)), shrink: () => setSizeIdx((i) => Math.max(0, i - 1)),
    location, setLocation, requestGps, geoStatus, hasLocation: location.lat != null, bookings, addBooking, updateBooking, removeBooking, toasts, toast, dismissToast,
  }), [lang, t, voice, contrast, sizeIdx, location, setLocation, requestGps, geoStatus, bookings, addBooking, updateBooking, removeBooking, toasts, toast, dismissToast]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  return useContext(Ctx);
}
