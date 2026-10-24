import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import {
  Accessibility, Ambulance, ArrowRight, Ban, CheckCircle2, Ear, HeartPulse, Languages, MapPin, Mic, Phone,
  ShieldCheck, Siren, Stethoscope, Type, UserCheck, UsersRound,
} from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { CARE_ICON, CARE_ORDER } from "../lib/care.js";
import { api } from "../lib/api.js";
import { haversineKm, kmLabel } from "../lib/format.js";
import { locationLabel } from "../lib/locations.js";
import { Avatar, Stars, UrgencyBadge } from "../components/ui.jsx";

const SAKET = { lat: 28.5245, lng: 77.2066 };

function Ecg({ className = "" }) {
  const reduce = useReducedMotion();
  return (
    <svg viewBox="0 0 600 80" preserveAspectRatio="none" className={className} aria-hidden="true">
      <motion.path d="M0 40 H170 L185 40 L195 18 L208 62 L220 6 L234 74 L246 40 H330 L342 40 L350 28 L360 50 L368 40 H600"
        fill="none" stroke="rgb(var(--primary))" strokeOpacity=".28" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
        initial={reduce ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 2.2, ease: "easeInOut" }} />
    </svg>
  );
}

function Pin({ x, y, Icon, label, tone = "primary" }) {
  return (
    <div className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${x}%`, top: `${y}%` }}>
      <div className={`flex h-10 w-10 items-center justify-center rounded-full border-[3px] border-white shadow-lift ${tone === "user" ? "bg-accent" : "bg-primary"} text-white`}>
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>
      <span className="absolute left-1/2 top-full mt-1 -translate-x-1/2 whitespace-nowrap rounded-md bg-surface/95 px-1.5 py-0.5 font-mono text-[0.62rem] font-medium text-ink shadow-card">
        {label}
      </span>
    </div>
  );
}

/** On-brand hero composition: stylised NCR map, caregiver pins, floating triage + caregiver cards, ECG motif. */
function HeroVisual() {
  const { t } = useApp();
  const reduce = useReducedMotion();
  const v = (k) => t(`landing.visual.${k}`);
  const float = (delay) => (reduce ? {} : { initial: { opacity: 0, y: 14 }, animate: { opacity: 1, y: 0 }, transition: { delay, duration: 0.5 } });
  // pin positions (% of map card) and the dashed distance lines in the same coordinate space (viewBox 0 0 100 100)
  const you = [46, 56];
  const pins = [
    { x: 24, y: 34, Icon: Ambulance, label: `${v("paramedic")} · 3.1 km` },
    { x: 72, y: 38, Icon: HeartPulse, label: `${v("nurse")} · 2.4 km` },
    { x: 86, y: 64, Icon: Stethoscope, label: `${v("doctor")} · 5.0 km` },
  ];
  return (
    <div className="relative mx-auto aspect-[4/5] w-full max-w-[560px] sm:aspect-square" role="img"
      aria-label={`${v("example")}: ${v("triageFrom")} → ${v("triageTo")}, ${v("urg")}. ${v("cgName")}, ${v("cgMeta")}`}>
      <Ecg className="absolute -left-[8%] top-[48%] h-16 w-[116%]" />

      {/* map card */}
      <motion.div {...float(0)} className="absolute bottom-[16%] left-[4%] right-0 top-[7%] overflow-hidden rounded-[1.6rem] border border-line bg-surface shadow-lift">
        <div className="absolute inset-0 bg-[linear-gradient(rgb(var(--line)/.55)_1px,transparent_1px),linear-gradient(90deg,rgb(var(--line)/.55)_1px,transparent_1px)] bg-[size:28px_28px]" aria-hidden="true" />
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden="true">
          <path d="M62 -2 C58 14 66 26 60 40 C55 52 63 64 58 78 C55 88 60 96 57 104" fill="none" stroke="rgb(var(--accent)/.35)" strokeWidth="3.2" />
          <ellipse cx="46" cy="52" rx="30" ry="26" fill="none" stroke="rgb(var(--muted)/.25)" strokeWidth=".8" />
          <ellipse cx="46" cy="54" rx="17" ry="15" fill="none" stroke="rgb(var(--muted)/.25)" strokeWidth=".8" />
          <path d="M0 70 L100 30 M10 0 L40 100 M100 82 L30 40" stroke="rgb(var(--muted)/.18)" strokeWidth=".7" />
          {pins.map((p) => (
            <line key={p.label} x1={you[0]} y1={you[1]} x2={p.x} y2={p.y} stroke="rgb(var(--primary))" strokeOpacity=".55" strokeWidth=".7" strokeDasharray="2 1.6" />
          ))}
        </svg>
        <span className="absolute left-4 top-3 font-mono text-[0.68rem] font-medium uppercase tracking-[0.16em] text-muted">{v("map")}</span>
        {[["Rohini", 14, 14], ["Dwarka", 8, 58], ["Saket", 40, 70], ["Noida", 84, 80], ["Gurugram", 14, 88]].map(([n, x, y]) => (
          <span key={n} className="absolute font-mono text-[0.6rem] text-muted/80" style={{ left: `${x}%`, top: `${y}%` }} aria-hidden="true">{n}</span>
        ))}
        <div className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${you[0]}%`, top: `${you[1]}%` }} aria-hidden="true">
          <span className="absolute inset-0 -m-3 rounded-full bg-accent/20 motion-safe:animate-ping" />
          <div className="relative flex h-9 w-9 items-center justify-center rounded-full border-[3px] border-white bg-accent text-white shadow-lift">
            <MapPin className="h-4 w-4" />
          </div>
          <span className="absolute left-1/2 top-full mt-1 -translate-x-1/2 rounded-md bg-accent px-1.5 py-0.5 font-mono text-[0.62rem] font-medium text-white">{v("you")}</span>
        </div>
        {pins.map((p) => <Pin key={p.label} {...p} />)}
      </motion.div>

      {/* safety chip */}
      <motion.div {...float(0.35)} className="absolute left-0 top-0 flex items-center gap-2 rounded-full border border-routine/30 bg-surface px-3.5 py-2 text-sm font-semibold text-routine shadow-lift">
        <ShieldCheck className="h-4 w-4" aria-hidden="true" />{v("safety")}
      </motion.div>

      {/* floating caregiver card */}
      <motion.div {...float(0.75)} className="absolute right-[-2%] top-[18%] w-[52%] min-w-[200px] rounded-2xl border border-line bg-surface p-3.5 shadow-lift sm:right-[-6%]">
        <div className="flex items-center gap-3">
          <Avatar name="Priya" className="h-11 w-11 text-base" seed={0} />
          <div className="min-w-0">
            <p className="flex items-center gap-1 font-bold leading-tight">{v("cgName")}<CheckCircle2 className="h-4 w-4 text-primary" aria-hidden="true" /></p>
            <p className="truncate text-xs text-muted">{v("cgMeta")}</p>
          </div>
        </div>
      </motion.div>

      {/* floating triage card */}
      <motion.div {...float(0.55)} className="absolute bottom-0 left-0 w-[74%] min-w-[250px] rounded-2xl border border-line bg-surface p-4 shadow-lift">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-muted">{v("example")}</span>
          <HeartPulse className="h-4 w-4 text-primary" aria-hidden="true" />
        </div>
        <p className="mt-1 text-sm text-muted">{v("triageFrom")}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-soft text-primary-deep"><Ambulance className="h-5 w-5" aria-hidden="true" /></span>
          <span className="font-display text-lg font-bold">{v("triageTo")}</span>
          <UrgencyBadge urgency="same_day" compact />
        </div>
      </motion.div>
    </div>
  );
}

function Reveal({ children, delay = 0, className = "" }) {
  return (
    <motion.div initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.4, delay }} className={className}>
      {children}
    </motion.div>
  );
}

function CaregiverPreview() {
  const { t, location } = useApp();
  const [list, setList] = useState(null);
  useEffect(() => {
    api.caregivers().then((all) => {
      const pick = (pred) => [...all].filter(pred).sort((a, b) => b.rating - a.rating)[0];
      setList([pick((c) => c.role === "paramedic"), pick((c) => c.role === "nurse"), pick((c) => c.role === "specialist")].filter(Boolean));
    }).catch(() => setList([]));
  }, []);
  const ref = location.lat != null ? location : SAKET;
  const place = location.lat != null ? locationLabel(location, t) : "Saket";
  if (list && list.length === 0) return null;
  return (
    <section className="container-page py-16 md:py-20" aria-labelledby="preview-h">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="preview-h" className="text-3xl font-bold md:text-4xl">{t("landing.previewTitle")}</h2>
          <p className="mt-2 text-lg text-muted">{t("landing.previewSub")}</p>
        </div>
        <Link to="/caregivers" className="btn-ghost">{t("landing.previewAll")}<ArrowRight className="h-4 w-4" aria-hidden="true" /></Link>
      </div>
      <div className="mt-8 grid gap-5 md:grid-cols-3">
        {(list || [0, 1, 2]).map((c, i) => c?.caregiver_id ? (
          <Reveal key={c.caregiver_id} delay={i * 0.06}>
            <article className="card p-5">
              <div className="flex items-center gap-4">
                <Avatar name={c.name.replace(/^Dr\.\s*/, "")} seed={i} />
                <div className="min-w-0">
                  <h3 className="font-sans text-lg font-bold leading-tight">{c.name}</h3>
                  <p className="text-sm text-muted">{t(`roles.${c.role}`)}{c.specialty ? ` · ${t(`specialty.${c.specialty}`)}` : ""}</p>
                  <div className="mt-1"><Stars rating={c.rating} /></div>
                </div>
              </div>
              <dl className="mt-4 space-y-1.5 text-sm">
                <div className="flex items-center gap-2"><MapPin className="h-4 w-4 text-primary" aria-hidden="true" /><dt className="sr-only">{t("common.away")}</dt>
                  <dd><span className="font-semibold">{kmLabel(haversineKm(ref, c), t)}</span> {t("landing.previewFrom", { place })} · {c.locality}</dd></div>
                <div className="flex items-center gap-2"><Languages className="h-4 w-4 text-primary" aria-hidden="true" /><dt className="sr-only">{t("common.languages")}</dt>
                  <dd>{c.languages.map((l) => t(`langNames.${l}`)).join(", ")}</dd></div>
              </dl>
            </article>
          </Reveal>
        ) : <div key={i} className="h-[190px] animate-pulse rounded-xl2 bg-sunken" aria-hidden="true" />)}
      </div>
    </section>
  );
}

export default function Home() {
  const { t, lang, setLang } = useApp();
  const trustIcons = [Languages, Mic, ShieldCheck, Ban];
  const stepIcons = [Mic, ShieldCheck, Stethoscope, UserCheck];
  const builtIcons = [Type, Ear, Accessibility, UsersRound];

  return (
    <>
      {/* HERO */}
      <section className="grain relative overflow-hidden border-b border-line bg-[radial-gradient(ellipse_at_top_right,rgb(var(--primary-soft))_0%,transparent_55%),radial-gradient(ellipse_at_bottom_left,rgb(var(--accent-soft))_0%,transparent_50%)]">
        <div className="container-page grid items-center gap-14 py-12 md:py-20 lg:grid-cols-[1.05fr_1fr]">
          <div>
            <p className="eyebrow mb-5 text-primary-deep">{t("landing.eyebrow")}</p>
            <h1 className="text-[2.6rem] font-extrabold leading-[1.06] sm:text-6xl xl:text-[4.1rem]">
              {t("landing.title").split(/(?<=[.।])\s*/).filter(Boolean).map((line) => (
                <span key={line} className="block">{line.replace(/[.।]$/, "")}<span className="text-primary">{/।$/.test(line) ? "।" : "."}</span></span>
              ))}
            </h1>
            <p className="mt-3 flex flex-wrap items-center gap-3 text-xl font-semibold text-primary-deep" lang={lang === "en" ? "hi" : "en"}>
              {lang === "en" ? t("landing.subHi") : t("landing.subEn")}
              <button type="button" onClick={() => setLang(lang === "en" ? "hi" : "en")}
                className="rounded-full border border-primary/30 px-3 py-1 text-sm font-semibold text-primary hover:bg-primary-soft">
                {t("landing.subToggle")}
              </button>
            </p>
            <p className="mt-5 max-w-xl text-lg text-muted md:text-xl">{t("landing.sub")}</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link to="/care" className="btn-primary min-h-[60px] px-7 text-lg">{t("landing.cta")}<ArrowRight className="h-5 w-5" aria-hidden="true" /></Link>
              <Link to="/how-it-works" className="btn-ghost min-h-[60px] px-7 text-lg">{t("landing.secondary")}</Link>
            </div>
          </div>
          <HeroVisual />
        </div>
      </section>

      {/* TRUST STRIP */}
      <section className="border-b border-line bg-surface">
        <ul className="container-page grid gap-4 py-6 sm:grid-cols-2 lg:grid-cols-4">
          {t("landing.trust").map((label, i) => {
            const Icon = trustIcons[i];
            return (
              <li key={label} className="flex items-center gap-3 font-semibold">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary-deep"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                {label}
              </li>
            );
          })}
        </ul>
      </section>

      {/* HOW IT WORKS */}
      <section className="container-page py-16 md:py-20" aria-labelledby="steps-h">
        <Reveal className="max-w-2xl">
          <p className="eyebrow mb-3">01 — 04</p>
          <h2 id="steps-h" className="text-3xl font-bold md:text-4xl">{t("landing.stepsTitle")}</h2>
          <p className="mt-2 text-lg text-muted">{t("landing.stepsSub")}</p>
        </Reveal>
        <ol className="relative mt-12 grid gap-10 md:grid-cols-4 md:gap-6">
          <span className="absolute left-7 top-7 hidden h-0.5 w-[calc(100%-56px)] bg-[linear-gradient(90deg,rgb(var(--primary)/.5)_50%,transparent_50%)] bg-[size:12px_2px] md:block" aria-hidden="true" />
          <span className="absolute bottom-7 left-7 top-7 w-0.5 bg-[linear-gradient(rgb(var(--primary)/.5)_50%,transparent_50%)] bg-[size:2px_12px] md:hidden" aria-hidden="true" />
          {t("landing.steps").map((s, i) => {
            const Icon = stepIcons[i];
            return (
              <Reveal key={s.t} delay={i * 0.07} className="relative flex gap-5 md:block">
                <span className="relative z-10 flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary text-white shadow-lift">
                  <Icon className="h-6 w-6" aria-hidden="true" />
                </span>
                <div className="md:mt-5">
                  <p className="font-mono text-xs text-muted">0{i + 1}</p>
                  <h3 className="text-xl font-bold">{s.t}</h3>
                  <p className="mt-1 text-muted">{s.d}</p>
                </div>
              </Reveal>
            );
          })}
        </ol>
      </section>

      {/* CARE TYPES */}
      <section className="border-y border-line bg-surface/70">
        <div className="container-page py-16 md:py-20">
          <Reveal className="max-w-2xl">
            <h2 className="text-3xl font-bold md:text-4xl">{t("landing.careTitle")}</h2>
            <p className="mt-2 text-lg text-muted">{t("landing.careSub")}</p>
          </Reveal>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {CARE_ORDER.map((c, i) => {
              const Icon = CARE_ICON[c];
              const em = c === "emergency_referral";
              return (
                <Reveal key={c} delay={i * 0.05}>
                  <article className={`flex h-full flex-col rounded-xl2 border p-5 ${em ? "border-emergency/40 bg-emergency-soft/70" : "border-line bg-surface shadow-card"}`}>
                    <span className={`flex h-12 w-12 items-center justify-center rounded-xl ${em ? "bg-emergency text-white" : "bg-primary-soft text-primary-deep"}`}>
                      <Icon className="h-6 w-6" aria-hidden="true" />
                    </span>
                    <h3 className={`mt-4 text-lg font-bold leading-snug ${em ? "text-emergency-deep" : ""}`}>{t(`careTypes.${c}.name`)}</h3>
                    <p className="mt-2 text-[0.95rem] text-muted">{t(`landing.careWhen.${c}`)}</p>
                  </article>
                </Reveal>
              );
            })}
          </div>
        </div>
      </section>

      {/* EMERGENCY STRIP */}
      <section className="bg-emergency text-white" aria-labelledby="em-h">
        <div className="container-page grid items-center gap-8 py-12 lg:grid-cols-[1.3fr_1fr]">
          <div className="flex gap-5">
            <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white/15"><Siren className="h-7 w-7" aria-hidden="true" /></span>
            <div>
              <h2 id="em-h" className="text-2xl font-bold md:text-3xl">{t("landing.emTitle")}</h2>
              <p className="mt-2 text-lg text-white/90">{t("landing.emBody")}</p>
            </div>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row lg:justify-end">
            <a href="tel:112" className="btn min-h-[60px] bg-white px-6 text-lg text-emergency hover:bg-emergency-soft"><Phone className="h-5 w-5" aria-hidden="true" />{t("landing.emCall")}</a>
            <a href="tel:108" className="btn min-h-[60px] border-2 border-white px-6 text-lg text-white hover:bg-white/10"><Ambulance className="h-5 w-5" aria-hidden="true" />{t("landing.emAmb")}</a>
          </div>
        </div>
      </section>

      <CaregiverPreview />

      {/* BUILT FOR EVERY HOME */}
      <section className="border-t border-line bg-surface/70">
        <div className="container-page py-16 md:py-20">
          <Reveal><h2 className="text-3xl font-bold md:text-4xl">{t("landing.builtTitle")}</h2></Reveal>
          <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {t("landing.built").map((b, i) => {
              const Icon = builtIcons[i];
              return (
                <Reveal key={b.t} delay={i * 0.06}>
                  <span className="flex h-14 w-14 items-center justify-center rounded-full border-2 border-primary/30 bg-primary-soft text-primary-deep"><Icon className="h-6 w-6" aria-hidden="true" /></span>
                  <h3 className="mt-4 text-xl font-bold">{b.t}</h3>
                  <p className="mt-1 text-muted">{b.d}</p>
                </Reveal>
              );
            })}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="container-page pt-16">
        <div className="grain flex flex-col items-start justify-between gap-6 overflow-hidden rounded-[1.75rem] bg-primary-deep px-6 py-10 text-white md:flex-row md:items-center md:px-12">
          <div>
            <h2 className="text-3xl font-bold">{t("landing.ctaTitle")}</h2>
            <p className="mt-1 text-lg text-white/85">{t("landing.ctaSub")}</p>
          </div>
          <Link to="/care" className="btn min-h-[60px] bg-white px-8 text-lg text-primary-deep hover:bg-primary-soft">{t("landing.cta")}<ArrowRight className="h-5 w-5" aria-hidden="true" /></Link>
        </div>
      </section>
    </>
  );
}
