import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, MapPin, Mic, MicOff, SendHorizontal, Trash2 } from "lucide-react";
import { useApp } from "../../context/AppContext.jsx";
import { canListen, listen, stopSpeaking } from "../../lib/speech.js";
import { CARE_EXAMPLES } from "../../lib/examples.js";
import { BrandAvatar } from "../Layout.jsx";

function time(ts, lang) {
  return new Date(ts).toLocaleTimeString(lang === "hi" ? "hi-IN" : "en-IN", { hour: "numeric", minute: "2-digit" });
}

function Bubble({ m, lang, t }) {
  const user = m.role === "user";
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}
      className={`flex gap-3 ${user ? "flex-row-reverse" : ""}`}>
      {!user && <BrandAvatar className="mt-1 h-9 w-9" />}
      <div className={`flex max-w-[85%] flex-col ${user ? "items-end" : "items-start"}`}>
        <div className={`rounded-2xl px-4 py-3 text-[1.02rem] leading-relaxed ${user
          ? "rounded-tr-md bg-primary text-primary-ink"
          : m.kind === "question" ? "rounded-tl-md border-2 border-primary/40 bg-primary-soft/50 font-semibold"
          : m.kind === "redirect" ? "rounded-tl-md border border-dashed border-primary/50 bg-primary-soft/40" : "rounded-tl-md border border-line bg-surface"}`}>
          {m.content}
        </div>
        <span className="mt-1 px-1 text-xs text-muted">{user ? t("common.you") : t("common.assistant")} · {time(m.ts, lang)}</span>
      </div>
    </motion.div>
  );
}

function Typing({ t }) {
  return (
    <div className="flex items-center gap-3" role="status" aria-label={t("care.typing")}>
      <BrandAvatar className="h-9 w-9" />
      <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-md border border-line bg-surface px-4 py-3.5">
        {[0, 1, 2].map((i) => (
          <motion.span key={i} className="h-2 w-2 rounded-full bg-muted" animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 1, repeat: Infinity, delay: i * 0.18 }} />
        ))}
        <span className="sr-only">{t("care.typing")}</span>
      </div>
    </div>
  );
}

/** Multi-select answer chips for a pathway question. "None" is exclusive and sends straight away. */
function MultiChoice({ options, onSend, t, single }) {
  const [picked, setPicked] = useState([]);
  const toggle = (o) => {
    if (o.exclusive || single) { onSend(o.label); return; }
    setPicked((p) => (p.includes(o.id) ? p.filter((x) => x !== o.id) : [...p, o.id]));
  };
  const send = () => onSend(options.filter((o) => picked.includes(o.id)).map((o) => o.label).join(", "));
  return (
    <div role="group" aria-label={t("care.chooseAll")}>
      <p className="mb-2 text-sm font-semibold text-muted">{single ? t("care.chooseOne") : t("care.chooseAll")}</p>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => {
          const on = picked.includes(o.id);
          return (
            <button key={o.id} type="button" onClick={() => toggle(o)} aria-pressed={o.exclusive ? undefined : on}
              className={`inline-flex min-h-[52px] items-center gap-2 rounded-xl border-2 px-4 text-lg font-bold transition-colors ${o.exclusive
                ? "border-line bg-sunken text-ink hover:border-primary"
                : on ? "border-primary bg-primary text-primary-ink" : "border-primary bg-surface text-primary-deep hover:bg-primary-soft"}`}>
              {!o.exclusive && !single && <span className={`flex h-5 w-5 items-center justify-center rounded border-2 ${on ? "border-white bg-white/20" : "border-primary"}`} aria-hidden="true">
                {on && <Check className="h-4 w-4" />}
              </span>}
              {o.label}
            </button>
          );
        })}
      </div>
      {picked.length > 0 && (
        <button type="button" onClick={send} className="btn-primary mt-3 min-h-[52px] px-6 text-lg">
          <SendHorizontal className="h-5 w-5" aria-hidden="true" />{t("care.sendSelected", { n: picked.length })}
        </button>
      )}
    </div>
  );
}

export default function ChatPanel({ messages, loading, onSend, quickReplies, choices, questionNo, maxQuestions, onReset, disabled, quickTitle, emptyLine, locationText }) {
  const { t, lang, incognito } = useApp();
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [micError, setMicError] = useState("");
  const recRef = useRef(null);
  const threadRef = useRef(null);

  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);
  useEffect(() => () => recRef.current?.abort?.(), []);

  const submit = (value) => {
    const v = (value ?? text).trim();
    if (!v || loading || disabled) return;
    setText("");
    onSend(v);
  };

  const toggleMic = () => {
    if (listening) { recRef.current?.stop(); return; }
    if (!canListen) { setMicError(t("care.micUnsupported")); return; }
    setMicError("");
    stopSpeaking();
    let finalText = "";
    setListening(true);
    recRef.current = listen({
      lang: lang === "hi" ? "hi-IN" : "en-IN",
      onText: (txt, isFinal) => { setText(txt); if (isFinal) finalText = txt; },
      onEnd: () => { setListening(false); if (finalText) submit(finalText); },
      onError: () => setListening(false),
    });
  };

  const started = messages.some((m) => m.role === "user");

  return (
    <section className={`card flex flex-col overflow-hidden ${incognito ? "incognito-chat" : ""}`} aria-label={t("care.title")} data-incognito={incognito || undefined}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <BrandAvatar className="h-9 w-9" />
          <div className="min-w-0">
            <p className="font-bold leading-tight">{t("common.assistant")}</p>
            {locationText && (
              <p className="flex items-center gap-1 truncate text-xs font-semibold text-muted">
                <MapPin className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" /><span className="truncate">{locationText}</span>
              </p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {questionNo > 0 && (
            <span className="chip border-sameday/40 bg-sameday-soft font-semibold text-[rgb(110_64_0)]">{t("care.questionOf", { n: questionNo, max: maxQuestions })}</span>
          )}
          {started && (
            <button type="button" onClick={onReset} className="btn-ghost h-11 w-11 justify-center p-0" aria-label={t("privacy.clearConversation")} title={t("privacy.clearConversation")}>
              <Trash2 className="h-5 w-5" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      <div ref={threadRef} className="flex min-h-[300px] flex-1 flex-col gap-5 overflow-y-auto bg-bg/40 px-4 py-5 sm:px-5 lg:h-[440px] lg:flex-none" aria-live="polite">
        {messages.map((m) => <Bubble key={m.id} m={m} lang={lang} t={t} />)}
        {loading && <Typing t={t} />}
      </div>

      <div className="space-y-4 border-t border-line bg-surface px-4 py-4 sm:px-5">
        <AnimatePresence>
          {choices && !loading && (
            <motion.div key={choices.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <MultiChoice key={choices.id} options={choices.options} single={choices.single} onSend={(v) => submit(v)} t={t} />
            </motion.div>
          )}
          {quickReplies?.length > 0 && !loading && (
            <motion.div key="quick" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <p className="mb-2 text-sm font-semibold text-muted">{quickTitle || t("care.answerHint")}</p>
              <div className="flex flex-wrap gap-2">
                {quickReplies.map((c) => (
                  <button key={c} type="button" onClick={() => submit(c)}
                    className="min-h-[52px] rounded-xl border-2 border-primary bg-surface px-5 text-lg font-bold text-primary-deep hover:bg-primary-soft">
                    {c}
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex flex-col gap-3 md:flex-row md:items-stretch">
          <button type="button" onClick={toggleMic} disabled={disabled}
            aria-label={listening ? t("care.micStopAria") : t("care.micAria")} aria-pressed={listening}
            className={`relative flex min-h-[64px] items-center justify-center gap-3 rounded-2xl px-6 text-lg font-bold text-white transition-colors md:w-[230px] md:shrink-0 ${listening ? "bg-accent" : "bg-primary hover:bg-primary-deep"}`}>
            {listening && <span className="absolute inset-0 rounded-2xl ring-4 ring-accent/40 motion-safe:animate-pulse" aria-hidden="true" />}
            {listening ? <MicOff className="h-6 w-6" aria-hidden="true" /> : <Mic className="h-6 w-6" aria-hidden="true" />}
            <span>{listening ? t("care.micListening") : t("care.micIdle")}</span>
          </button>
          <form className="flex min-w-0 flex-1 gap-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <label htmlFor="care-input" className="sr-only">{t("care.placeholder")}</label>
            <input id="care-input" value={text} onChange={(e) => setText(e.target.value)} placeholder={t("care.placeholder")}
              className={`input min-h-[64px] min-w-0 text-lg ${listening ? "border-accent bg-accent-soft/40" : ""}`} autoComplete="off" />
            <button type="submit" disabled={!text.trim() || loading || disabled} className="btn-primary min-h-[64px] shrink-0 px-5" aria-label={t("common.send")}>
              <SendHorizontal className="h-5 w-5" aria-hidden="true" /><span className="hidden xl:inline">{t("common.send")}</span>
            </button>
          </form>
        </div>
        {micError && <p className="text-sm font-semibold text-emergency" role="alert">{micError}</p>}

        {emptyLine && <p className="font-semibold text-ink/80">{emptyLine}</p>}
        {!started && (
          <div>
            <p className="eyebrow mb-2">{t("care.examples")}</p>
            <div className="flex flex-wrap gap-2">
              {CARE_EXAMPLES.map((e) => (
                <button key={e.key} type="button" onClick={() => submit(e.text)} title={e.text}
                  className={`chip min-h-[44px] px-4 font-semibold hover:border-primary hover:text-primary-deep ${e.key === "emergency" ? "border-emergency/40 text-emergency" : ""}`}>
                  {t(`care.exampleLabels.${e.key}`)}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
