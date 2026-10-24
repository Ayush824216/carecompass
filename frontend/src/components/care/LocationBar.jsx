import { useEffect, useMemo, useState } from "react";
import L from "leaflet";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";
import { AlertTriangle, Check, Crosshair, MapPin, Pencil } from "lucide-react";
import { useApp } from "../../context/AppContext.jsx";
import { getLocalities, locationLabel } from "../../lib/locations.js";
import { Spinner } from "../ui.jsx";

const PIN = L.divIcon({
  className: "",
  iconSize: [30, 30],
  iconAnchor: [15, 30],
  html: `<div style="width:30px;height:30px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:rgb(var(--accent));border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35)"></div>`,
});

function ClickToPin({ onPick }) {
  useMapEvents({ click: (e) => onPick(e.latlng) });
  return null;
}

export default function LocationBar() {
  const { t, location, setLocation, requestGps, geoStatus, hasLocation } = useApp();
  const [open, setOpen] = useState(!hasLocation);
  const [list, setList] = useState([]);
  useEffect(() => { getLocalities().then(setList); }, []);
  useEffect(() => { if (!hasLocation && geoStatus !== "asking") setOpen(true); }, [hasLocation, geoStatus]);

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
        {hasLocation && (
          <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="btn-ghost min-h-[44px] px-4 text-sm">
            <Pencil className="h-4 w-4" aria-hidden="true" />{open ? t("location.done") : t("location.change")}
          </button>
        )}
      </div>

      {open && (
        <div className="grid gap-5 border-t border-line px-4 pb-4 pt-4 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-4">
            <p className="text-sm text-muted">{t("location.chooseHint")}</p>
            {(geoStatus === "denied" || geoStatus === "unavailable") && (
              <p className="flex items-start gap-2 rounded-xl bg-accent-soft px-3 py-2 text-sm font-semibold" role="status">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                {geoStatus === "denied" ? t("location.denied") : t("location.unavailable")}
              </p>
            )}
            <button type="button" onClick={() => requestGps()} className="btn-primary w-full" disabled={geoStatus === "asking"}>
              {geoStatus === "asking" ? <Spinner /> : <Crosshair className="h-5 w-5" aria-hidden="true" />}{t("location.useCurrent")}
            </button>
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
            {hasLocation && (
              <button type="button" onClick={() => setOpen(false)} className="btn-ghost w-full">
                <Check className="h-5 w-5" aria-hidden="true" />{t("location.done")}
              </button>
            )}
          </div>
          <div>
            <p className="mb-1.5 font-semibold">{t("location.pickMap")}</p>
            <div className="h-[260px] overflow-hidden rounded-xl2 border border-line">
              <MapContainer center={hasLocation ? [location.lat, location.lng] : [28.6139, 77.209]} zoom={hasLocation ? 12 : 10}
                scrollWheelZoom={false} style={{ height: "100%", width: "100%" }}>
                <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                <ClickToPin onPick={(ll) => setLocation({ lat: ll.lat, lng: ll.lng, source: "map", label: "" })} />
                {hasLocation && <Marker position={[location.lat, location.lng]} icon={PIN} />}
              </MapContainer>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
