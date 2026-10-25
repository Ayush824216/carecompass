import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, Crosshair, MapPin, Pencil } from "lucide-react";
import { useApp } from "../../context/AppContext.jsx";
import { getLocalities, locationLabel } from "../../lib/locations.js";
import { reverseGeocode, useGoogleMaps } from "../../lib/gmaps.js";
import PickerMap from "../maps/PickerMap.jsx";
import PlaceSearch from "../maps/PlaceSearch.jsx";
import { Spinner } from "../ui.jsx";

const GEO_MSG = { denied: "location.denied", unavailable: "location.unavailable", insecure: "location.insecure" };

export default function LocationBar() {
  const { t, location, setLocation, requestGps, geoStatus, hasLocation } = useApp();
  const { status, google } = useGoogleMaps();
  const [open, setOpen] = useState(!hasLocation);
  const [list, setList] = useState([]);
  useEffect(() => { getLocalities().then(setList); }, []);
  useEffect(() => { if (!hasLocation && geoStatus !== "asking") setOpen(true); }, [hasLocation, geoStatus]);

  // GPS fix or dropped pin: ask Google for the area name (browser -> Google only; never sent to our server)
  useEffect(() => {
    if (!google || location.lat == null || location.label || !["gps", "map"].includes(location.source)) return;
    let live = true;
    const { lat, lng } = location;
    reverseGeocode(google, lat, lng).then((label) => { if (live && label) setLocation({ ...location, label }); });
    return () => { live = false; };
  }, [google, location, setLocation]);

  const label = locationLabel(location, t);
  const byCity = useMemo(() => {
    const g = {};
    for (const l of list) (g[l.city] ||= []).push(l);
    return Object.entries(g);
  }, [list]);
  const selectedId = location.source === "locality" ? location.id || "" : "";

  const pickLocality = (id) => {
    const l = list.find((x) => x.id === id);
    if (l) setLocation({ lat: l.lat, lng: l.lng, source: "locality", id: l.id, label: `${l.name}, ${l.city}` });
  };

  const sourceText = location.source === "gps" ? t("location.gps") : location.source === "map" ? t("location.pinned") : "";
  const point = hasLocation ? { lat: location.lat, lng: location.lng } : null;

  return (
    <section className={`mb-6 rounded-xl2 border ${hasLocation ? "border-line bg-surface" : "border-accent bg-accent-soft/50"}`} aria-label={t("location.your")}>
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <MapPin className={`h-5 w-5 shrink-0 ${hasLocation ? "text-primary" : "text-accent"}`} aria-hidden="true" />
        <p className="min-w-0 flex-1">
          <span className="text-muted">{t("location.your")}: </span>
          {geoStatus === "asking" && !hasLocation ? (
            <span className="inline-flex items-center gap-2 font-semibold"><Spinner />{t("location.detecting")}</span>
          ) : hasLocation ? (
            <span className="font-bold">{label}{sourceText && <span className="ml-2 text-sm font-semibold text-muted">({sourceText})</span>}</span>
          ) : (
            <span className="font-bold text-accent">{t("location.choose")}</span>
          )}
        </p>
        {hasLocation && !open && (
          <button type="button" onClick={() => setOpen(true)} aria-expanded={false} className="btn-ghost min-h-[44px] px-4 text-sm">
            <Pencil className="h-4 w-4" aria-hidden="true" />{t("location.change")}
          </button>
        )}
      </div>

      {!hasLocation && geoStatus === "idle" && (
        <div className="flex flex-wrap items-center gap-3 border-t border-line px-4 py-3" role="note">
          <p className="min-w-0 flex-1 text-sm font-semibold">{t("location.allowPrompt")}</p>
          <button type="button" onClick={() => requestGps()} className="btn-primary min-h-[44px] px-4 text-sm">
            <Crosshair className="h-4 w-4" aria-hidden="true" />{t("location.allow")}
          </button>
        </div>
      )}

      {open && (
        <div className="grid gap-5 border-t border-line px-4 pb-4 pt-4 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-4">
            <p className="text-sm text-muted">{t("location.chooseHint")}</p>
            {GEO_MSG[geoStatus] && (
              <p className="flex items-start gap-2 rounded-xl bg-accent-soft px-3 py-2 text-sm font-semibold" role="status">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />{t(GEO_MSG[geoStatus])}
              </p>
            )}
            <button type="button" onClick={() => requestGps()} className="btn-primary w-full" disabled={geoStatus === "asking"}>
              {geoStatus === "asking" ? <Spinner /> : <Crosshair className="h-5 w-5" aria-hidden="true" />}{t("location.useCurrent")}
            </button>
            {status === "google" ? (
              <div>
                <label htmlFor="loc-search" className="mb-1.5 block font-semibold">{t("location.search")}</label>
                <PlaceSearch g={google} id="loc-search" placeholder={t("location.searchPlaceholder")}
                  onPlace={(p) => setLocation({ ...p, source: "search" })} />
              </div>
            ) : status === "leaflet" ? (
              <div>
                <label htmlFor="loc-select" className="mb-1.5 block font-semibold">{t("location.pickList")}</label>
                <select id="loc-select" className="input" value={selectedId} onChange={(e) => pickLocality(e.target.value)}>
                  <option value="" disabled>{t("location.selectPlaceholder")}</option>
                  {byCity.map(([city, items]) => (
                    <optgroup key={city} label={city}>
                      {items.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                    </optgroup>
                  ))}
                </select>
              </div>
            ) : null}
            {hasLocation && (
              <button type="button" onClick={() => setOpen(false)} className="btn-ghost w-full">
                <Check className="h-5 w-5" aria-hidden="true" />{t("location.done")}
              </button>
            )}
          </div>
          <div>
            <p className="mb-1.5 font-semibold">{t("location.pickMap")}</p>
            <PickerMap status={status} google={google} point={point}
              onPick={(ll) => setLocation({ lat: ll.lat, lng: ll.lng, source: "map", label: "" })} />
          </div>
        </div>
      )}
    </section>
  );
}
