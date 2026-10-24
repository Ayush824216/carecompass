// Browser Web Speech API helpers (speech-to-text + text-to-speech). Both degrade gracefully.

const Recognition = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);

export const canListen = Boolean(Recognition);

export function listen({ lang, onText, onEnd, onError }) {
  if (!Recognition) {
    onError?.("unsupported");
    return null;
  }
  const rec = new Recognition();
  rec.lang = lang; // "hi-IN" also transcribes Hinglish speech; "en-IN" for English
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;
  rec.onresult = (e) => {
    const text = Array.from(e.results).map((r) => r[0].transcript).join(" ");
    onText(text, e.results[e.results.length - 1].isFinal);
  };
  rec.onerror = (e) => onError?.(e.error);
  rec.onend = () => onEnd?.();
  rec.start();
  return rec;
}

const DEVANAGARI = /[ऀ-ॿ]/;

export function speak(text, enabled) {
  if (!enabled || !text || typeof window === "undefined" || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  // Hinglish (Latin script) reads best with a Hindi voice too
  const hindiLike = DEVANAGARI.test(text) || /\b(hai|ko|nahi|aap|karein|aaj|ghar)\b/i.test(text);
  u.lang = hindiLike ? "hi-IN" : "en-IN";
  const voice = window.speechSynthesis.getVoices().find((v) => v.lang === u.lang);
  if (voice) u.voice = voice;
  u.rate = 0.92;
  window.speechSynthesis.speak(u);
}

export function stopSpeaking() {
  if (typeof window !== "undefined" && window.speechSynthesis) window.speechSynthesis.cancel();
}
