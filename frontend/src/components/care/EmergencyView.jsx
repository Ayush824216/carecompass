import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { Ambulance, ArrowLeft, Ban, MapPin, Phone, ShieldAlert, Volume2 } from "lucide-react";
import { useApp } from "../../context/AppContext.jsx";
import { speak } from "../../lib/speech.js";
import { locationLabel } from "../../lib/locations.js";

function steps(reasoning) {
  return (reasoning || "").split(/(?<=[.।!?])\s+/).map((s) => s.trim()).filter(Boolean);
}

export default function EmergencyView({ response, onBack }) {
  const { t, location, voice } = useApp();
  const headingRef = useRef(null);
  const list = steps(response.reasoning);
  const gps = location.lat != null;
  const place = locationLabel(location, t);

  useEffect(() => {
    headingRef.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  return (
    <motion.div role="alertdialog" aria-modal="true" aria-labelledby="em-title" aria-describedby="em-steps"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      className="fixed inset-0 z-[70] overflow-y-auto bg-emergency text-white">
      <div className="mx-auto flex min-h-full max-w-5xl flex-col px-4 py-6 sm:px-8 sm:py-10">
        <button type="button" onClick={onBack}
          className="inline-flex min-h-[48px] w-fit items-center gap-2 rounded-xl px-3 font-semibold text-white/90 underline-offset-4 hover:bg-white/10 hover:underline">
          <ArrowLeft className="h-5 w-5" aria-hidden="true" />{t("emergency.back")}
        </button>

        <div className="mt-4 flex items-start gap-4">
          <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-white/15">
            <ShieldAlert className="h-9 w-9" aria-hidden="true" />
          </span>
          <div>
            <h1 id="em-title" ref={headingRef} tabIndex={-1} className="text-3xl font-semibold outline-none focus-visible:outline-none sm:text-5xl">{t("emergency.title")}</h1>
            <p className="mt-1 text-lg text-white/90 sm:text-xl">{t("emergency.subtitle")}</p>
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          <a href="tel:112" className="group flex items-center gap-5 rounded-3xl bg-white p-5 text-emergency shadow-lift sm:p-7" aria-label={t("emergency.call112")}>
            <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-emergency text-white sm:h-20 sm:w-20">
              <Phone className="h-9 w-9 sm:h-10 sm:w-10" aria-hidden="true" />
            </span>
            <span className="min-w-0">
              <span className="block font-display text-5xl font-bold leading-none sm:text-7xl">112</span>
              <span className="mt-1 block text-lg font-bold sm:text-xl">{t("emergency.call112")}</span>
              <span className="block text-sm text-emergency/80">{t("emergency.call112d")}</span>
            </span>
          </a>
          <a href="tel:108" className="flex items-center gap-5 rounded-3xl bg-emergency-soft p-5 text-emergency-deep shadow-lift sm:p-7" aria-label={t("emergency.call108")}>
            <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-emergency-deep text-white sm:h-20 sm:w-20">
              <Ambulance className="h-9 w-9 sm:h-10 sm:w-10" aria-hidden="true" />
            </span>
            <span className="min-w-0">
              <span className="block font-display text-5xl font-bold leading-none sm:text-7xl">108</span>
              <span className="mt-1 block text-lg font-bold sm:text-xl">{t("emergency.call108")}</span>
              <span className="block text-sm opacity-80">{t("emergency.call108d")}</span>
            </span>
          </a>
        </div>

        <div className="mt-8 grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          <section className="rounded-3xl bg-black/20 p-5 sm:p-6" aria-labelledby="em-steps-h">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="em-steps-h" className="text-2xl font-semibold">{t("emergency.steps")}</h2>
              <button type="button" onClick={() => speak(response.reasoning, true)}
                className="inline-flex min-h-[48px] items-center gap-2 rounded-xl bg-white/15 px-4 font-semibold hover:bg-white/25">
                <Volume2 className="h-5 w-5" aria-hidden="true" />{t("emergency.readAloud")}
              </button>
            </div>
            <ol id="em-steps" className="mt-4 space-y-3">
              {list.map((s, i) => (
                <li key={i} className="flex gap-3 text-lg leading-snug">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white font-bold text-emergency">{i + 1}</span>
                  <span className="pt-0.5">{s}</span>
                </li>
              ))}
            </ol>
          </section>

          <div className="space-y-5">
            {response.red_flags?.length > 0 && (
              <section className="rounded-3xl bg-black/20 p-5" aria-labelledby="em-flags">
                <h2 id="em-flags" className="text-xl font-semibold">{t("emergency.flags")}</h2>
                <ul className="mt-3 space-y-2">
                  {response.red_flags.map((f) => (
                    <li key={f} className="flex items-start gap-2 font-semibold">
                      <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />{t(`flags.${f}`)}
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <section className="rounded-3xl bg-white p-5 text-ink" aria-labelledby="em-loc">
              <h2 id="em-loc" className="flex items-center gap-2 text-xl font-semibold"><MapPin className="h-5 w-5 text-emergency" aria-hidden="true" />{t("emergency.location")}</h2>
              {gps ? (
                <>
                  {place && <p className="mt-2 text-lg font-bold">{place}</p>}
                  <p className="mt-1 font-mono text-2xl font-bold tracking-tight sm:text-3xl">{location.lat.toFixed(5)}, {location.lng.toFixed(5)}</p>
                  <p className="mt-1 text-muted">{t("emergency.locationHint")}</p>
                </>
              ) : (
                <p className="mt-3 font-semibold">{t("emergency.locationUnknown")}</p>
              )}
            </section>
            <p className="flex items-start gap-2 rounded-2xl border border-white/40 px-4 py-3 font-semibold">
              <Ban className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />{t("emergency.noBooking")}
            </p>
          </div>
        </div>
        {voice && <span className="sr-only" aria-live="assertive">{response.reasoning}</span>}
      </div>
    </motion.div>
  );
}
