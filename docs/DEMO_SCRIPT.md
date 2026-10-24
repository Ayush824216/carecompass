# Demo video script (≤ 3:00)

Record on a phone-sized browser window (Chrome DevTools device mode, 390×844) with sound on, so the read-aloud is audible. Have the backend running with the LLM key set, plus a second tab open at `/docs`.

| # | Time | Shot | What to show / say |
|---|---|---|---|
| 1 | 0:00–0:15 | Title card, then app home | "In India, an elderly parent with a fever often doesn't know whether to call a doctor, a nurse or an ambulance. SwasthMitra answers three questions: what care, how urgent, and who should go." |
| 2 | 0:15–0:45 | **Hinglish voice input.** Tap the big mic and say *"Papa ko do din se bukhar hai aur khansi bhi"* | The transcript appears live. Result: **Paramedic visit at home · Today**. The *Why* line quotes the user's own words ("Do din se bukhar aur khansi"), and the answer is read aloud. |
| 3 | 0:45–1:10 | **Follow-up flow.** Start again and type *"mujhe khansi hai"* (or pick a vague input such as "tabiyat kharab hai") | One short question appears in the user's language with one-tap chips (**Haan / Nahi**). Tap **Nahi**, and the decision follows. Point out that the system asks only when the answer could change the decision, with at most 4 questions. Most inputs need none (average 0.09 on dev). |
| 4 | 1:10–1:40 | **Caregiver match + booking** | Three caregiver cards, each with a reason built from real data: "Hindi bolte hain, 5 km door, aaj 3 pm free, rating 4.6". Tap **Book**, and the confirmation screen shows the booking ID and time. |
| 5 | 1:40–2:05 | **Hindi + specialist.** Toggle the UI to हिंदी and tap the example "मम्मी को तीन महीने से घुटनों में दर्द है" | **Specialist · Within a few days**, with a bone and joint specialist matched and the reasons in Hindi. |
| 6 | 2:05–2:30 | **Emergency.** Tap the example *"Dadaji ke seene mein tez dard ho raha hai aur paseena aa raha hai"* | The full red screen with large **Call 112** and **Call 108** buttons and step-by-step instructions. No booking flow and no questions. Then type *"seene mein dard nahi hai, bas gas hai"* to show that negation is handled and the case is not an emergency. |
| 7 | 2:30–2:45 | `/docs` (Swagger) | One `POST /api/v1/triage` call: stateless, JSON schema, `conversation_history`, plus `/book` and `/caregivers/{id}`. Show `docker compose up` in a terminal for a second. |
| 8 | 2:45–3:00 | `docs/EVAL.md` table | Emergency recall **1.00** on dev validation, macro-F1 for care type and urgency, p95 latency in milliseconds, and 130+ tests including 91 safety cases in three languages. "Routing support only: no diagnosis, no prescriptions." End card: team OCTUPUS, KIET. |

**Tips**
- Pre-grant microphone and location permission so no browser prompt appears during recording.
- If voice recognition is unreliable in the room, type the same sentence. The demo chips are one tap.
- Keep the voice toggle **on** for shots 2, 4 and 6.
