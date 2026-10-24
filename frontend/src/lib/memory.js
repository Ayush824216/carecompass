// "My health memory": saved ONLY on this device (localStorage key cc.memory), never on the server.
// Sensitive items (HIV/STI, mental health, sexual health, pregnancy, substance use) are saved only when the user
// ticks "Save this". Every item can be forgotten one by one, or all at once. Nothing is written in Incognito.
import { load, remove, save } from "./storage.js";

export const MEMORY_KEY = "cc.memory";
// other device-only data shown on the memory page (each has its own key)
export const DEVICE_KEYS = { language: "cc.lang", location: "cc.location", emergencyContact: "cc.sosContacts" };
const EMPTY = { v: 1, items: {}, assessments: [] };

export function loadMemory() {
  const m = load(MEMORY_KEY, EMPTY);
  return m && typeof m === "object" && m.items ? { ...EMPTY, ...m } : EMPTY;
}

function write(m) { save(MEMORY_KEY, m); return m; }

/** Save chosen candidates ({id, kind, value, label, sensitive}); returns the new memory. */
export function saveItems(items) {
  const m = loadMemory();
  const now = new Date().toISOString();
  const next = { ...m, items: { ...m.items } };
  for (const it of items) next.items[it.id] = { id: it.id, kind: it.kind, value: it.value, label: it.label, sensitive: Boolean(it.sensitive), saved_at: now };
  return write(next);
}

export function updateItem(id, patch) {
  const m = loadMemory();
  if (!m.items[id]) return m;
  return write({ ...m, items: { ...m.items, [id]: { ...m.items[id], ...patch, saved_at: new Date().toISOString() } } });
}

export function forgetItem(id) {
  const m = loadMemory();
  const items = { ...m.items };
  delete items[id];
  return write({ ...m, items });
}

/** A short summary only: date, category, stage, care type. Never the chat. */
export function addAssessment(summary) {
  const m = loadMemory();
  const row = { date: new Date().toISOString().slice(0, 10), category: summary.category || null, stage: summary.stage || null,
    care_type: summary.care_type, urgency: summary.urgency, sensitive: Boolean(summary.sensitive) };
  return write({ ...m, assessments: [row, ...m.assessments].slice(0, 20) });
}

export function forgetAssessment(i) {
  const m = loadMemory();
  return write({ ...m, assessments: m.assessments.filter((_, j) => j !== i) });
}

export function forgetAll() {
  remove(MEMORY_KEY);
  Object.values(DEVICE_KEYS).forEach(remove);
  remove("cc.emergencyContact"); // single contact of earlier versions
  return EMPTY;
}

/** What the triage request may carry (confirmed once in the chat before use; can only add risk). */
export function memoryHints(m = loadMemory()) {
  const it = m.items;
  const conditions = ["diabetes", "hypertension", "heart", "kidney", "asthma"].filter((c) => it[c]?.value === true);
  const hints = {};
  if (it.age_group?.value) hints.age_group = it.age_group.value;
  if (conditions.length) hints.conditions = conditions;
  if (it.pregnancy?.value === true) hints.pregnant = true;
  return Object.keys(hints).length ? hints : null;
}

export function exportMemory() {
  const data = { exported_at: new Date().toISOString(), note: "SwasthMitra health memory: saved only on this device.",
    memory: loadMemory(), language: load(DEVICE_KEYS.language, null), location: load(DEVICE_KEYS.location, null),
    emergency_contact: load(DEVICE_KEYS.emergencyContact, null) };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "swasthmitra-memory.json";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
