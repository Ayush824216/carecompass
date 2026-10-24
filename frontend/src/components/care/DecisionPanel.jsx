import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight, CheckCircle2, ChevronDown, Circle, Cpu, HelpCircle, Languages, ListChecks, MessageCircleQuestion,
  ShieldAlert, ShieldCheck, Stethoscope, UsersRound,
} from "lucide-react";
import { useApp } from "../../context/AppContext.jsx";
import { URGENCY_ORDER, URGENCY_STYLE } from "../../lib/care.js";
import { Spinner } from "../ui.jsx";

const STAGES = [
  ["language", Languages], ["symptoms", ListChecks], ["safety", ShieldCheck],
  ["followup", MessageCircleQuestion], ["triage", Stethoscope], ["matching", UsersRound],
];

export function modelKey(name = "") {
  if (!name) return "default";
  if (name === "rules") return "rules";
  if (name.includes("llm")) return "llm";
  if (name.startsWith("tfidf")) return "tfidf_lr";
  if (name.includes("muril") || name.includes("transformer") || name.includes("ensemble")) return "transformer";
  return "default";
}

function buildStages({ response, debug, t }) {
  if (!response) return null;
  const dbg = debug || {};
  const slots = dbg.extracted_slots || {};
  const emergency = response.care_type === "emergency_referral";
  const followup = Boolean(response.follow_up_question);
  const flags = response.red_flags?.length ? response.red_flags : dbg.safety_checks?.red_flags || [];
  const syms = slots.symptoms || [];
  const out = {};
  out.language = { status: "done", value: dbg.detected_language ? t(`langNames.${dbg.detected_language}`) : "—" };
  out.symptoms = {
    status: "done",
    value: syms.length ? [syms.map((x) => { const v = t(`symptoms.${x}`); return v.startsWith("symptoms.") ? x : v; }).join(", "), slots.duration_text].filter(Boolean).join(" · ") : t("panel.noSymptoms"),
  };
  out.safety = flags.length
    ? { status: "alert", value: t("panel.redFlags", { flags: flags.map((f) => t(`flags.${f}`)).join(", ") }) }
    : emergency ? { status: "alert", value: t("panel.redFlags", { flags: "—" }) }
    : { status: "done", value: t("panel.noRedFlags") };
  out.followup = emergency ? { status: "skipped", value: t("panel.followupSkipped") }
    : followup ? { status: "question", value: t("panel.followupYes") } : { status: "done", value: t("panel.followupNo") };
  out.triage = followup ? { status: "pending", value: "" }
    : { status: emergency ? "alert" : "done", value: `${t(`careTypes.${response.care_type}.name`)} · ${t(`urgency.${response.urgency}.label`)}` };
  out.matching = emergency ? { status: "skipped", value: t("panel.matchSkipped") }
    : followup ? { status: "pending", value: "" } : { status: "done", value: t("panel.matched", { n: response.matched_caregivers.length }) };
  return out;
}

function StatusIcon({ status, running }) {
  if (running) return <Spinner className="h-5 w-5 text-primary" />;
  if (status === "done") return <CheckCircle2 className="h-5 w-5 text-routine" aria-hidden="true" />;
  if (status === "alert") return <ShieldAlert className="h-5 w-5 text-emergency" aria-hidden="true" />;
  if (status === "question") return <HelpCircle className="h-5 w-5 text-accent" aria-hidden="true" />;
  return <Circle className="h-5 w-5 text-line" aria-hidden="true" />;
}

function UrgencyMeter({ urgency, t }) {
  const active = URGENCY_ORDER.indexOf(urgency);
  return (
    <div>
      <p className="eyebrow mb-2">{t("panel.meter")}</p>
      <div className="grid grid-cols-3 gap-1.5" role="img"
        aria-label={urgency ? `${t("panel.meter")}: ${t(`urgency.${urgency}.label`)}` : t("panel.meter")}>
        {URGENCY_ORDER.map((u, i) => {
          const s = URGENCY_STYLE[u];
          const Icon = s.icon;
          const on = i === active;
          return (
            <div key={u} className={`flex min-h-[64px] flex-col items-center justify-center gap-1 rounded-xl border px-1 text-center text-sm font-bold transition-all ${on ? `${s.chip} border-2 shadow-card` : "border-line bg-sunken/60 text-muted/70"}`}>
              <Icon className="h-5 w-5" aria-hidden="true" />
              <span className="leading-tight">{t(`urgency.${u}.label`)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function DecisionPanel({ phase, response, debug, ms }) {
  const { t } = useApp();
  const [revealed, setRevealed] = useState(0);
  const stages = buildStages({ response, debug, t });

  useEffect(() => {
    if (phase !== "done") { setRevealed(0); return undefined; }
    setRevealed(0);
    let i = 0;
    const id = setInterval(() => { i += 1; setRevealed(i); if (i >= STAGES.length) clearInterval(id); }, 170);
    return () => clearInterval(id);
  }, [phase, response]);

  const terms = debug?.term_matches || [];
  const latency = debug?.per_stage_latency_ms || {};
  const maxLat = Math.max(1, ...Object.entries(latency).filter(([k]) => k !== "total").map(([, v]) => v));
  const slots = debug?.extracted_slots || {};
  const slotRows = ["duration", "age_group", "severity", "breathing", "can_travel"]
    .map((k) => [k, slots[k]]).filter(([, v]) => v !== null && v !== undefined && v !== "");
  const why = response?.follow_up_question
    ? t("panel.whyFollowup", { q: response.follow_up_question })
    : response?.reasoning;

  return (
    <aside className="card flex flex-col gap-6 p-5 lg:sticky lg:top-[92px]" aria-labelledby="panel-title">
      <div>
        <h2 id="panel-title" className="text-2xl font-semibold">{t("panel.title")}</h2>
        <p className="text-sm text-muted">{t("panel.subtitle")}</p>
      </div>

      <ol className="relative space-y-1">
        {STAGES.map(([key, Icon], i) => {
          const st = stages?.[key];
          const shown = phase === "done" && i < revealed;
          const running = phase === "loading" && i === 0;
          const status = shown ? st?.status : "idle";
          const tone = status === "alert" ? "border-emergency/40 bg-emergency-soft/60"
            : status === "question" ? "border-accent/50 bg-accent-soft/50"
            : shown && status !== "pending" && status !== "skipped" ? "border-line bg-surface" : "border-transparent";
          return (
            <li key={key} className="relative flex gap-3">
              {i < STAGES.length - 1 && <span className="absolute left-[22px] top-11 h-[calc(100%-28px)] w-px bg-line" aria-hidden="true" />}
              <span className={`z-10 mt-1.5 flex h-[30px] w-[30px] shrink-0 translate-x-[7px] items-center justify-center rounded-full bg-surface`}>
                <StatusIcon status={status} running={running} />
              </span>
              <motion.div className={`ml-2 min-w-0 flex-1 rounded-xl border px-3 py-2 ${tone}`}
                initial={false} animate={{ opacity: shown || running ? 1 : 0.55 }}>
                <div className="flex items-center gap-2 text-sm font-semibold text-muted">
                  <Icon className="h-4 w-4" aria-hidden="true" />{t(`panel.stage.${key}`)}
                </div>
                <p className="min-h-[1.5rem] break-words font-semibold">
                  {shown ? (st?.value || "…") : running ? t("panel.running") : phase === "idle" ? "" : "…"}
                </p>
              </motion.div>
            </li>
          );
        })}
      </ol>
      {phase === "idle" && <p className="-mt-3 text-center text-sm text-muted">{t("panel.idle")}</p>}

      {terms.length > 0 && phase === "done" && (
        <div>
          <p className="eyebrow mb-2">{t("panel.symptomChips")}</p>
          <div className="flex flex-wrap gap-2">
            {terms.map((m) => (
              <span key={m.source + m.canonical} className="chip bg-primary-soft/60 font-semibold">
                <span lang="hi">{m.source}</span>
                <ArrowRight className="h-3.5 w-3.5 text-muted" aria-label="means" />
                <span className="text-primary-deep">{m.canonical}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <UrgencyMeter urgency={phase === "done" ? response?.urgency : null} t={t} />

      <div className="rounded-xl border-l-4 border-primary bg-primary-soft/50 px-4 py-3">
        <p className="eyebrow mb-1 text-primary-deep">{t("panel.why")}</p>
        <p className="leading-relaxed">{phase === "done" && why ? why : <span className="text-muted">{t("panel.whyIdle")}</span>}</p>
      </div>

      {debug && phase === "done" && (
        <details className="group rounded-xl border border-line bg-sunken/40">
          <summary className="flex min-h-[48px] cursor-pointer list-none items-center justify-between gap-2 px-4 font-semibold">
            <span className="flex items-center gap-2"><Cpu className="h-4 w-4" aria-hidden="true" />{t("panel.tech")}</span>
            <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" aria-hidden="true" />
          </summary>
          <div className="space-y-4 border-t border-line px-4 py-4 text-sm">
            <div>
              <p className="eyebrow mb-1">{t("panel.model")}</p>
              <p className="font-semibold">{t(`panel.models.${modelKey(debug.model_used)}`)}</p>
              <p className="font-mono text-xs text-muted">{debug.model_used}{debug.llm && !debug.llm.available ? " · LLM not configured" : ""}</p>
            </div>
            <div>
              <p className="eyebrow mb-2">{t("panel.latency")}</p>
              <ul className="space-y-1.5">
                {Object.entries(latency).filter(([k]) => k !== "total").map(([k, v]) => (
                  <li key={k} className="grid grid-cols-[96px_1fr_64px] items-center gap-2">
                    <span className="font-mono text-xs">{k}</span>
                    <span className="h-2 rounded-full bg-primary/70" style={{ width: `${Math.max(3, (v / maxLat) * 100)}%` }} />
                    <span className="text-right font-mono text-xs">{v.toFixed(1)} ms</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 font-semibold">{t("panel.total")}: {latency.total?.toFixed?.(1)} ms{ms ? ` · ${ms} ms round trip` : ""}</p>
            </div>
            <div>
              <p className="eyebrow mb-1">{t("panel.rules")}</p>
              <p className="font-semibold">{debug.safety_checks?.categories_checked ?? "—"}</p>
            </div>
            {slotRows.length > 0 && (
              <div>
                <p className="eyebrow mb-1">{t("panel.slots")}</p>
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                  {slotRows.map(([k, v]) => (
                    <div key={k} className="contents">
                      <dt className="text-muted">{t(`panel.slotNames.${k}`)}</dt>
                      <dd className="font-semibold">{k === "duration" && slots.duration_text ? slots.duration_text : t(`panel.values.${String(v)}`)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
            <div>
              <p className="eyebrow mb-1">{t("panel.normalised")}</p>
              <p className="break-words rounded-lg bg-surface px-3 py-2 font-mono text-xs">{debug.normalised_text}</p>
            </div>
          </div>
        </details>
      )}
    </aside>
  );
}
