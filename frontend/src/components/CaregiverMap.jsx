import { useEffect, useRef } from "react";
import L from "leaflet";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import { useApp } from "../context/AppContext.jsx";
import { useGoogleMaps } from "../lib/gmaps.js";

const NCR_CENTER = [28.6139, 77.209];
// OpenStreetMap tiles require this attribution (ODbL); kept on every Leaflet fallback map
export const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
export const OSM_TILES = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

/** "13 110 104" CSS token -> "rgb(13,110,104)" for Google marker icons. */
export function cssColor(name) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v ? `rgb(${v.split(/\s+/).join(",")})` : "#0d6e68";
}

function pin(label, tone) {
  if (tone === "user") {
    return L.divIcon({
      className: "", iconSize: [26, 26], iconAnchor: [13, 13], popupAnchor: [0, -12],
      html: `<div style="width:26px;height:26px;border-radius:50%;background:rgb(var(--accent));border:4px solid #fff;box-shadow:0 0 0 3px rgb(var(--accent) / .35),0 2px 6px rgba(0,0,0,.35)"></div>`,
    });
  }
  const bg = tone === "selected" ? "rgb(var(--accent))" : tone === "top" ? "rgb(var(--primary))" : "rgb(var(--ink))";
  return L.divIcon({
    className: "",
    iconSize: [34, 34],
    iconAnchor: [17, 34],
    popupAnchor: [0, -30],
    html: `<div style="width:34px;height:34px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:${bg};border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center"><span style="transform:rotate(45deg);color:#fff;font:700 14px/1 'Source Sans 3',sans-serif">${label}</span></div>`,
  });
}

function FitBounds({ points }) {
  const map = useMap();
  const key = JSON.stringify(points);
  useEffect(() => {
    const pts = JSON.parse(key);
    if (!pts.length) return;
    if (pts.length === 1) { map.setView(pts[0], 13); return; }
    map.fitBounds(L.latLngBounds(pts), { padding: [40, 40], maxZoom: 14 });
  }, [map, key]);
  return null;
}

function LeafletCaregiverMap({ items, user, onSelect, selectedId, t }) {
  const pts = items.map((i) => [i.cg.lat, i.cg.lng]);
  if (user) pts.push([user.lat, user.lng]);
  return (
    <MapContainer center={pts[0] || NCR_CENTER} zoom={11} scrollWheelZoom={false} style={{ height: "100%", width: "100%" }}>
      <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_TILES} />
      <FitBounds points={pts} />
      {user && (
        <Marker position={[user.lat, user.lng]} icon={pin("•", "user")} title={t("common.yourLocation")}>
          <Popup>{t("common.yourLocation")}</Popup>
        </Marker>
      )}
      {items.map((i) => (
        <Marker key={i.cg.caregiver_id} position={[i.cg.lat, i.cg.lng]} title={i.cg.name}
          icon={pin(i.label, selectedId === i.cg.caregiver_id ? "selected" : i.top ? "top" : "other")}
          eventHandlers={{ click: () => onSelect?.(i.cg.caregiver_id) }}>
          <Popup>
            <strong>{i.label}. {i.cg.name}</strong><br />{t(`roles.${i.cg.role}`)}{i.sub ? <><br />{i.sub}</> : null}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}

function GoogleCaregiverMap({ g, items, user, onSelect, selectedId, t }) {
  const el = useRef(null);
  const map = useRef(null);
  const info = useRef(null);
  const markers = useRef([]);
  const select = useRef(onSelect);
  select.current = onSelect;

  useEffect(() => {
    map.current = new g.maps.Map(el.current, { center: { lat: NCR_CENTER[0], lng: NCR_CENTER[1] }, zoom: 11,
      gestureHandling: "cooperative", streetViewControl: false, mapTypeControl: false, fullscreenControl: false, clickableIcons: false });
    info.current = new g.maps.InfoWindow();
    return () => { markers.current.forEach((m) => m.setMap(null)); markers.current = []; };
  }, [g]);

  const key = JSON.stringify([items.map((i) => [i.cg.caregiver_id, i.label, i.top]), user && [user.lat, user.lng], selectedId]);
  useEffect(() => {
    const m = map.current;
    markers.current.forEach((x) => x.setMap(null));
    markers.current = [];
    const bounds = new g.maps.LatLngBounds();
    const dot = (fill, scale) => ({ path: g.maps.SymbolPath.CIRCLE, scale, fillColor: fill, fillOpacity: 1, strokeColor: "#fff", strokeWeight: 3 });
    if (user) {
      const mk = new g.maps.Marker({ map: m, position: { lat: user.lat, lng: user.lng }, title: t("common.yourLocation"), icon: dot(cssColor("--accent"), 9), zIndex: 1000 });
      mk.addListener("click", () => { info.current.setContent(t("common.yourLocation")); info.current.open({ map: m, anchor: mk }); });
      markers.current.push(mk);
      bounds.extend(mk.getPosition());
    }
    for (const i of items) {
      const tone = selectedId === i.cg.caregiver_id ? "--accent" : i.top ? "--primary" : "--ink";
      const mk = new g.maps.Marker({ map: m, position: { lat: i.cg.lat, lng: i.cg.lng }, title: i.cg.name,
        label: { text: String(i.label), color: "#fff", fontWeight: "700" }, icon: dot(cssColor(tone), 15) });
      mk.addListener("click", () => {
        const box = document.createElement("div");
        const b = document.createElement("strong");
        b.textContent = `${i.label}. ${i.cg.name}`;
        box.append(b, document.createElement("br"), t(`roles.${i.cg.role}`));
        if (i.sub) box.append(document.createElement("br"), i.sub);
        info.current.setContent(box);
        info.current.open({ map: m, anchor: mk });
        select.current?.(i.cg.caregiver_id);
      });
      markers.current.push(mk);
      bounds.extend(mk.getPosition());
    }
    if (markers.current.length === 1) { m.setCenter(bounds.getCenter()); m.setZoom(14); }
    else if (markers.current.length > 1) m.fitBounds(bounds, 40);
  }, [g, key]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={el} style={{ height: "100%", width: "100%" }} />;
}

/** items: [{ cg, label, top, sub }] ; user: {lat,lng}; onSelect(id) when a pin is clicked. Google Maps, else Leaflet/OSM. */
export default function CaregiverMap({ items, user, height = 420, onSelect, selectedId }) {
  const { t } = useApp();
  const { status, google } = useGoogleMaps();
  const shown = items.filter((i) => i.cg?.lat != null);
  const props = { items: shown, user, onSelect, selectedId, t };
  return (
    <div className="overflow-hidden rounded-xl2 border border-line bg-surface" style={{ height }} data-map={status}>
      {status === "google" ? <GoogleCaregiverMap g={google} {...props} />
        : status === "leaflet" ? <LeafletCaregiverMap {...props} /> : null}
    </div>
  );
}
