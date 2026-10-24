import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Mic, MicOff, RotateCcw, SendHorizontal } from "lucide-react";
import { useApp } from "../../context/AppContext.jsx";
import { canListen, listen, stopSpeaking } from "../../lib/speech.js";
import { CARE_EXAMPLES } from "../../lib/examples.js";
import { Logo } from "../Layout.jsx";

function time(ts, lang) {
  return new Date(ts).toLocaleTimeString(lang === "hi" ? "hi-IN" : "en-IN", { hour: "numeric", minute: "2-digit" });
}

function Bubble({ m, lang, t }) {
  const user = m.role === "user";
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}
      className={`flex gap-3 ${user ? "flex-row-reverse" : ""}`}>
      {!user && <Logo className="mt-1 h-8 w-8 shrink-0" />}
      <div className={`flex max-w-[85%] flex-col ${user ? "items-end" : "items-start"}`}>
        <div className={`rounded-2xl px-4 py-3 text-[1.02rem] leading-relaxed ${user
          ? "rounded-tr-md bg-primary text-primary-ink"
          : m.kind === "question" ? "rounded-tl-md border-2 border-accent/60 bg-accent-soft/60 font-semibold"
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
      <Logo className="h-8 w-8 shrink-0" />
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

export default function ChatPanel({ messages, loading, onSend, quickReplies, questionNo, maxQuestions, onReset, disabled, quickTitle, emptyLine }) {
  const { t, lang } = useApp();
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
    <section className="card flex flex-col overflow-hidden" aria-label={t("care.title")}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5" aria-hidden="true">
            <span className="absolute inline-flex h-full w-full rounded-full bg-routine opacity-60 motion-safe:animate-ping" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-routine" />
          </span>
          <span className="font-semibold">{t("common.assistant")}</span>
        </div>
        <div className="flex items-center gap-2">
          {questionNo > 0 && (
            <span className="chip border-accent/50 bg-accent-soft font-semibold">{t("care.questionOf", { n: questionNo, max: maxQuestions })}</span>
          )}
          {started && (
            <button type="button" onClick={onReset} className="btn-ghost min-h-[44px] px-3 text-sm">
              <RotateCcw className="h-4 w-4" aria-hidden="true" />{t("common.startOver")}
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
          {quickReplies?.length > 0 && !loading && (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
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
