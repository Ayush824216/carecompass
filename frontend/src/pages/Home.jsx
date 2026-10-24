import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowRight, BadgeCheck, CheckCircle2, Clock, Languages, Mic, MousePointerClick, ShieldAlert, ShieldCheck,
  Stethoscope, Type, UserRoundSearch, XCircle,
} from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { CARE_ICON, CARE_ORDER } from "../lib/care.js";
import { Logo } from "../components/Layout.jsx";
import { UrgencyBadge } from "../components/ui.jsx";

/** Looping sample conversation: Hinglish message -> understanding -> result card. */
function MiniDemo() {
  const { t } = useApp();
  const reduce = useReducedMotion();
  const [step, setStep] = useState(reduce ? 3 : 0);
  useEffect(() => {
    if (reduce) { setStep(3); return undefined; }
    const timings = [900, 1400, 1500, 5200];
    const id = setTimeout(() => setStep((s) => (s + 1) % 4), timings[step]);
    return () => clearTimeout(id);
  }, [step, reduce]);

  const msg = t("home.demoUser");
  return (
    <div className="relative" aria-label={t("home.demoLabel")} role="img">
      <div className="absolute -inset-4 -z-10 rounded-[2rem] bg-primary-soft/60 rotate-[-2deg]" aria-hidden="true" />
      <div className="card overflow-hidden shadow-lift">
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <span className="flex items-center gap-2 font-semibold"><Logo className="h-6 w-6" />CareCompass</span>
          <span className="chip border-accent/40 bg-accent-soft text-xs font-bold uppercase tracking-wider">{t("home.demoLabel")}</span>
        </div>
        <div className="min-h-[360px] space-y-4 bg-bg/50 p-5" aria-hidden="true">
          <motion.div initial={false} animate={{ opacity: step >= 0 ? 1 : 0 }} className="flex justify-end">
            <div className="max-w-[85%] rounded-2xl rounded-tr-md bg-primary px-4 py-3 text-primary-ink">
              {step === 0 && !reduce ? <TypeOut text={msg} /> : msg}
            </div>
          </motion.div>
          <AnimatePresence>
            {step >= 1 && (
              <motion.div key="chips" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex flex-wrap gap-2">
                <span className="chip text-sm font-semibold"><Languages className="h-4 w-4 text-primary" />{t("langNames.hinglish")}</span>
                <span className="chip text-sm font-semibold">bukhar <ArrowRight className="h-3.5 w-3.5" /> fever</span>
                <span className="chip text-sm font-semibold">khansi <ArrowRight className="h-3.5 w-3.5" /> cough</span>
                <span className="chip border-routine/40 bg-routine-soft text-sm font-semibold text-routine"><ShieldCheck className="h-4 w-4" />{t("panel.noRedFlags")}</span>
              </motion.div>
            )}
            {step >= 2 && (
              <motion.div key="card" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                className="rounded-2xl border-2 border-primary bg-surface p-4">
                <div className="flex items-center gap-3">
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-soft text-primary-deep"><Stethoscope className="h-6 w-6" /></span>
                  <div>
                    <p className="font-display text-xl font-semibold leading-tight">{t("careTypes.paramedic_home_visit.name")}</p>
                    <div className="mt-1"><UrgencyBadge urgency="same_day" /></div>
                  </div>
                </div>
                <p className="mt-3 text-[0.95rem]">{t("home.demoReason")}</p>
                {step >= 3 && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 flex items-start gap-2 rounded-xl bg-primary-soft/50 px-3 py-2 text-sm font-semibold">
                    <UserRoundSearch className="mt-0.5 h-4 w-4 shrink-0 text-primary" />{t("home.demoMatch")}
                  </motion.p>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

function TypeOut({ text }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setN((x) => (x >= text.length ? x : x + 2)), 30);
    return () => clearInterval(id);
  }, [text]);
  return <>{text.slice(0, n)}<span className="ml-0.5 inline-block h-4 w-0.5 translate-y-0.5 animate-pulse bg-white/80" /></>;
}

function Reveal({ children, delay = 0, className = "" }) {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.45, delay }} className={className}>
      {children}
    </motion.div>
  );
}

export default function Home() {
  const { t } = useApp();
  const three = [
    ["q1", Stethoscope, "01"], ["q2", Clock, "02"], ["q3", UserRoundSearch, "03"],
  ];
  const safety = [["safety1", ShieldAlert], ["safety2", BadgeCheck], ["safety3", XCircle], ["safety4", ShieldCheck]];
  const built = [["built1", Mic], ["built2", Languages], ["built3", Type], ["built4", MousePointerClick]];

  return (
    <>
      {/* HERO */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute right-[-10%] top-[-20%] -z-10 h-[520px] w-[520px] rounded-full bg-accent-soft/70 blur-3xl" aria-hidden="true" />
        <div className="container-page grid items-center gap-12 py-12 md:py-20 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <p className="eyebrow mb-4 text-primary-deep">{t("home.eyebrow")}</p>
            <h1 className="text-4xl font-semibold leading-[1.08] sm:text-5xl xl:text-6xl">{t("home.title")}</h1>
            <p className="mt-5 max-w-xl text-lg text-muted md:text-xl">{t("home.subtitle")}</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link to="/care" className="btn-primary min-h-[60px] px-7 text-lg">
                {t("home.cta")}<ArrowRight className="h-5 w-5" aria-hidden="true" />
              </Link>
              <Link to="/how-it-works" className="btn-ghost min-h-[60px] px-7 text-lg">{t("home.secondary")}</Link>
            </div>
            <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm font-semibold text-ink/80">
              {["trust1", "trust2", "trust3"].map((k) => (
                <li key={k} className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-routine" aria-hidden="true" />{t(`home.${k}`)}</li>
              ))}
            </ul>
          </div>
          <MiniDemo />
        </div>
      </section>

      {/* THREE QUESTIONS */}
      <section className="border-y border-line bg-surface">
        <div className="container-page py-16">
          <Reveal className="max-w-2xl">
            <h2 className="text-3xl font-semibold md:text-4xl">{t("home.threeTitle")}</h2>
            <p className="mt-2 text-lg text-muted">{t("home.threeSub")}</p>
          </Reveal>
          <div className="mt-10 grid gap-0 md:grid-cols-3 md:divide-x md:divide-line">
            {three.map(([k, Icon, n], i) => (
              <Reveal key={k} delay={i * 0.08} className="border-t border-line py-6 md:border-t-0 md:px-8 md:py-2 md:first:pl-0">
                <div className="flex items-center gap-3">
                  <span className="font-display text-4xl font-semibold text-accent">{n}</span>
                  <Icon className="h-7 w-7 text-primary" aria-hidden="true" />
                </div>
                <h3 className="mt-3 text-2xl font-semibold">{t(`home.${k}`)}</h3>
                <p className="mt-2 text-muted">{t(`home.${k}d`)}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* CARE TYPES */}
      <section className="container-page py-16 md:py-20">
        <Reveal className="max-w-2xl">
          <h2 className="text-3xl font-semibold md:text-4xl">{t("home.careTitle")}</h2>
          <p className="mt-2 text-lg text-muted">{t("home.careSub")}</p>
        </Reveal>
        <ol className="mt-10 divide-y divide-line overflow-hidden rounded-xl2 border border-line bg-surface">
          {CARE_ORDER.map((c, i) => {
            const Icon = CARE_ICON[c];
            const em = c === "emergency_referral";
            return (
              <Reveal key={c} delay={i * 0.05}>
                <li className={`grid gap-4 p-5 md:grid-cols-[64px_1.1fr_1.4fr] md:items-start md:gap-8 md:p-7 ${em ? "bg-emergency-soft/60" : ""}`}>
                  <span className={`flex h-14 w-14 items-center justify-center rounded-2xl ${em ? "bg-emergency text-white" : "bg-primary-soft text-primary-deep"}`}>
                    <Icon className="h-7 w-7" aria-hidden="true" />
                  </span>
                  <div>
                    <h3 className={`text-2xl font-semibold ${em ? "text-emergency-deep" : ""}`}>{t(`careTypes.${c}.name`)}</h3>
                    <p className="mt-1 text-muted">{t(`careTypes.${c}.meaning`)}</p>
                  </div>
                  <div className="rounded-xl bg-sunken/60 px-4 py-3">
                    <p className="eyebrow mb-1">{t("home.whenUsed")}</p>
                    <p>{t(`careTypes.${c}.when`)}</p>
                  </div>
                </li>
              </Reveal>
            );
          })}
        </ol>
      </section>

      {/* SAFETY */}
      <section className="bg-primary-deep text-white">
        <div className="container-page grid gap-12 py-16 md:py-20 lg:grid-cols-[1fr_1.15fr]">
          <Reveal>
            <p className="eyebrow mb-3 text-accent-soft">{t("home.safetyEyebrow")}</p>
            <h2 className="text-3xl font-semibold md:text-4xl">{t("home.safetyTitle")}</h2>
            <p className="mt-4 text-lg text-white/85">{t("home.safetySub")}</p>
            <div className="mt-8 space-y-3" aria-hidden="true">
              <div className="flex flex-wrap items-center gap-3 rounded-xl bg-white/10 px-4 py-3">
                <span className="font-mono text-sm">"saans ki dikkat nahi hai"</span>
                <ArrowRight className="h-4 w-4 text-white/60" />
                <span className="inline-flex items-center gap-1.5 rounded-full bg-routine-soft px-3 py-1 text-sm font-bold text-routine"><ShieldCheck className="h-4 w-4" />{t("panel.noRedFlags")}</span>
              </div>
              <div className="flex flex-wrap items-center gap-3 rounded-xl bg-white/10 px-4 py-3">
                <span className="font-mono text-sm">"saans nahi aa rahi"</span>
                <ArrowRight className="h-4 w-4 text-white/60" />
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emergency px-3 py-1 text-sm font-bold text-white"><ShieldAlert className="h-4 w-4" />{t("careTypes.emergency_referral.name")}</span>
              </div>
            </div>
          </Reveal>
          <div className="grid gap-5 sm:grid-cols-2">
            {safety.map(([k, Icon], i) => (
              <Reveal key={k} delay={i * 0.07} className="rounded-xl2 border border-white/15 bg-white/[0.06] p-5">
                <Icon className="h-7 w-7 text-accent-soft" aria-hidden="true" />
                <h3 className="mt-3 font-sans text-lg font-bold">{t(`home.${k}`)}</h3>
                <p className="mt-1 text-white/80">{t(`home.${k}d`)}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* BUILT FOR EVERYONE */}
      <section className="container-page py-16 md:py-20">
        <Reveal><h2 className="text-3xl font-semibold md:text-4xl">{t("home.builtTitle")}</h2></Reveal>
        <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {built.map(([k, Icon], i) => (
            <Reveal key={k} delay={i * 0.06}>
              <span className="flex h-14 w-14 items-center justify-center rounded-full border-2 border-primary text-primary"><Icon className="h-6 w-6" aria-hidden="true" /></span>
              <h3 className="mt-4 font-sans text-xl font-bold">{t(`home.${k}`)}</h3>
              <p className="mt-1 text-muted">{t(`home.${k}d`)}</p>
            </Reveal>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="container-page">
        <div className="flex flex-col items-start justify-between gap-6 rounded-xl2 bg-accent-soft px-6 py-10 md:flex-row md:items-center md:px-12">
          <div>
            <h2 className="text-3xl font-semibold">{t("home.ctaTitle")}</h2>
            <p className="mt-1 text-lg text-ink/80">{t("home.ctaSub")}</p>
          </div>
          <Link to="/care" className="btn-primary min-h-[60px] px-8 text-lg">{t("home.cta")}<ArrowRight className="h-5 w-5" aria-hidden="true" /></Link>
        </div>
      </section>
    </>
  );
}
