import { useMemo, useState } from "react";
import { Check, Copy, ExternalLink, Play, Timer } from "lucide-react";
import PageHeader from "../components/PageHeader.jsx";
import { ErrorState, Spinner } from "../components/ui.jsx";
import { useApp } from "../context/AppContext.jsx";
import { API_BASE, api } from "../lib/api.js";
import { DEV_PRESETS } from "../lib/examples.js";

const TOKEN = /("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(?:\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;

function Json({ value }) {
  const text = useMemo(() => (value == null ? "" : JSON.stringify(value, null, 2)), [value]);
  const parts = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN)) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    const cls = tok.startsWith('"') ? (tok.endsWith(":") ? "text-[#7dd3c0]" : "text-[#f5c98a]")
      : /true|false/.test(tok) ? "text-[#f4a8b0]" : tok === "null" ? "text-white/50" : "text-[#a5c8ff]";
    parts.push(<span key={m.index} className={cls}>{tok}</span>);
    last = m.index + tok.length;
  }
  parts.push(text.slice(last));
  return <code>{parts}</code>;
}

function CopyButton({ text, label }) {
  const { t } = useApp();
  const [ok, setOk] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); } catch {
      const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); } catch { /* ignore */ } ta.remove();
    }
    setOk(true); setTimeout(() => setOk(false), 1600);
  };
  return (
    <button type="button" onClick={copy} aria-label={`${t("common.copy")} ${label || ""}`}
      className="inline-flex min-h-[40px] items-center gap-1.5 rounded-lg border border-white/20 px-3 text-sm font-semibold text-white hover:bg-white/10">
      {ok ? <Check className="h-4 w-4" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
      {ok ? t("common.copied") : t("common.copy")}
    </button>
  );
}

function CodePanel({ title, children, copyText, extra }) {
  return (
    <div className="flex min-w-0 flex-col overflow-hidden rounded-xl2 bg-[#0f1f1c] text-white shadow-card">
      <div className="flex items-center justify-between gap-2 border-b border-white/10 px-4 py-2">
        <span className="font-mono text-sm font-semibold text-white/80">{title}</span>
        <div className="flex items-center gap-2">{extra}{copyText && <CopyButton text={copyText} label={title} />}</div>
      </div>
      <pre className="max-h-[560px] min-h-[160px] flex-1 overflow-auto whitespace-pre-wrap p-4 font-mono text-[0.8rem] leading-relaxed [overflow-wrap:anywhere]">{children}</pre>
    </div>
  );
}

export default function Developers() {
  const { t } = useApp();
  const [input, setInput] = useState(DEV_PRESETS[0].user_input);
  const [language, setLanguage] = useState("auto");
  const [lat, setLat] = useState("28.54");
  const [lng, setLng] = useState("77.27");
  const [debug, setDebug] = useState(false);
  const [resp, setResp] = useState(null);
  const [ms, setMs] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [active, setActive] = useState("hinglish");

  const body = useMemo(() => ({
    user_input: input, language,
    location: { lat: Number(lat) || 0, lng: Number(lng) || 0 },
    conversation_history: [],
  }), [input, language, lat, lng]);
  const shownReq = debug ? { ...body, debug: true } : body;

  async function send(e) {
    e?.preventDefault();
    setBusy(true); setError("");
    try {
      const { data, ms: took } = await api.triage(body, { debug });
      setResp(data); setMs(took);
    } catch {
      setError(t("common.serverDown")); setResp(null);
    } finally {
      setBusy(false);
    }
  }

  const curlTriage = `curl -s -X POST ${API_BASE}/api/v1/triage \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify(body)}'`;
  const curlBook = `curl -s -X POST ${API_BASE}/api/v1/book \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify({ caregiver_id: resp?.matched_caregivers?.[0]?.caregiver_id || "CG_011", care_type: resp?.care_type || "paramedic_home_visit", urgency: resp?.urgency || "same_day" })}'`;

  return (
    <>
      <PageHeader title={t("dev.title")} subtitle={t("dev.subtitle")}>
        <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer" className="btn-ghost mt-6">
          <ExternalLink className="h-4 w-4" aria-hidden="true" />{t("dev.swagger")}
        </a>
      </PageHeader>
      <div className="container-page space-y-10 py-10">
        <section aria-labelledby="presets-h">
          <h2 id="presets-h" className="eyebrow mb-3 font-sans">{t("dev.presets")}</h2>
          <div className="flex flex-wrap gap-2">
            {DEV_PRESETS.map((p) => (
              <button key={p.key} type="button" aria-pressed={active === p.key}
                onClick={() => { setActive(p.key); setInput(p.user_input); setLanguage(p.language); }}
                className={`chip min-h-[44px] px-4 font-semibold ${active === p.key ? "border-primary bg-primary text-primary-ink" : "hover:border-primary"} ${p.key === "emergency" && active !== p.key ? "text-emergency" : ""}`}>
                {t(`dev.presetNames.${p.key}`)}
              </button>
            ))}
          </div>
        </section>

        <form onSubmit={send} className="card grid gap-4 p-5 md:grid-cols-[1fr_auto] md:items-end">
          <div className="grid gap-4 md:grid-cols-[2fr_1fr_1fr_1fr]">
            <div className="md:col-span-4">
              <label htmlFor="dev-input" className="mb-1.5 block font-mono text-sm font-semibold">{t("dev.input")}</label>
              <textarea id="dev-input" rows={2} value={input} onChange={(e) => { setInput(e.target.value); setActive(""); }} className="input py-3" />
            </div>
            <div>
              <label htmlFor="dev-lang" className="mb-1.5 block font-mono text-sm font-semibold">{t("dev.language")}</label>
              <select id="dev-lang" value={language} onChange={(e) => setLanguage(e.target.value)} className="input">
                {["auto", "en", "hi", "hinglish"].map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="dev-lat" className="mb-1.5 block font-mono text-sm font-semibold">{t("dev.lat")}</label>
              <input id="dev-lat" value={lat} onChange={(e) => setLat(e.target.value)} inputMode="decimal" className="input" />
            </div>
            <div>
              <label htmlFor="dev-lng" className="mb-1.5 block font-mono text-sm font-semibold">{t("dev.lng")}</label>
              <input id="dev-lng" value={lng} onChange={(e) => setLng(e.target.value)} inputMode="decimal" className="input" />
            </div>
            <label className="flex min-h-[48px] cursor-pointer items-center gap-3 self-end rounded-xl border border-line px-4">
              <input type="checkbox" checked={debug} onChange={(e) => setDebug(e.target.checked)} className="h-5 w-5 accent-[rgb(var(--primary))]" />
              <span className="font-semibold">{t("dev.debug")}</span>
            </label>
          </div>
          <button type="submit" className="btn-primary min-h-[56px] px-7 text-lg" disabled={busy || !input.trim()}>
            {busy ? <Spinner className="h-5 w-5" /> : <Play className="h-5 w-5" aria-hidden="true" />}{t("dev.send")}
          </button>
        </form>

        {error && <ErrorState message={error} onRetry={send} />}

        <div className="grid gap-5 lg:grid-cols-2">
          <CodePanel title={`POST /api/v1/triage${debug ? "?debug=true" : ""} · ${t("dev.request")}`} copyText={JSON.stringify(shownReq, null, 2)}>
            <Json value={shownReq} />
          </CodePanel>
          <CodePanel title={t("dev.response")} copyText={resp ? JSON.stringify(resp, null, 2) : ""}
            extra={ms != null && resp && (
              <span className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-2.5 py-1 font-mono text-xs font-semibold">
                <Timer className="h-3.5 w-3.5" aria-hidden="true" />{t("dev.time")}: {ms} ms
              </span>)}>
            {resp ? <Json value={resp} /> : <span className="text-white/50">{t("dev.noResponse")}</span>}
          </CodePanel>
        </div>

        <section aria-labelledby="curl-h" className="space-y-4">
          <h2 id="curl-h" className="text-2xl font-semibold">{t("dev.curl")}</h2>
          <div className="grid gap-5 lg:grid-cols-2">
            <CodePanel title="POST /api/v1/triage" copyText={curlTriage}><code>{curlTriage}</code></CodePanel>
            <CodePanel title="POST /api/v1/book" copyText={curlBook}><code>{curlBook}</code></CodePanel>
          </div>
        </section>
      </div>
    </>
  );
}
