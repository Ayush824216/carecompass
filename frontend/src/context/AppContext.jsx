import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { translate } from "../i18n/index.js";
import { load, save, setNoStore } from "../lib/storage.js";
import { setIncognitoHeader } from "../lib/api.js";
import { SOS_KEY, loadContacts } from "../lib/sos.js";
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
  // SOS family contacts: device only (save() writes nothing in Incognito; the list then lives for this tab only)
  const [sosContacts, setSosContactsState] = useState(loadContacts);
  const setSosContacts = useCallback((list) => { setSosContactsState(list); save(SOS_KEY, list); }, []);
  // privacy mode lives in memory only: a fresh tab always starts in "memory" (device memory ON)
  const [mode, setModeState] = useState("memory"); // memory | incognito
  const [consent, setConsentState] = useState(() => load("cc.consent", null));
  const [session, setSession] = useState(0); // bumped by "End session" / "Clear conversation" to wipe chat state
  const setMode = useCallback((m) => {
    const inc = m === "incognito";
    setNoStore(inc); setIncognitoHeader(inc); setModeState(m);
  }, []);
  const endSession = useCallback(() => { setMode("memory"); setSession((n) => n + 1); }, [setMode]);
  const giveConsent = useCallback((choice) => {
    const c = { choice, at: new Date().toISOString() };
    setConsentState(c);
    if (choice === "incognito") setMode("incognito"); else save("cc.consent", c);
  }, [setMode]);

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
    if (!window.isSecureContext) { setGeoStatus("insecure"); resolve(false); return; } // browsers allow GPS only on https or localhost
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

  // no automatic GPS request: Get Care shows "Allow location" and the browser asks only after that tap

  const t = useCallback((key, vars) => translate(lang, key, vars), [lang]);

  const toast = useCallback((message, tone = "success") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((ts) => [...ts, { id, message, tone }]);
    setTimeout(() => setToasts((ts) => ts.filter((x) => x.id !== id)), 4500);
  }, []);
  // one navbar switch: turning Incognito off ends the session (the conversation held in memory is wiped)
  const toggleIncognito = useCallback(() => {
    if (mode === "incognito") { endSession(); toast(translate(lang, "privacy.incognitoOffToast"), "info"); }
    else { setMode("incognito"); toast(translate(lang, "privacy.incognitoOnToast"), "info"); }
  }, [mode, endSession, setMode, toast, lang]);
  const dismissToast = useCallback((id) => setToasts((ts) => ts.filter((x) => x.id !== id)), []);

  const addBooking = useCallback((b) => setBookings((bs) => [b, ...bs]), []);
  const updateBooking = useCallback((id, patch) => setBookings((bs) => bs.map((b) => (b.booking_id === id ? { ...b, ...patch } : b))), []);
  const removeBooking = useCallback((id) => setBookings((bs) => bs.filter((b) => b.booking_id !== id)), []);

  const value = useMemo(() => ({
    lang, setLang, t, voice, setVoice, contrast, setContrast,
    sizeIdx, basePx: SIZES[sizeIdx], canGrow: sizeIdx < SIZES.length - 1, canShrink: sizeIdx > 0,
    grow: () => setSizeIdx((i) => Math.min(SIZES.length - 1, i + 1)), shrink: () => setSizeIdx((i) => Math.max(0, i - 1)),
    location, setLocation, requestGps, geoStatus, hasLocation: location.lat != null, bookings, addBooking, updateBooking, removeBooking, toasts, toast, dismissToast,
    mode, setMode, incognito: mode === "incognito", endSession, toggleIncognito, session, consent, giveConsent, sosContacts, setSosContacts,
  }), [lang, t, voice, contrast, sizeIdx, location, setLocation, requestGps, geoStatus, bookings, addBooking, updateBooking, removeBooking, toasts, toast, dismissToast,
    mode, setMode, endSession, toggleIncognito, session, consent, giveConsent, sosContacts, setSosContacts]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  return useContext(Ctx);
}
