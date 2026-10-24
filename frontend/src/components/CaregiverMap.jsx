import { useEffect } from "react";
import L from "leaflet";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import { useApp } from "../context/AppContext.jsx";

function pin(label, tone) {
  if (tone === "user") {
    return L.divIcon({
      className: "", iconSize: [26, 26], iconAnchor: [13, 13], popupAnchor: [0, -12],
      html: `<div style="width:26px;height:26px;border-radius:50%;background:rgb(var(--accent));border:4px solid #fff;box-shadow:0 0 0 3px rgb(var(--accent) / .35),0 2px 6px rgba(0,0,0,.35)"></div>`,
    });
  }
  const bg = tone === "user" ? "rgb(var(--accent))" : tone === "selected" ? "rgb(var(--accent))" : tone === "top" ? "rgb(var(--primary))" : "rgb(var(--ink))";
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

/** items: [{ cg, label, top, sub }] ; user: {lat,lng}; onSelect(id) when a pin is clicked */
export default function CaregiverMap({ items, user, height = 420, onSelect, selectedId }) {
  const { t } = useApp();
  const pts = items.filter((i) => i.cg?.lat != null).map((i) => [i.cg.lat, i.cg.lng]);
  if (user) pts.push([user.lat, user.lng]);
  const center = pts[0] || [28.6139, 77.209];
  return (
    <div className="overflow-hidden rounded-xl2 border border-line" style={{ height }}>
      <MapContainer center={center} zoom={11} scrollWheelZoom={false} style={{ height: "100%", width: "100%" }}>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <FitBounds points={pts} />
        {user && (
          <Marker position={[user.lat, user.lng]} icon={pin("•", "user")} title={t("common.yourLocation")}>
            <Popup>{t("common.yourLocation")}</Popup>
          </Marker>
        )}
        {items.filter((i) => i.cg?.lat != null).map((i) => (
          <Marker key={i.cg.caregiver_id} position={[i.cg.lat, i.cg.lng]} title={i.cg.name}
            icon={pin(i.label, selectedId === i.cg.caregiver_id ? "selected" : i.top ? "top" : "other")}
            eventHandlers={{ click: () => onSelect?.(i.cg.caregiver_id) }}>
            <Popup>
              <strong>{i.label}. {i.cg.name}</strong><br />{t(`roles.${i.cg.role}`)}{i.sub ? <><br />{i.sub}</> : null}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
