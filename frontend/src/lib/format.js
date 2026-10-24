export function haversineKm(a, b) {
  if (!a || !b || a.lat == null || b.lat == null) return null;
  const R = 6371;
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function futureSlots(cg, now = new Date()) {
  return (cg?.availability_slots || []).map((s) => new Date(s)).filter((d) => !Number.isNaN(+d) && d > now).sort((a, b) => a - b);
}

/** Earliest slot; for same-day urgency prefer a slot today. */
export function nextSlot(cg, urgency) {
  const slots = futureSlots(cg);
  if (urgency === "same_day") {
    const today = slots.find((d) => d.toDateString() === new Date().toDateString());
    if (today) return today;
  }
  return slots[0] || null;
}

export function isFreeToday(cg) {
  const today = new Date().toDateString();
  return futureSlots(cg).some((d) => d.toDateString() === today);
}

export function dayLabel(d, t, lang) {
  const today = new Date();
  const tomorrow = new Date(); tomorrow.setDate(today.getDate() + 1);
  if (d.toDateString() === today.toDateString()) return t("common.today");
  if (d.toDateString() === tomorrow.toDateString()) return t("common.tomorrow");
  return d.toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", { weekday: "short", day: "numeric", month: "short" });
}

export function timeLabel(d, lang) {
  return d.toLocaleTimeString(lang === "hi" ? "hi-IN" : "en-IN", { hour: "numeric", minute: "2-digit" });
}

export function slotLabel(d, t, lang) {
  if (!d) return "—";
  return `${dayLabel(d, t, lang)}, ${timeLabel(d, lang)}`;
}

export function kmLabel(km, t) {
  if (km == null) return "";
  return `${km < 1 ? "<1" : km.toFixed(km < 10 ? 1 : 0)} ${t("common.km")}`;
}
