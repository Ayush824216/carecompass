const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function req(path, opts = {}) {
  const r = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

export const api = {
  triage: (body) => req("/api/v1/triage", { method: "POST", body: JSON.stringify(body) }),
  caregiver: (id) => req(`/api/v1/caregivers/${encodeURIComponent(id)}`),
  book: (body) => req("/api/v1/book", { method: "POST", body: JSON.stringify(body) }),
  questions: () => req("/api/v1/questions"),
};
