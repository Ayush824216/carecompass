import { useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle, Check, ChevronDown, ClipboardCheck, FlaskConical, HelpCircle, Lightbulb, ListChecks, Phone, ShieldCheck,
  Thermometer, X,
} from "lucide-react";
import { useApp } from "../../context/AppContext.jsx";

const STATUS = {
  present: { Icon: Check, cls: "bg-emergency-soft text-emergency", key: "present" },
  absent: { Icon: X, cls: "bg-routine-soft text-routine", key: "absent" },
  not_asked: { Icon: HelpCircle, cls: "bg-sunken text-muted", key: "notAsked" },
  not_measured: { Icon: Thermometer, cls: "bg-sameday-soft text-[rgb(110_64_0)]", key: "notMeasured" },
  measured: { Icon: Thermometer, cls: "bg-primary-soft text-primary-deep", key: "measured" },
};
const STRENGTH = { strong: "bg-primary text-primary-ink", moderate: "bg-primary-soft text-primary-deep", weak: "bg-sunken text-muted" };

function Section({ id, icon: Icon, title, children, open: initial = false, tone = "" }) {
  const [open, setOpen] = useState(initial);
  return (
    <section className={`rounded-xl2 border border-line bg-surface ${tone}`} aria-labelledby={`as-${id}`}>
      <h3 id={`as-${id}`} className="m-0">
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
          className="flex min-h-[56px] w-full items-center justify-between gap-3 px-4 text-left font-sans text-lg font-bold">
          <span className="flex items-center gap-2.5"><Icon className="h-5 w-5 shrink-0 text-primary" aria-hidden="true" />{title}</span>
          <ChevronDown className={`h-5 w-5 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden="true" />
        </button>
      </h3>
      {open && <div className="border-t border-line px-4 py-4">{children}</div>}
    </section>
  );
}

/** "Your assessment": symptoms checked, why this urgency, possible causes (not a diagnosis), tests, precautions,
 *  when to call 112 and the next step. Built by the backend in the user's language (debug.assessment). */
export default function AssessmentCard({ card, onGoToCaregivers }) {
  const { t } = useApp();
  if (!card) return null;
  const s = card.sections;
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="card p-5 md:p-7" aria-labelledby="assessment-title">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow mb-1">{card.pathway_label} · {card.stage} {card.stage_label}</p>
          <h2 id="assessment-title" className="text-2xl font-semibold md:text-3xl">{card.title}</h2>
        </div>
        <span className="chip font-semibold"><ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />{t("assessment.notDiagnosis")}</span>
      </div>

      <div className="space-y-3">
        <Section id="symptoms" icon={ListChecks} title={s.symptoms.title} open>
          <ul className="grid gap-2 sm:grid-cols-2">
            {s.symptoms.items.map((it) => {
              const st = STATUS[it.status] || STATUS.not_asked;
              return (
                <li key={it.id} className="flex items-center gap-2.5">
                  <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${st.cls}`} aria-hidden="true"><st.Icon className="h-4 w-4" /></span>
                  <span className="min-w-0"><span className="font-semibold">{it.label}</span>
                    <span className="text-sm text-muted"> · {it.value || t(`assessment.status.${st.key}`)}</span></span>
                </li>
              );
            })}
          </ul>
        </Section>

        <Section id="why" icon={ClipboardCheck} title={s.why.title} open>
          {s.why.signs.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">{s.why.signs.map((x) => <span key={x} className="chip bg-sameday-soft font-semibold">{x}</span>)}</div>
          )}
          <p className="leading-relaxed">{s.why.text}</p>
          {s.why.contradictions.map((c) => <p key={c} className="mt-2 text-sm font-semibold text-[rgb(110_64_0)]">{c}</p>)}
        </Section>

        {s.causes.shown && s.causes.items.length > 0 && (
          <Section id="causes" icon={Lightbulb} title={s.causes.title}>
            <ul className="space-y-3">
              {s.causes.items.map((c) => (
                <li key={c.id} className="rounded-xl border border-line p-3">
                  <p className="flex flex-wrap items-center gap-2 font-bold">{c.label}
                    <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${STRENGTH[c.strength]}`}>{t(`assessment.strength.${c.strength}`)}</span></p>
                  {c.matched.length > 0 && <p className="mt-1 text-sm"><span className="font-semibold">{t("assessment.matched")}:</span> {c.matched.join(", ")}</p>}
                  {c.missing.length > 0 && <p className="text-sm text-muted"><span className="font-semibold">{t("assessment.missing")}:</span> {c.missing.join(", ")}</p>}
                </li>
              ))}
            </ul>
            {s.causes.notes.map((n) => <p key={n} className="mt-3 text-sm font-semibold">{n}</p>)}
            <p className="mt-3 font-bold">{s.causes.note}</p>
          </Section>
        )}

        {s.tests.items.length > 0 && (
          <Section id="tests" icon={FlaskConical} title={s.tests.title}>
            <p className="mb-2 text-muted">{s.tests.lead}</p>
            <ul className="list-disc space-y-1 pl-6">{s.tests.items.map((x) => <li key={x.id}>{x.label}</li>)}</ul>
            {s.tests.home_sample_note && (
              <div className="mt-3 flex flex-wrap items-center gap-3 rounded-xl bg-primary-soft/50 px-3 py-2">
                <p className="font-semibold">{s.tests.home_sample_note}</p>
                {onGoToCaregivers && <button type="button" onClick={onGoToCaregivers} className="btn-ghost min-h-[44px] px-3 text-sm">{t("assessment.seeCaregivers")}</button>}
              </div>
            )}
          </Section>
        )}

        <Section id="precautions" icon={ShieldCheck} title={s.precautions.title}>
          <ul className="space-y-2">
            {s.precautions.items.map((p, i) => (
              <li key={p} className={`flex gap-2.5 ${i === s.precautions.items.length - 1 ? "font-bold" : ""}`}>
                <Check className="mt-0.5 h-5 w-5 shrink-0 text-routine" aria-hidden="true" />{p}
              </li>
            ))}
          </ul>
        </Section>

        <Section id="call112" icon={AlertTriangle} title={s.call_112.title} open tone="border-emergency/40">
          <ul className="space-y-2">
            {s.call_112.items.map((x) => <li key={x} className="flex gap-2.5"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-emergency" aria-hidden="true" />{x}</li>)}
          </ul>
          <a href="tel:112" className="btn-primary mt-4 inline-flex min-h-[52px] bg-emergency px-5 hover:bg-emergency-deep">
            <Phone className="h-5 w-5" aria-hidden="true" />{t("assessment.tapToCall112")}
          </a>
        </Section>
      </div>
    </motion.div>
  );
}
