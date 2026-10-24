// SOS to family: up to 5 contacts saved ONLY on this device (cc.sosContacts; nothing is written in Incognito).
// The message is prefilled and sent by the user from their own SMS / WhatsApp app. Optional server sending
// (SMS_PROVIDER=twilio) is reported as "Sent" only when the provider confirms it.
import { load } from "./storage.js";

export const SOS_KEY = "cc.sosContacts";
export const MAX_CONTACTS = 5;

export function loadContacts() {
  const list = load(SOS_KEY, null);
  if (Array.isArray(list)) return list.slice(0, MAX_CONTACTS);
  const old = load("cc.emergencyContact", null); // the single contact of earlier versions
  return old?.phone ? [{ name: old.name || "", phone: old.phone, relation: "" }] : [];
}

export const cleanPhone = (p) => String(p || "").replace(/[^\d+]/g, "");
export const validPhone = (p) => /^(\+?91)?[6-9]\d{9}$/.test(cleanPhone(p));
const e164 = (p) => { const d = cleanPhone(p).replace(/^\+?91/, ""); return `91${d.slice(-10)}`; };

export function sosMessage({ t, signs = [], location, place }) {
  const lines = [t("emergency.share.line1")];
  if (signs.length) lines.push(`${t("emergency.share.signs")}: ${signs.join(", ")}`);
  if (location?.lat != null) {
    lines.push(`${t("emergency.share.location")}: ${place ? `${place} ` : ""}https://maps.google.com/?q=${location.lat.toFixed(5)},${location.lng.toFixed(5)}`);
  }
  lines.push(`${t("emergency.share.time")}: ${new Date().toLocaleString()}`);
  lines.push(t("emergency.share.call112"));
  return lines.join("\n");
}

const isIOS = () => /iPad|iPhone|iPod/.test(navigator.userAgent || "");

/** One sms: link to every contact (Android "?body=", iOS "&body="). */
export function smsAllHref(contacts, body) {
  const nums = contacts.map((c) => cleanPhone(c.phone)).filter(Boolean).join(",");
  return `sms:${nums}${isIOS() ? "&" : "?"}body=${encodeURIComponent(body)}`;
}

export const smsHref = (phone, body) => `sms:${cleanPhone(phone)}${isIOS() ? "&" : "?"}body=${encodeURIComponent(body)}`;
export const waHref = (phone, body) => `https://wa.me/${e164(phone)}?text=${encodeURIComponent(body)}`;
export const telHref = (phone) => `tel:${cleanPhone(phone)}`;
