import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Database, EyeOff, ShieldCheck } from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { addAssessment, loadMemory, saveItems } from "../lib/memory.js";

/** The one Incognito switch (navbar). Turning it off ends the session: the conversation in memory is wiped. */
export function IncognitoToggle() {
  const { t, incognito, toggleIncognito } = useApp();
  return (
    <button type="button" onClick={toggleIncognito} aria-pressed={incognito} title={incognito ? t("privacy.incognitoOffHint") : t("privacy.incognitoOnHint")}
      className={`btn-ghost min-h-[44px] px-3 text-sm font-semibold ${incognito ? "bg-ink text-bg" : ""}`}>
      <EyeOff className="h-4 w-4" aria-hidden="true" />{t("privacy.incognito")}
    </button>
  );
}

export function IncognitoBadge() {
  const { t, incognito } = useApp();
  if (!incognito) return null;
  return (
    <p role="status" className="chip inline-flex items-center gap-2 bg-ink font-semibold text-bg">
      <EyeOff className="h-4 w-4" aria-hidden="true" />{t("privacy.incognitoBadge")}
    </p>
  );
}

/** First use: what is processed, what is saved (this device only), not a diagnosis, how to use Incognito. */
export function ConsentNotice() {
  const { t, consent, giveConsent, incognito } = useApp();
  if (consent || incognito) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 p-4 sm:items-center" role="dialog" aria-modal="true" aria-labelledby="consent-title">
      <div className="card max-h-[90vh] w-full max-w-lg overflow-y-auto p-6">
        <h2 id="consent-title" className="flex items-center gap-2 text-2xl font-semibold"><ShieldCheck className="h-6 w-6 text-primary" aria-hidden="true" />{t("privacy.consentTitle")}</h2>
        <ul className="mt-4 list-disc space-y-2 pl-5">
          {t("privacy.consentPoints").split("|").map((p) => <li key={p}>{p}</li>)}
        </ul>
        <div className="mt-6 flex flex-wrap gap-3">
          <button type="button" className="btn-primary min-h-[48px]" onClick={() => giveConsent("memory")}>{t("privacy.consentOk")}</button>
          <button type="button" className="btn-ghost min-h-[48px]" onClick={() => giveConsent("incognito")}>
            <EyeOff className="h-4 w-4" aria-hidden="true" />{t("privacy.consentIncognito")}</button>
        </div>
        <p className="mt-4 text-sm text-muted"><Link to="/memory" className="underline">{t("privacy.manage")}</Link></p>
      </div>
    </div>
  );
}

/** After a decision: choose what to keep on this device. Sensitive items start unticked ("Save this"). */
export function SaveToMemory({ debug }) {
  const { t, incognito, toast } = useApp();
  const cands = debug?.memory_candidates || [];
  const summary = debug?.memory_summary;
  const already = useMemo(() => loadMemory().items, []);
  const fresh = cands.filter((c) => !(already[c.id] && already[c.id].value === c.value));
  const [picked, setPicked] = useState(() => Object.fromEntries(fresh.map((c) => [c.id, !c.sensitive])));
  const [keepSummary, setKeepSummary] = useState(() => Boolean(summary && !summary.sensitive));
  const [done, setDone] = useState(false);
  if (incognito || done || (!fresh.length && !summary)) return null;
  const onSave = () => {
    saveItems(fresh.filter((c) => picked[c.id]));
    if (summary && keepSummary) addAssessment(summary);
    setDone(true);
    toast(t("memory.saved"));
  };
  return (
    <section className="card mt-6 p-5" aria-labelledby="save-mem-title">
      <h2 id="save-mem-title" className="flex items-center gap-2 text-xl font-semibold"><Database className="h-5 w-5 text-primary" aria-hidden="true" />{t("memory.saveTitle")}</h2>
      <p className="mt-1 text-sm text-muted">{t("memory.saveHint")}</p>
      <ul className="mt-3 space-y-2">
        {fresh.map((c) => (
          <li key={c.id}>
            <label className="flex min-h-[44px] items-center gap-3">
              <input type="checkbox" className="h-5 w-5" checked={Boolean(picked[c.id])} onChange={(e) => setPicked((p) => ({ ...p, [c.id]: e.target.checked }))} />
              <span className="font-semibold">{c.label}</span>
              {c.sensitive && <span className="chip bg-sameday-soft text-xs font-bold">{t("memory.sensitive")} · {t("memory.saveThis")}</span>}
            </label>
          </li>
        ))}
        {summary && (
          <li>
            <label className="flex min-h-[44px] items-center gap-3">
              <input type="checkbox" className="h-5 w-5" checked={keepSummary} onChange={(e) => setKeepSummary(e.target.checked)} />
              <span className="font-semibold">{t("memory.summaryLine")}</span>
              {summary.sensitive && <span className="chip bg-sameday-soft text-xs font-bold">{t("memory.sensitive")} · {t("memory.saveThis")}</span>}
            </label>
          </li>
        )}
      </ul>
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" className="btn-primary min-h-[48px]" onClick={onSave}>{t("memory.saveButton")}</button>
        <button type="button" className="btn-ghost min-h-[48px]" onClick={() => setDone(true)}>{t("memory.dontSave")}</button>
      </div>
    </section>
  );
}
