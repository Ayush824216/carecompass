import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Info, X } from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { api } from "../lib/api.js";
import { dayLabel, futureSlots, slotLabel, timeLabel } from "../lib/format.js";
import { speak } from "../lib/speech.js";
import StatusTimeline from "./StatusTimeline.jsx";
import { Avatar, ErrorState, Spinner } from "./ui.jsx";

export default function BookingModal({ cg, careType, urgency, onClose, preferredSlot }) {
  const { t, lang, location, addBooking, toast, voice } = useApp();
  const slots = useMemo(() => futureSlots(cg).slice(0, 12), [cg]);
  const [slot, setSlot] = useState(() => (preferredSlot ? preferredSlot.toISOString() : slots[0]?.toISOString() || ""));
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(null);
  const [status] = useState(0); // "booked" only: nothing beyond the demo booking is claimed
  const dialogRef = useRef(null);
  const closeRef = useRef(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && dialogRef.current) { // simple focus trap
        const f = dialogRef.current.querySelectorAll("button, input, textarea, a[href]");
        if (!f.length) return;
        const first = f[0];
        const last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose]);

  // no simulated progress: the demo never claims a caregiver was assigned or is on the way

  const byDay = useMemo(() => {
    const groups = [];
    for (const d of slots) {
      const key = d.toDateString();
      let g = groups.find((x) => x.key === key);
      if (!g) { g = { key, label: dayLabel(d, t, lang), items: [] }; groups.push(g); }
      g.items.push(d);
    }
    return groups;
  }, [slots, t, lang]);

  const phoneOk = !phone || /^(\+?91[- ]?)?[6-9]\d{9}$/.test(phone.replace(/\s/g, ""));

  async function confirm(e) {
    e.preventDefault();
    if (!phoneOk) return;
    setBusy(true); setError("");
    try {
      // the phone number and notes stay in the browser (demo): they are not sent to the server
      const r = await api.book({ caregiver_id: cg.caregiver_id, slot: slot || null, care_type: careType, urgency,
        patient_name: name || null, ...(location.lat != null ? { location: { lat: location.lat, lng: location.lng } } : {}) });
      if (r.status !== "confirmed") throw new Error(r.message);
      const b = { booking_id: r.booking_id, caregiver_id: cg.caregiver_id, caregiver_name: cg.name, role: cg.role,
        slot: r.slot || slot || null, care_type: careType, urgency, patient_name: name || null, notes: notes || null,
        created_at: new Date().toISOString(), status: 0 };
      addBooking(b);
      setDone(b);
      toast(t("booking.toast", { name: cg.name }));
      speak(`${t("booking.successTitle")}. ${cg.name}`, voice);
    } catch {
      setError(t("booking.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AnimatePresence>
      <motion.div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-0 sm:items-center sm:p-6"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
        <motion.div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="booking-title"
          initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
          className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-t-3xl bg-surface shadow-lift sm:rounded-3xl">
          <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-line bg-surface px-5 py-4">
            <Avatar name={cg.name} className="h-11 w-11 text-base" />
            <div className="min-w-0 flex-1">
              <h2 id="booking-title" className="truncate text-xl font-semibold">
                {done ? t("booking.successTitle") : t("booking.title", { name: cg.name })}
              </h2>
              <p className="text-sm text-muted">{t(`roles.${cg.role}`)} · {t(`careTypes.${careType}.name`)}</p>
            </div>
            <button ref={closeRef} type="button" onClick={onClose} aria-label={t("common.close")}
              className="flex h-12 w-12 items-center justify-center rounded-xl hover:bg-sunken"><X className="h-5 w-5" aria-hidden="true" /></button>
          </div>

          {done ? (
            <div className="space-y-6 px-5 py-6">
              <div className="flex items-center gap-3 rounded-xl2 bg-routine-soft px-4 py-4 text-routine">
                <CheckCircle2 className="h-8 w-8 shrink-0" aria-hidden="true" />
                <p className="text-lg font-bold">{t("booking.toast", { name: cg.name })}</p>
              </div>
              <dl className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl bg-sunken/60 px-4 py-3"><dt className="eyebrow">{t("booking.bookingId")}</dt><dd className="mt-1 font-mono text-lg font-bold">{done.booking_id}</dd></div>
                <div className="rounded-xl bg-sunken/60 px-4 py-3"><dt className="eyebrow">{t("booking.caregiver")}</dt><dd className="mt-1 font-semibold">{cg.name}</dd></div>
                <div className="rounded-xl bg-sunken/60 px-4 py-3"><dt className="eyebrow">{t("booking.time")}</dt><dd className="mt-1 font-semibold">{done.slot ? slotLabel(new Date(done.slot), t, lang) : "—"}</dd></div>
              </dl>
              <div>
                <p className="eyebrow mb-3">{t("booking.track")}</p>
                <StatusTimeline current={status} />
              </div>
              <div className="flex flex-col gap-3 sm:flex-row">
                <Link to="/bookings" className="btn-ghost flex-1" onClick={onClose}>{t("booking.viewBookings")}</Link>
                <button type="button" className="btn-primary flex-1" onClick={onClose}>{t("booking.done")}</button>
              </div>
            </div>
          ) : (
            <form onSubmit={confirm} className="space-y-6 px-5 py-6">
              <fieldset>
                <legend className="mb-3 text-lg font-semibold">{t("booking.slot")}</legend>
                {slots.length === 0 ? (
                  <p className="flex items-start gap-2 rounded-xl bg-sunken px-4 py-3"><Info className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />{t("booking.noSlots")}</p>
                ) : (
                  <div className="space-y-3">
                    {byDay.map((g) => (
                      <div key={g.key}>
                        <p className="mb-1.5 text-sm font-bold text-muted">{g.label}</p>
                        <div className="flex flex-wrap gap-2">
                          {g.items.map((d) => {
                            const v = d.toISOString();
                            const on = v === slot;
                            return (
                              <label key={v} className={`flex min-h-[48px] cursor-pointer items-center rounded-xl border-2 px-4 font-semibold ${on ? "border-primary bg-primary text-primary-ink" : "border-line bg-surface hover:border-primary"}`}>
                                <input type="radio" name="slot" value={v} checked={on} onChange={() => setSlot(v)} className="sr-only" />
                                {timeLabel(d, lang)}
                              </label>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </fieldset>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="bk-name" className="mb-1.5 block font-semibold">{t("booking.patientName")}</label>
                  <input id="bk-name" className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
                </div>
                <div>
                  <label htmlFor="bk-phone" className="mb-1.5 block font-semibold">{t("booking.contact")}</label>
                  <input id="bk-phone" className={`input ${phoneOk ? "" : "border-emergency"}`} value={phone} onChange={(e) => setPhone(e.target.value)}
                    inputMode="tel" autoComplete="tel" placeholder="98xxxxxxxx" aria-describedby="bk-phone-note" aria-invalid={!phoneOk} />
                  <p id="bk-phone-note" className={`mt-1 text-sm ${phoneOk ? "text-muted" : "font-semibold text-emergency"}`}>
                    {phoneOk ? t("booking.contactNote") : t("booking.invalidPhone")}
                  </p>
                </div>
              </div>
              <div>
                <label htmlFor="bk-notes" className="mb-1.5 block font-semibold">{t("booking.notes")}</label>
                <textarea id="bk-notes" rows={2} className="input py-3" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={t("booking.notesPlaceholder")} />
              </div>
              {error && <ErrorState message={error} />}
              <button type="submit" className="btn-primary w-full min-h-[56px] text-lg" disabled={busy || !phoneOk}>
                {busy ? <><Spinner />{t("booking.confirming")}</> : t("booking.confirm")}
              </button>
            </form>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
