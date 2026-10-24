import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { CARE, EXAMPLES, ROLE, STR, URGENCY } from "./i18n.js";
import { canListen, listen, speak, stopSpeaking } from "./speech.js";

const DEFAULT_LOC = { lat: 28.6139, lng: 77.209 }; // New Delhi fallback

function useLocation() {
  const [loc, setLoc] = useState(DEFAULT_LOC);
  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (p) => setLoc({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => {},
      { timeout: 5000, maximumAge: 600000 }
    );
  }, []);
  return loc;
}

function pickSlot(cg, urgency) {
  const now = Date.now();
  const slots = (cg?.availability_slots || []).map((s) => new Date(s)).filter((d) => d.getTime() > now).sort((a, b) => a - b);
  if (urgency === "same_day") {
    const today = slots.find((d) => d.toDateString() === new Date().toDateString());
    if (today) return today;
  }
  return slots[0] || null;
}

function fmtSlot(d, ui) {
  if (!d) return "";
  return d.toLocaleString(ui === "hi" ? "hi-IN" : "en-IN", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

function chipsFor(question, bank) {
  if (!question || !bank) return [];
  for (const q of Object.values(bank)) {
    for (const l of ["en", "hi", "hinglish"]) {
      if (q[l] === question) return q.options.map((o) => o[l]);
    }
  }
  return [];
}

export default function App() {
  const [ui, setUi] = useState("en");
  const [voice, setVoice] = useState(true);
  const [messages, setMessages] = useState([]);
  const [history, setHistory] = useState([]);
  const [result, setResult] = useState(null);
  const [cgDetails, setCgDetails] = useState({});
  const [stage, setStage] = useState("chat"); // chat | emergency | confirmed
  const [booking, setBooking] = useState(null);
  const [bookingId, setBookingId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [bank, setBank] = useState(null);
  const [error, setError] = useState("");
  const recRef = useRef(null);
  const endRef = useRef(null);
  const loc = useLocation();
  const t = STR[ui];

  useEffect(() => { api.questions().then(setBank).catch(() => {}); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, result, loading]);

  const reset = () => {
    stopSpeaking();
    setMessages([]); setHistory([]); setResult(null); setCgDetails({}); setStage("chat");
    setBooking(null); setBookingId(null); setText(""); setError("");
  };

  async function send(input) {
    const msg = (input ?? text).trim();
    if (!msg || loading) return;
    setText(""); setError(""); setResult(null);
    setMessages((m) => [...m, { role: "user", content: msg }]);
    setLoading(true);
    try {
      const res = await api.triage({ user_input: msg, language: "auto", location: loc, conversation_history: history });
      const newHist = [...history, { role: "user", content: msg }];
      if (res.follow_up_question) {
        setMessages((m) => [...m, { role: "assistant", content: res.follow_up_question, chips: chipsFor(res.follow_up_question, bank) }]);
        setHistory([...newHist, { role: "assistant", content: res.follow_up_question }]);
        speak(res.follow_up_question, voice);
      } else if (res.care_type === "emergency_referral") {
        setResult(res); setHistory(newHist); setStage("emergency");
        speak(res.reasoning, voice);
      } else {
        setResult(res); setHistory(newHist);
        speak(res.reasoning, voice);
        const ids = res.matched_caregivers.map((c) => c.caregiver_id);
        const details = await Promise.all(ids.map((id) => api.caregiver(id).catch(() => null)));
        setCgDetails(Object.fromEntries(ids.map((id, i) => [id, details[i]])));
      }
    } catch {
      setError(t.error);
    } finally {
      setLoading(false);
    }
  }

  function toggleMic() {
    if (listening) { recRef.current?.stop(); return; }
    if (!canListen) { setError(t.micUnsupported); return; }
    stopSpeaking();
    let finalText = "";
    setListening(true);
    recRef.current = listen({
      lang: ui === "hi" ? "hi-IN" : "en-IN",
      onText: (txt, isFinal) => { setText(txt); if (isFinal) finalText = txt; },
      onEnd: () => { setListening(false); if (finalText) send(finalText); },
      onError: () => setListening(false),
    });
  }

  async function book(match) {
    const cg = cgDetails[match.caregiver_id];
    const slot = pickSlot(cg, result.urgency);
    setBooking(match.caregiver_id);
    try {
      const r = await api.book({ caregiver_id: match.caregiver_id, slot: slot ? slot.toISOString() : null,
        care_type: result.care_type, urgency: result.urgency, location: loc });
      setBookingId({ ...r, cg, slot });
      setStage("confirmed");
      speak(`${t.confirmed}. ${cg?.name || ""}`, voice);
    } catch {
      setError(t.error);
    } finally {
      setBooking(null);
    }
  }

  if (stage === "emergency" && result) {
    const steps = result.reasoning.split(/(?<=[.।])\s+/).filter(Boolean);
    return (
      <div className="emergency" role="alert">
        <div className="em-icon">🚨</div>
        <h1>{t.emergencyTitle}</h1>
        <a className="call-btn" href="tel:112">📞 {t.call112}</a>
        <a className="call-btn secondary" href="tel:108">🚑 {t.call108}</a>
        <ol className="em-steps">{steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
        <button className="ghost-btn" onClick={reset}>{t.startAgain}</button>
        <p className="disclaimer light">{t.disclaimer}</p>
      </div>
    );
  }

  if (stage === "confirmed" && bookingId) {
    const role = ROLE[bookingId.cg?.role]?.[ui] || "";
    return (
      <div className="app">
        <Header t={t} ui={ui} setUi={setUi} voice={voice} setVoice={setVoice} />
        <div className="confirm card">
          <div className="big-check">✅</div>
          <h2>{t.confirmed}</h2>
          <p><b>{t.who}:</b> {bookingId.cg?.name} · {role}</p>
          {bookingId.slot && <p><b>{t.when}:</b> {fmtSlot(bookingId.slot, ui)}</p>}
          <p><b>{t.bookingId}:</b> {bookingId.booking_id}</p>
          <button className="primary-btn" onClick={reset}>{t.startAgain}</button>
        </div>
        <p className="disclaimer">{t.disclaimer}</p>
      </div>
    );
  }

  const lastChips = messages.length && messages[messages.length - 1].role === "assistant" ? messages[messages.length - 1].chips : [];

  return (
    <div className="app">
      <Header t={t} ui={ui} setUi={setUi} voice={voice} setVoice={setVoice} />

      {messages.length === 0 && (
        <section className="hero">
          <p className="tagline">{t.tagline}</p>
          <div className="examples">
            <span className="examples-label">{t.examples}</span>
            {EXAMPLES.map((e) => (
              <button key={e.label} className="example-chip" onClick={() => send(e.text)} title={e.text}>{e.label}</button>
            ))}
          </div>
        </section>
      )}

      <main className="chat" aria-live="polite">
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>{m.content}</div>
        ))}
        {loading && <div className="bubble assistant muted">{t.thinking}</div>}
        {result && result.care_type && <ResultCard result={result} ui={ui} t={t} details={cgDetails} onBook={book} booking={booking} />}
        {error && <div className="error">{error}</div>}
        <div ref={endRef} />
      </main>

      <footer className="composer">
        {lastChips?.length > 0 && !loading && (
          <div className="chips">{lastChips.map((c) => <button key={c} className="chip" onClick={() => send(c)}>{c}</button>)}</div>
        )}
        <button className={`mic ${listening ? "on" : ""}`} onClick={toggleMic} aria-label={t.speak}>
          <span className="mic-icon">🎤</span>
          <span>{listening ? t.listening : t.speak}</span>
        </button>
        <form className="text-row" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t.typeHere} aria-label={t.typeHere} />
          <button type="submit" className="send" disabled={!text.trim() || loading}>{t.send}</button>
        </form>
        {(result || messages.length > 0) && <button className="link-btn" onClick={reset}>{t.startAgain}</button>}
        <p className="disclaimer">{t.disclaimer}</p>
      </footer>
    </div>
  );
}

function Header({ t, ui, setUi, voice, setVoice }) {
  return (
    <header className="top">
      <div className="brand">🧭 CareCompass</div>
      <div className="top-actions">
        <button className="pill" onClick={() => { setVoice(!voice); if (voice) stopSpeaking(); }} aria-pressed={voice}>
          {voice ? "🔊 " + t.voiceOn : "🔇 " + t.voiceOff}
        </button>
        <button className="pill" onClick={() => setUi(ui === "en" ? "hi" : "en")}>{t.lang}</button>
      </div>
    </header>
  );
}

function ResultCard({ result, ui, t, details, onBook, booking }) {
  const care = CARE[result.care_type];
  const urg = URGENCY[result.urgency];
  return (
    <section className="result">
      <div className="card care-card">
        <div className="care-head">
          <span className="care-icon">{care.icon}</span>
          <div>
            <div className="label">{t.resultTitle}</div>
            <div className="care-name">{care[ui]}</div>
          </div>
        </div>
        <span className={`badge ${urg.cls}`}>⏱ {urg[ui]}</span>
        <div className="why"><b>{t.why}:</b> {result.reasoning}</div>
      </div>

      <h3 className="section-title">{t.caregivers}</h3>
      {result.matched_caregivers.length === 0 && <div className="card">{t.noCaregivers}</div>}
      {result.matched_caregivers.map((m, i) => {
        const cg = details[m.caregiver_id];
        return (
          <div className={`card cg-card ${i === 0 ? "top-pick" : ""}`} key={m.caregiver_id}>
            <div className="cg-row">
              <div className="avatar">{(cg?.name || "?").slice(0, 1)}</div>
              <div className="cg-info">
                <div className="cg-name">{cg?.name || m.caregiver_id}</div>
                <div className="cg-role">{ROLE[cg?.role]?.[ui] || ""} · ⭐ {cg?.rating ?? ""}</div>
              </div>
              <div className="score" title="match score">{Math.round(m.score * 100)}%</div>
            </div>
            <div className="cg-reason">{m.reason}</div>
            <button className="primary-btn" onClick={() => onBook(m)} disabled={!!booking}>
              {booking === m.caregiver_id ? t.booking : `✔ ${t.book}`}
            </button>
          </div>
        );
      })}
    </section>
  );
}
