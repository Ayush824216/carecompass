import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight, CheckCircle2, ChevronDown, Circle, ClipboardList, Cpu, Gauge, HelpCircle, Languages, MessageCircleQuestion,
  MapPin, ShieldAlert, ShieldCheck, Stethoscope, UserCheck,
} from "lucide-react";
import { useApp } from "../../context/AppContext.jsx";
import { SEVERITY_STAGES, URGENCY_ORDER, URGENCY_STYLE, flagLabel } from "../../lib/care.js";
import { Spinner } from "../ui.jsx";

const STAGES = [
  ["language", Languages], ["symptoms", ClipboardList], ["safety", ShieldCheck],
  ["followup", MessageCircleQuestion], ["severity", Gauge], ["triage", Stethoscope], ["matching", UserCheck],
];
const STAGE_URGENCY = { S0: "routine", S1: "same_day", S2: "same_day", S3: "immediate" };

export function modelKey(name = "") {
  if (!name) return "default";
  if (name === "rules") return "rules";
  if (name.includes("llm")) return "llm";
  if (name.startsWith("tfidf")) return "tfidf_lr";
  if (name.includes("muril") || name.includes("transformer") || name.includes("ensemble")) return "transformer";
  return "default";
}

function matchSummary(response, dbg, t) {
  const n = response.matched_caregivers.length;
  const best = dbg.matching?.[0];
  const f = dbg.matching_filters || {};
  if (!best) return t("panel.matched", { n });
  if (response.care_type === "gp_teleconsult") return t("panel.matchedTele", { n, name: best.name });
  const dist = best.distance_km != null ? best.distance_km.toFixed(1) : "—";
  return f.radius_km
    ? t("panel.matchedWithin", { n, km: f.radius_km, name: best.name, dist })
    : t("panel.matchedAll", { n, name: best.name, dist });
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
  if (dbg.domain_class && dbg.domain_class !== "health_request") {
    const skip = { status: "skipped", value: t("guard.stageSkipped") };
    return { ...out, notHealth: dbg.domain_class, symptoms: skip, safety: { status: "done", value: t("panel.noRedFlags") },
      followup: skip, severity: skip, triage: skip, matching: skip };
  }
  out.symptoms = {
    status: "done",
    value: syms.length ? [syms.map((x) => { const v = t(`symptoms.${x}`); return v.startsWith("symptoms.") ? x : v; }).join(", "), slots.duration_text].filter(Boolean).join(" · ") : t("panel.noSymptoms"),
  };
  out.safety = flags.length
    ? { status: "alert", value: t("panel.redFlags", { flags: flags.map((f) => flagLabel(f, t, dbg)).join(", ") }) }
    : emergency ? { status: "alert", value: t("panel.redFlags", { flags: "—" }) }
    : { status: "done", value: t("panel.noRedFlags") };
  out.followup = emergency ? { status: "skipped", value: t("panel.followupSkipped") }
    : followup ? { status: "question", value: t("panel.followupYes") } : { status: "done", value: t("panel.followupNo") };
  const prim = dbg.pathways?.primary;
  // e.g. "Fever pathway · S2 · platelets 80,000 + abdominal pain"
  out.severity = prim
    ? { status: prim.stage === "S3" ? "alert" : followup ? "question" : "done",
      value: followup && prim.stage !== "S3" ? t("panel.severityAssessing", { pathway: t(`pathways.${prim.pathway}`) })
        : [t("panel.severityLine", { pathway: t(`pathways.${prim.pathway}`), stage: prim.stage }),
          (dbg.pathways.moved_by || []).join(" + ")].filter(Boolean).join(" · ") }
    : { status: emergency && flags.length ? "skipped" : "done", value: t("panel.severityNone") };
  out.triage = followup ? { status: "pending", value: "" }
    : { status: emergency ? "alert" : "done", value: `${t(`careTypes.${response.care_type}.name`)} · ${t(`urgency.${response.urgency}.label`)}` };
  out.matching = emergency ? { status: "skipped", value: t("panel.matchSkipped") }
    : followup ? { status: "pending", value: "" } : { status: "done", value: matchSummary(response, dbg, t) };
  return out;
}

function StatusIcon({ status, running }) {
  if (running) return <Spinner className="h-5 w-5 text-primary" />;
  if (status === "done") return <CheckCircle2 className="h-5 w-5 text-primary" aria-hidden="true" />;
  if (status === "alert") return <ShieldAlert className="h-5 w-5 text-emergency" aria-hidden="true" />;
  if (status === "question") return <HelpCircle className="h-5 w-5 text-sameday" aria-hidden="true" />;
  return <Circle className="h-5 w-5 text-line" aria-hidden="true" />;
}

function SeverityLadder({ stage, t }) {
  const active = SEVERITY_STAGES.indexOf(stage);
  return (
    <div>
      <p className="eyebrow mb-2">{t("panel.severityLadder")}</p>
      <ol className="grid grid-cols-4 gap-1.5" aria-label={`${t("panel.severityLadder")}: ${stage} ${t(`severity.${stage}.name`)}`}>
        {SEVERITY_STAGES.map((st, i) => {
          const on = i === active;
          return (
            <li key={st} aria-current={on ? "step" : undefined}
              className={`flex min-h-[64px] flex-col items-center justify-center rounded-xl border px-1 text-center transition-all ${on ? `${URGENCY_STYLE[STAGE_URGENCY[st]].chip} border-2 shadow-card` : i < active ? "border-line bg-sunken text-muted" : "border-line bg-sunken/60 text-muted/70"}`}>
              <span className="font-mono text-sm font-bold">{st}</span>
              <span className="text-xs font-semibold leading-tight">{t(`severity.${st}.name`)}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
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

export default function DecisionPanel({ phase, response, debug, ms, locationText }) {
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
  const notHealth = stages?.notHealth;
  const why = notHealth ? t("guard.notHealthHint")
    : response?.follow_up_question ? t("panel.whyFollowup", { q: response.follow_up_question })
    : response?.reasoning;

  return (
    <aside className={`card flex flex-col gap-6 p-5 transition-colors lg:sticky lg:top-[92px] ${phase === "done" && response?.care_type === "emergency_referral" ? "border-2 border-emergency bg-emergency-soft/40" : ""}`} aria-labelledby="panel-title">
      <div>
        <h2 id="panel-title" className="text-2xl font-semibold">{t("panel.title")}</h2>
        <p className="text-sm text-muted">{t("panel.subtitle")}</p>
        {locationText && (
          <p className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-sunken px-2.5 py-1 text-sm font-semibold">
            <MapPin className="h-4 w-4 text-primary" aria-hidden="true" />{t("panel.locationLine")}: {locationText}
          </p>
        )}
      </div>

      <ol className="relative space-y-1">
        {STAGES.map(([key, Icon], i) => {
          const st = stages?.[key];
          const shown = phase === "done" && i < revealed;
          const running = phase === "loading" && i === 0;
          const status = shown ? st?.status : "idle";
          const tone = status === "alert" ? "border-emergency/40 bg-emergency-soft/70"
            : status === "question" ? "border-sameday/40 bg-sameday-soft/60"
            : shown && status === "done" ? "border-primary/20 bg-primary-soft/30" : "border-transparent";
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

      {notHealth && phase === "done" && (
        <div className="rounded-xl2 border-2 border-dashed border-line bg-sunken/60 px-4 py-4" role="status">
          <p className="flex items-center gap-2 font-bold"><MessageCircleQuestion className="h-5 w-5 text-muted" aria-hidden="true" />{t("guard.notHealth")}</p>
          <p className="mt-1 text-sm text-muted">{t(`guard.classes.${notHealth}`)}</p>
        </div>
      )}

      {terms.length > 0 && phase === "done" && !notHealth && (
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

      {phase === "done" && debug?.pathways?.primary && !notHealth && !response?.follow_up_question && <SeverityLadder stage={debug.pathways.primary.stage} t={t} />}

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
            {debug.pathways?.concern_patterns_internal?.length > 0 && (
              <div className="rounded-lg border border-dashed border-line bg-surface px-3 py-2">
                <p className="eyebrow mb-1">{t("panel.internalPattern")}</p>
                <p className="flex flex-wrap gap-1.5">
                  {debug.pathways.concern_patterns_internal.map((c) => <span key={c} className="chip font-mono text-xs">{c}</span>)}
                </p>
                <p className="mt-1 text-xs text-muted">{t("panel.internalPatternNote")}</p>
              </div>
            )}
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
