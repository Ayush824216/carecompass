import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useApp } from "../context/AppContext.jsx";
import { api } from "../lib/api.js";
import { speak, stopSpeaking } from "../lib/speech.js";
import ChatPanel from "../components/care/ChatPanel.jsx";
import DecisionPanel from "../components/care/DecisionPanel.jsx";
import ResultSection from "../components/care/ResultSection.jsx";
import EmergencyView from "../components/care/EmergencyView.jsx";
import { ErrorState } from "../components/ui.jsx";
import { ShieldAlert } from "lucide-react";

const MAX_Q = 4;
let uid = 0;
const nextId = () => `m${++uid}`;

function quickRepliesFor(question, bank) {
  if (!question || !bank) return [];
  for (const q of Object.values(bank)) {
    for (const l of ["en", "hi", "hinglish"]) if (q[l] === question) return q.options.map((o) => o[l]);
  }
  return [];
}

export default function GetCare() {
  const { t, lang, voice, location } = useApp();
  const welcome = useCallback(() => [{ id: nextId(), role: "assistant", content: t("care.welcome"), ts: Date.now() }], [t]);
  const [messages, setMessages] = useState(welcome);
  const [history, setHistory] = useState([]);
  const [phase, setPhase] = useState("idle"); // idle | loading | done
  const [response, setResponse] = useState(null);
  const [debug, setDebug] = useState(null);
  const [ms, setMs] = useState(0);
  const [error, setError] = useState("");
  const [bank, setBank] = useState(null);
  const [emOpen, setEmOpen] = useState(false);
  const lastInput = useRef(null);

  useEffect(() => { api.questions().then(setBank).catch(() => {}); }, []);
  // keep the welcome bubble in the current UI language until the user starts
  useEffect(() => { setMessages((m) => (m.length === 1 && m[0].role === "assistant" ? welcome() : m)); }, [lang, welcome]);
  useEffect(() => () => stopSpeaking(), []);

  const send = useCallback(async (text, hist = history) => {
    lastInput.current = { text, hist };
    setError("");
    setMessages((m) => [...m, { id: nextId(), role: "user", content: text, ts: Date.now() }]);
    setPhase("loading");
    try {
      const { data, ms: took } = await api.triage(
        { user_input: text, language: "auto", location: { lat: location.lat, lng: location.lng }, conversation_history: hist },
        { debug: true });
      const { debug: dbg, ...official } = data;
      setResponse(official); setDebug(dbg || null); setMs(took); setPhase("done");
      setEmOpen(official.care_type === "emergency_referral");
      const newHist = [...hist, { role: "user", content: text }];
      if (official.follow_up_question) {
        setMessages((m) => [...m, { id: nextId(), role: "assistant", kind: "question", content: official.follow_up_question, ts: Date.now() }]);
        setHistory([...newHist, { role: "assistant", content: official.follow_up_question }]);
        speak(official.follow_up_question, voice);
      } else {
        setHistory(newHist);
        setMessages((m) => [...m, { id: nextId(), role: "assistant", content: official.reasoning, ts: Date.now() }]);
        speak(official.reasoning, voice);
      }
    } catch (e) {
      setPhase(response ? "done" : "idle");
      setError(t("common.serverDown"));
      setMessages((m) => m.slice(0, -1));
    }
  }, [history, location, voice, t, response]);

  const reset = () => {
    stopSpeaking();
    setMessages(welcome()); setHistory([]); setPhase("idle"); setResponse(null); setDebug(null); setError(""); setEmOpen(false);
  };

  const questionNo = useMemo(() => history.filter((h) => h.role === "assistant").length, [history]);
  const final = phase === "done" && response && !response.follow_up_question;
  const emergency = response?.care_type === "emergency_referral";
  const quick = response?.follow_up_question && phase === "done" ? quickRepliesFor(response.follow_up_question, bank) : [];

  return (
    <div className="container-page py-8 md:py-10">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold md:text-4xl">{t("care.title")}</h1>
        <p className="mt-1 text-lg text-muted">{t("care.subtitle")}</p>
      </div>
      {error && (
        <div className="mb-5">
          <ErrorState message={error} onRetry={lastInput.current ? () => send(lastInput.current.text, lastInput.current.hist) : undefined} />
        </div>
      )}
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <ChatPanel messages={messages} loading={phase === "loading"} onSend={(v) => send(v)} quickReplies={quick}
          questionNo={response?.follow_up_question ? questionNo : 0} maxQuestions={MAX_Q} onReset={reset} />
        <DecisionPanel phase={phase} response={response} debug={debug} ms={ms} />
      </div>
      {final && emergency && !emOpen && (
        <button type="button" onClick={() => setEmOpen(true)}
          className="mt-8 flex w-full items-center gap-4 rounded-xl2 bg-emergency p-5 text-left text-white shadow-lift">
          <ShieldAlert className="h-8 w-8 shrink-0" aria-hidden="true" />
          <span><span className="block text-xl font-bold">{t("emergency.title")}</span><span className="block">{t("emergency.call112")} · {t("emergency.call108")}</span></span>
        </button>
      )}
      {final && !emergency && <ResultSection response={response} />}
      {final && emergency && emOpen && <EmergencyView response={response} onBack={() => setEmOpen(false)} />}
    </div>
  );
}
