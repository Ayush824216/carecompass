export const API_BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, { status = 0, network = false } = {}) {
    super(message);
    this.status = status;
    this.network = network;
  }
}

async function req(path, opts = {}) {
  let r;
  try {
    r = await fetch(`${API_BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...opts });
  } catch {
    throw new ApiError("network", { network: true });
  }
  if (!r.ok) throw new ApiError(`${r.status}`, { status: r.status });
  return r.json();
}

/** POST /api/v1/triage. `debug: true` adds the optional decision trace; the rest of the body is the official schema. */
async function triage(body, { debug = false } = {}) {
  const t0 = performance.now();
  const data = await req("/api/v1/triage", { method: "POST", body: JSON.stringify(debug ? { ...body, debug: true } : body) });
  return { data, ms: Math.round(performance.now() - t0) };
}

export const api = {
  triage,
  caregiver: (id) => req(`/api/v1/caregivers/${encodeURIComponent(id)}`),
  caregivers: () => req("/api/v1/caregivers"),
  book: (body) => req("/api/v1/book", { method: "POST", body: JSON.stringify(body) }),
  questions: () => req("/api/v1/questions"),
  health: () => req("/health"),
};
