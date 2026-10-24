import { useState } from "react";
import { MessageCircle, MessageSquareText, Phone, Share2, UserPlus, X } from "lucide-react";
import { useApp } from "../../context/AppContext.jsx";
import { load, save } from "../../lib/storage.js";

const KEY = "cc.emergencyContact";

function digits(p) {
  const d = String(p || "").replace(/\D/g, "");
  return d.length === 10 ? `91${d}` : d;
}

/** Pre-filled message the user sends themselves. Nothing is sent by SwasthMitra. */
export function shareText({ t, signs, location, when }) {
  const lines = [t("emergency.share.line1")];
  if (signs.length) lines.push(`${t("emergency.share.signs")}: ${signs.join(", ")}`);
  if (location?.lat != null) {
    const ll = `${location.lat.toFixed(5)},${location.lng.toFixed(5)}`;
    lines.push(`${t("emergency.share.location")}: ${ll} https://www.google.com/maps?q=${ll}`);
  }
  lines.push(`${t("emergency.share.time")}: ${when.toLocaleString()}`);
  lines.push(t("emergency.share.call112"));
  return lines.join("\n");
}

/** Tap-to-call / tap-to-share actions. Only links and the browser share sheet: the app never claims a message
 *  was sent or that anyone was notified. The saved contact stays in this browser only. */
export default function EmergencyContacts({ signs }) {
  const { t, location } = useApp();
  const [contact, setContact] = useState(() => load(KEY, null));
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(contact?.name || "");
  const [phone, setPhone] = useState(contact?.phone || "");
  const [err, setErr] = useState("");
  const text = shareText({ t, signs, location, when: new Date() });
  const enc = encodeURIComponent(text);
  const canShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  const saveContact = (e) => {
    e.preventDefault();
    if (!/^\d{10}$/.test(phone.replace(/\D/g, "").slice(-10)) || !name.trim()) { setErr(t("emergency.contact.invalid")); return; }
    const c = { name: name.trim(), phone: phone.replace(/\D/g, "").slice(-10) };
    save(KEY, c);
    setContact(c); setEditing(false); setErr("");
  };
  const clear = () => {
    try { window.localStorage.removeItem(KEY); } catch { /* storage blocked */ }
    setContact(null); setName(""); setPhone("");
  };
  const btn = "inline-flex min-h-[56px] items-center gap-2 rounded-2xl px-5 text-lg font-bold";

  return (
    <section className="rounded-3xl bg-white p-5 text-ink" aria-labelledby="em-family">
      <h2 id="em-family" className="text-xl font-semibold">{t("emergency.share.title")}</h2>
      <p className="mt-1 text-sm text-muted">{t("emergency.share.hint")}</p>

      {contact && !editing && (
        <div className="mt-4 rounded-2xl border-2 border-emergency/30 p-4">
          <p className="font-bold">{contact.name} · <span className="font-mono">{contact.phone}</span></p>
          <div className="mt-3 flex flex-wrap gap-2">
            <a href={`tel:+${digits(contact.phone)}`} className={`${btn} bg-emergency text-white`}><Phone className="h-5 w-5" aria-hidden="true" />{t("emergency.contact.call", { name: contact.name })}</a>
            <a href={`https://wa.me/${digits(contact.phone)}?text=${enc}`} target="_blank" rel="noreferrer" className={`${btn} border-2 border-line`}><MessageCircle className="h-5 w-5" aria-hidden="true" />{t("emergency.share.whatsapp")}</a>
            <a href={`sms:+${digits(contact.phone)}?body=${enc}`} className={`${btn} border-2 border-line`}><MessageSquareText className="h-5 w-5" aria-hidden="true" />{t("emergency.share.sms")}</a>
          </div>
          <div className="mt-2 flex gap-3 text-sm">
            <button type="button" className="font-semibold underline" onClick={() => setEditing(true)}>{t("emergency.contact.edit")}</button>
            <button type="button" className="font-semibold underline" onClick={clear}>{t("emergency.contact.remove")}</button>
          </div>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {canShare && (
          <button type="button" className={`${btn} border-2 border-line`} onClick={() => navigator.share({ text }).catch(() => {})}>
            <Share2 className="h-5 w-5" aria-hidden="true" />{t("emergency.share.tapToShare")}
          </button>
        )}
        <a href={`https://wa.me/?text=${enc}`} target="_blank" rel="noreferrer" className={`${btn} border-2 border-line`}><MessageCircle className="h-5 w-5" aria-hidden="true" />{t("emergency.share.whatsappAny")}</a>
        <a href={`sms:?body=${enc}`} className={`${btn} border-2 border-line`}><MessageSquareText className="h-5 w-5" aria-hidden="true" />{t("emergency.share.smsAny")}</a>
      </div>

      {(!contact || editing) && (
        <form onSubmit={saveContact} className="mt-4 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
          <label className="sr-only" htmlFor="ec-name">{t("emergency.contact.name")}</label>
          <input id="ec-name" className="input min-h-[52px]" placeholder={t("emergency.contact.name")} value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" />
          <label className="sr-only" htmlFor="ec-phone">{t("emergency.contact.phone")}</label>
          <input id="ec-phone" className="input min-h-[52px]" inputMode="tel" placeholder={t("emergency.contact.phone")} value={phone} onChange={(e) => setPhone(e.target.value)} autoComplete="off" />
          <button type="submit" className="btn-primary min-h-[52px]"><UserPlus className="h-5 w-5" aria-hidden="true" />{t("emergency.contact.save")}</button>
          {editing && <button type="button" className="btn-ghost min-h-[44px] sm:col-span-3 sm:justify-self-start" onClick={() => setEditing(false)}><X className="h-4 w-4" aria-hidden="true" />{t("common.cancel")}</button>}
          {err && <p className="text-sm font-semibold text-emergency sm:col-span-3" role="alert">{err}</p>}
        </form>
      )}
      <p className="mt-3 text-xs text-muted">{t("emergency.contact.deviceOnly")}</p>
    </section>
  );
}
