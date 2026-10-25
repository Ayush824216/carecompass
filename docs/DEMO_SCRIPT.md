# Demo plan (3:00)

Setup: backend + frontend running (`LOCAL_ONLY=true` is fine: no LLM key needed), browser at phone size (Chrome DevTools, 390×844), location set to Saket, South Delhi, voice on. Clear site data once so the consent card shows, then tap **OK**. Have `docs/EVAL.md` open in a second tab.

| # | Time | Flow | Do | Point out |
|---|---|---|---|---|
| 1 | 0:00–0:15 | Hook | Home screen | "An elderly parent has a fever. Doctor, nurse or ambulance, and how soon? SwasthMitra answers: what care, how urgent, who can come." |
| 2 | 0:15–1:00 | **Hinglish fever with follow-ups** | Get Care → type *"Papa ko bukhar hai"*. Answer the chips: danger screen **Kuch nahi**, age **65+ saal**, then **2–3 din** + **102–104°F** | Questions come one at a time in Hinglish, danger signs first, at most 4 clinical questions. The decision panel fills in as answers arrive. |
| 3 | 1:00–1:30 | **Assessment + booking** | Scroll to the assessment card, then the caregiver cards; tap **Book** on the first | Paramedic home visit, same day (65+ prefers a home visit). Possible causes are labelled "not a diagnosis". Each caregiver card gives real reasons (distance, free today, Hindi, rating). The booking confirmation shows an ID and slot. |
| 4 | 1:30–2:00 | **Emergency + SOS** | New chat → *"Dadaji ke seene mein tez dard ho raha hai aur paseena aa raha hai"* | The red screen opens at once, with no questions: big **112**, **108** and **SOS to family**. Tap SOS: the SMS app opens with every family contact, the danger signs and a map link. "Sent" appears only if the server SMS provider confirms. |
| 5 | 2:00–2:20 | **Women's health + several complaints** | New chat → *"Mujhe periods mein bahut dard hota hai, mood swings aur rona bhi aata hai"*. Answer **Inmein se kuch nahi**, age, **Nahi**, **Kuch mahino se** | Routed to a gynaecologist. The reply ends with "Aapne rona aana aur mood badalna bhi bataya — kya aap is par bhi baat karna chahengi?", and the **Talk about** button opens the mood pathway. |
| 6 | 2:20–2:35 | **Abstention** | New chat → *"abba dabba jabba"* | No clinical question: "I could not find a health problem… what, who, since when?". Then *"mujhe cnacer hai"* is recognised despite the typo, and the name is not repeated back. |
| 7 | 2:35–2:50 | **Incognito** | Tap **Incognito** in the navbar | Toast "Incognito on: nothing will be saved". The chat gets a dashed border. Nothing is written to the device, server cache, metrics or logs, and the LLM is skipped. |
| 8 | 2:50–3:00 | Metrics | `docs/EVAL.md`, headline table | Dev/synthetic validation: S3 recall 1.000, false emergencies 0 on the challenge sets, care-type F1 0.861, urgency F1 0.929, 958 tests. "Routing support only: no diagnosis, no prescriptions." End card: team OCTUPUS, KIET. |

**Before recording**
- Add two SOS contacts on `/sos` (demo numbers) and grant location permission, so no prompt appears mid-shot.
- If typing is slow, paste the sentences; all of them are deterministic, so a retake gives the same answer.
- The emergency screen can be closed with **Back to chat**, so shot 4 can be retaken.
