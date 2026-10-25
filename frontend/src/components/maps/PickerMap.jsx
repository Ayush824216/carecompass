import { useEffect, useRef } from "react";
import L from "leaflet";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";
import { OSM_ATTRIBUTION, OSM_TILES, cssColor } from "../CaregiverMap.jsx";

const NCR = { lat: 28.6139, lng: 77.209 };

const PIN = L.divIcon({
  className: "",
  iconSize: [30, 30],
  iconAnchor: [15, 30],
  html: `<div style="width:30px;height:30px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:rgb(var(--accent));border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35)"></div>`,
});

function ClickToPin({ onPick }) {
  useMapEvents({ click: (e) => onPick({ lat: e.latlng.lat, lng: e.latlng.lng }) });
  return null;
}

function Recenter({ point }) {
  const map = useMap();
  useEffect(() => { if (point) map.setView([point.lat, point.lng], Math.max(map.getZoom(), 12)); }, [map, point?.lat, point?.lng]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function GooglePicker({ g, point, onPick }) {
  const el = useRef(null);
  const map = useRef(null);
  const marker = useRef(null);
  const pick = useRef(onPick);
  pick.current = onPick;

  useEffect(() => {
    map.current = new g.maps.Map(el.current, { center: point || NCR, zoom: point ? 13 : 10, gestureHandling: "cooperative",
      streetViewControl: false, mapTypeControl: false, fullscreenControl: false, clickableIcons: false });
    const l = map.current.addListener("click", (e) => pick.current({ lat: e.latLng.lat(), lng: e.latLng.lng() }));
    return () => { l.remove(); marker.current?.setMap(null); marker.current = null; };
  }, [g]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!point) return;
    if (!marker.current) {
      marker.current = new g.maps.Marker({ map: map.current, position: point,
        icon: { path: g.maps.SymbolPath.CIRCLE, scale: 10, fillColor: cssColor("--accent"), fillOpacity: 1, strokeColor: "#fff", strokeWeight: 3 } });
    } else marker.current.setPosition(point);
    map.current.panTo(point);
    if (map.current.getZoom() < 12) map.current.setZoom(13);
  }, [g, point?.lat, point?.lng]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={el} style={{ height: "100%", width: "100%" }} />;
}

/** Tap to drop a pin. Google Maps when loaded, else Leaflet + OpenStreetMap (attribution kept). */
export default function PickerMap({ status, google, point, onPick, height = 260 }) {
  return (
    <div className="overflow-hidden rounded-xl2 border border-line bg-surface" style={{ height }} data-map={status}>
      {status === "google" ? <GooglePicker g={google} point={point} onPick={onPick} />
        : status === "leaflet" ? (
          <MapContainer center={point ? [point.lat, point.lng] : [NCR.lat, NCR.lng]} zoom={point ? 12 : 10}
            scrollWheelZoom={false} style={{ height: "100%", width: "100%" }}>
            <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_TILES} />
            <ClickToPin onPick={onPick} />
            <Recenter point={point} />
            {point && <Marker position={[point.lat, point.lng]} icon={PIN} />}
          </MapContainer>
        ) : null}
    </div>
  );
}
