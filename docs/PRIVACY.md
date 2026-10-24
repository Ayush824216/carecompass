# Privacy

SwasthMitra routes care. It does not diagnose. This page describes what it processes, where data lives, and how
long it is kept. It was written with India's Digital Personal Data Protection Act, 2023 (DPDP Act) in mind:
purpose limitation, data minimisation, consent, the right to erase, and no sale or advertising use.

## Data flow

1. The browser sends one request per turn to `POST /api/v1/triage`: the message, the conversation so far, the
   location, and (Memory ON only) a few remembered items. The API is stateless.
2. The server decides in memory: safety rules, clinical pathways, local models, and optionally a hosted LLM.
   Before any LLM call, names, phone numbers, emails, addresses and Aadhaar-like numbers are replaced with `[NAME]`,
   `[PHONE]`, `[EMAIL]`, `[ADDRESS]` and `[ID]` (`backend/app/redact.py`). Symptoms and readings are kept.
3. The answer goes back to the browser. The server keeps no account, no database and no files about the user.

What the server holds briefly:

| What | Where | How long |
|---|---|---|
| Response cache: a hash of the request maps to the answer, so the same request gets the same answer | Process memory | 15 min (`RESPONSE_CACHE_TTL_S`), lost on restart; skipped in Incognito |
| Metrics: counts of decision labels, stages and latency buckets, never text | Process memory (`GET /metrics`) | Until restart; skipped in Incognito |
| Logs: startup, latency timings, error class names | Server stdout | As your log host keeps them; no user text unless `DEBUG_LOG_TEXT=true` (local development only) |

## Memory ON (default) vs Incognito

**Memory ON.** A health profile is saved only in this browser on this device (localStorage key `cc.memory`):
- age group;
- chronic conditions the user confirms (sugar, BP, heart, kidney, asthma);
- pregnancy, opt-in only;
- short summaries of past assessments (date, category, stage, care type), never the chat.

Preferred language, saved location and the emergency contact use their own keys on the same device. Next time,
remembered items are sent in the optional `memory` request field and confirmed once in the chat ("Pichli baar
aapne bataya tha: sugar. Kya yeh abhi bhi sahi hai?"). Only "Yes" adds them as risk factors, so memory can raise
urgency but never lower it. "My health memory" (`/memory`) lets the user view, edit, forget one item ("Mat yaad
rakho / Forget"), delete everything, or export a JSON file.

**Incognito.** Nothing is written to any browser storage. The conversation lives in page memory only and is wiped
when the tab closes or the user taps "End session". Every request carries `X-Incognito: 1`, and the server then
skips its cache, its metrics and its latency log line, and uses local models only (no LLM call). The badge says
"Incognito: nothing is saved".

**LOCAL_ONLY.** `LOCAL_ONLY=true` turns off every external API call for all requests. The decision panel shows
"Processed locally" whenever no hosted model was used.

## Sensitive information

The following are never saved by default: HIV/STI, mental health (the mood pathway), sexual health, pregnancy,
and alcohol or drug use. When the conversation touches one of these, the "Remember for next time?" card lists it
unticked and marked *Sensitive*. It is saved only if the user ticks "Save this". An assessment summary in the mood
category is treated the same way.

## Retention and erasure

- Device memory stays until the user deletes it (one item, or everything) or clears the browser's site data.
- Server-side data is limited to the cache and metrics in the table above. Nothing to erase survives a restart.
- Synthetic data only: the demo has no real patients.

## Consent

On first use a notice explains:
- what is processed;
- that memory is saved on this device only, never on the server;
- that this is not a diagnosis;
- how to use Incognito.

The user chooses "I understand, continue" (device memory) or "Use Incognito". "Clear conversation" on the Get Care
page wipes the current chat at any time.
