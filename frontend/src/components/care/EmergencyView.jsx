import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Ambulance, ArrowLeft, ExternalLink, MapPin, MessageCircle, MessageSquare, Phone, ShieldAlert, Users, Volume2 } from "lucide-react";
import { useApp } from "../../context/AppContext.jsx";
import { api } from "../../lib/api.js";
import { speak } from "../../lib/speech.js";
import { locationLabel } from "../../lib/locations.js";
import { flagLabel } from "../../lib/care.js";
import CaregiverMap from "../CaregiverMap.jsx";
import { smsAllHref, smsHref, sosMessage, telHref, waHref } from "../../lib/sos.js";

const BLINKIT_URL = "https://blinkit.com/"; // booking happens inside the Blinkit app; no API call is made

/** Big call buttons first, three short steps, small cards. The call-for-help path is always on screen. */
export default function EmergencyView({ response, debug, onBack, onUndo }) {
  const { t, location, voice, sosContacts } = useApp();
  const headingRef = useRef(null);
  const [sosOpen, setSosOpen] = useState(false);
  const [sosState, setSosState] = useState(""); // "" | sending | sent | manual
  const place = locationLabel(location, t);
  const signs = (response.red_flags || []).map((f) => flagLabel(f, t, debug));
  const message = sosMessage({ t, signs, location, place });
  const steps = [t("emergency.quick1"), t("emergency.quick2"), t("emergency.quick3")];
  const crisis = (response.red_flags || []).includes("suicidal_intent");

  useEffect(() => {
    headingRef.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  /** One tap: server SMS if configured and confirmed, else the phone's SMS app with every contact filled in. */
  const sos = async () => {
    setSosOpen(true);
    if (!sosContacts.length) return;
    setSosState("sending");
    try {
      const st = await api.sosStatus();
      if (st.enabled) {
        const r = await api.sosSend(sosContacts.map((c) => c.phone), message);
        if (r.sent) { setSosState("sent"); return; }
      }
    } catch { /* offline or server down: the SMS app still works */ }
    setSosState("manual");
    window.location.href = smsAllHref(sosContacts, message);
  };

  const big = "flex min-h-[148px] items-center gap-4 rounded-3xl p-5 shadow-lift sm:p-6";
  return (
    <motion.div role="alertdialog" aria-modal="true" aria-labelledby="em-title" aria-describedby="em-steps"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      className="fixed inset-0 z-[70] overflow-y-auto bg-emergency text-white">
      <div className="mx-auto flex min-h-full max-w-4xl flex-col px-4 py-5 sm:px-8 sm:py-8">
        <button type="button" onClick={onBack}
          className="inline-flex min-h-[48px] w-fit items-center gap-2 rounded-xl px-3 font-semibold text-white/90 hover:bg-white/10">
          <ArrowLeft className="h-5 w-5" aria-hidden="true" />{t("emergency.back")}
        </button>

        <h1 id="em-title" ref={headingRef} tabIndex={-1} className="mt-3 flex items-center gap-3 text-3xl font-semibold outline-none sm:text-4xl">
          <ShieldAlert className="h-9 w-9 shrink-0" aria-hidden="true" />{t("emergency.title")}
        </h1>
        {onUndo && (
          <button type="button" onClick={onUndo} className="mt-1 min-h-[44px] w-fit text-left text-sm font-semibold text-white/90 underline underline-offset-4">
            {t("emergency.undo")}
          </button>
        )}

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <a href="tel:112" className={`${big} bg-white text-emergency`} aria-label={t("emergency.call112")}>
            <Phone className="h-9 w-9 shrink-0" aria-hidden="true" />
            <span><span className="block font-display text-5xl font-bold leading-none">112</span>
              <span className="mt-1 block font-bold">{t("emergency.call112")}</span></span>
          </a>
          <a href="tel:108" className={`${big} bg-emergency-soft text-emergency-deep`} aria-label={t("emergency.call108")}>
            <Ambulance className="h-9 w-9 shrink-0" aria-hidden="true" />
            <span><span className="block font-display text-5xl font-bold leading-none">108</span>
              <span className="mt-1 block font-bold">{t("emergency.call108")}</span></span>
          </a>
          <button type="button" onClick={sos} className={`${big} bg-ink text-white text-left`} aria-label={t("sos.button")}>
            <Users className="h-9 w-9 shrink-0" aria-hidden="true" />
            <span><span className="block font-display text-3xl font-bold leading-none">SOS</span>
              <span className="mt-1 block font-bold">{t("sos.button")}</span></span>
          </button>
        </div>

        <a href={BLINKIT_URL} target="_blank" rel="noreferrer" className={`${big} mt-3 border-2 border-white/70 bg-white/10 text-white hover:bg-white/20`}>
          <Ambulance className="h-9 w-9 shrink-0" aria-hidden="true" />
          <span className="min-w-0 flex-1"><span className="flex items-center gap-2 text-lg font-bold leading-tight sm:text-2xl">{t("emergency.blinkit")}<ExternalLink className="h-4 w-4 shrink-0" aria-hidden="true" /></span>
            <span className="mt-1 block text-sm leading-snug text-white/90 sm:text-base">{t("emergency.blinkitNote")}</span></span>
        </a>

        {crisis && (
          <a href="tel:14416" className={`${big} mt-3 bg-white text-emergency-deep`} aria-label={t("emergency.teleManas")}>
            <Phone className="h-8 w-8 shrink-0 text-primary" aria-hidden="true" />
            <span><span className="block font-display text-3xl font-bold leading-none">14416</span>
              <span className="mt-1 block font-bold">{t("emergency.teleManas")}</span>
              <span className="block text-sm opacity-80">{t("emergency.teleManasD")}</span></span>
          </a>
        )}

        {sosOpen && (
          <section className="mt-3 rounded-3xl bg-white p-4 text-ink" aria-labelledby="sos-h" aria-live="polite">
            <h2 id="sos-h" className="font-semibold">{t("sos.button")}</h2>
            {!sosContacts.length && <p className="mt-1">{t("sos.none")} <Link to="/sos" className="font-semibold underline">{t("sos.addLink")}</Link></p>}
            {sosState === "sending" && <p className="mt-1 text-muted">{t("sos.sending")}</p>}
            {sosState === "sent" && <p className="mt-1 font-semibold text-routine">{t("sos.sent")}</p>}
            {sosState === "manual" && <p className="mt-1 font-semibold">{t("sos.tapSend")}</p>}
            {sosContacts.length > 0 && (
              <ul className="mt-2 divide-y divide-line">
                {sosContacts.map((c, i) => (
                  <li key={`${c.phone}-${i}`} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <span className="font-semibold">{c.name}{c.relation && <span className="font-normal text-muted"> · {c.relation}</span>}</span>
                    <span className="flex gap-2">
                      <a href={telHref(c.phone)} className="btn-ghost min-h-[44px] px-3 text-sm"><Phone className="h-4 w-4" aria-hidden="true" />{t("sos.call")}</a>
                      <a href={waHref(c.phone, message)} target="_blank" rel="noreferrer" className="btn-ghost min-h-[44px] px-3 text-sm"><MessageCircle className="h-4 w-4" aria-hidden="true" />WhatsApp</a>
                      <a href={smsHref(c.phone, message)} className="btn-ghost min-h-[44px] px-3 text-sm"><MessageSquare className="h-4 w-4" aria-hidden="true" />SMS</a>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        <section className="mt-5 rounded-3xl bg-black/20 p-5" aria-labelledby="em-steps-h">
          <div className="flex items-center justify-between gap-3">
            <h2 id="em-steps-h" className="text-xl font-semibold">{t("emergency.steps")}</h2>
            <button type="button" onClick={() => speak(steps.join(" "), true)} aria-label={t("emergency.readAloud")}
              className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-white/15 hover:bg-white/25">
              <Volume2 className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
          <ol id="em-steps" className="mt-3 space-y-2 text-lg">
            {steps.map((s, i) => (
              <li key={i} className="flex gap-3"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white font-bold text-emergency">{i + 1}</span>{s}</li>
            ))}
          </ol>
        </section>

        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {signs.length > 0 && (
            <section className="rounded-2xl bg-black/20 p-4" aria-labelledby="em-flags">
              <h2 id="em-flags" className="text-sm font-semibold uppercase tracking-wide text-white/80">{t("emergency.flags")}</h2>
              <p className="mt-1 font-semibold">{signs.join(" · ")}</p>
            </section>
          )}
          <section className="rounded-2xl bg-black/20 p-4" aria-labelledby="em-loc">
            <h2 id="em-loc" className="flex items-center gap-1 text-sm font-semibold uppercase tracking-wide text-white/80"><MapPin className="h-4 w-4" aria-hidden="true" />{t("emergency.location")}</h2>
            {location.lat != null
              ? <p className="mt-1 font-semibold">{place ? `${place} · ` : ""}<span className="font-mono">{location.lat.toFixed(5)}, {location.lng.toFixed(5)}</span></p>
              : <p className="mt-1 font-semibold">{t("emergency.locationUnknown")}</p>}
            {location.lat != null && <div className="mt-3 text-ink"><CaregiverMap items={[]} user={location} height={160} /></div>}
          </section>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-white/25 pt-4 text-sm">
          <Link to="/sos" className="ml-auto min-h-[44px] content-center font-semibold underline underline-offset-4">{t("sos.manage")}</Link>
        </div>
        {voice && <span className="sr-only" aria-live="assertive">{steps.join(" ")}</span>}
      </div>
    </motion.div>
  );
}
