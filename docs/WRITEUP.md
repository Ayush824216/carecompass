# CareCompass: multilingual care routing with safety-first triage
**Team OCTUPUS (KIET Group of Institutions) · HackIIITD 2026, AI for Healthcare Access**

## 1. Problem and approach
Families, often elderly or with low literacy, describe a health need in English, Hindi or Hinglish ("Papa ko do din se bukhar hai aur khansi bhi"). CareCompass answers three questions: **what care** (paramedic home visit, nurse home visit, GP teleconsult, specialist referral, emergency referral), **how urgent** (routine, same-day, immediate) and **who should go** (a ranked caregiver with a reason). It is a **routing** tool: it never diagnoses, never prescribes, and never shows disease or medicine names.

The design principle is *deterministic safety, learned routing*. Emergencies are caught by an auditable multilingual rule engine that runs before and after the models. The learned components then handle the large, ambiguous non-emergency space, where macro-F1 is earned.

## 2. Pipeline
`lang → normalise → safety → (emergency | intake → follow-up | triage → safety re-check → matching)`. The API is stateless: the client sends the full `conversation_history` every turn.

- **Language** (`lang.py`). Devanagari script means Hindi. Latin script with Hindi function or symptom words means Hinglish. A normaliser maps about 120 Hindi and Hinglish symptom and family terms, with their spelling variants (bukhar/bukhaar/bukar, saans phoolna, चक्कर), to canonical English. Questions, reasoning and reasons are returned in the user's language.
- **Safety** (`safety.py`). There are 20 red-flag categories: chest pain and cardiac referred pain, severe breathing difficulty, blue lips, unconsciousness, seizure, stroke signs, heavy bleeding, anaphylaxis, suicidal intent, poisoning or overdose, burns, major trauma including a fall where the person can't stand, sudden vision loss, low blood sugar, urinary retention, altered mental state, fever with stiff neck or confusion, infant danger signs (any fever under 3 months), pregnancy emergencies, and serious head injury. Each is covered by English, Devanagari and Hinglish patterns. Negation is clause-scoped: English pre-negation ("no chest pain") and Hindi post-negation ("seene mein dard *nahi* hai"). Patterns that contain a negation themselves ("saans *nahi* aa rahi") still fire. Targeted exclusions stop over-triage of history ("discharged after a stroke"), chronic exertional breathlessness, heavy periods over months, and small cuts. Rules run on the raw text, the normalised text and every user turn. Any flag gives `emergency_referral` + `immediate`, no follow-up questions, no caregiver matching, and plain-language call-for-help steps (112 / 108, stay with the person, do not drive yourself). Suicidal intent also gets the Tele-MANAS 14416 helpline.
- **Intake** (`intake.py`). Extracts symptoms, duration (using the user's own words, e.g. "do din se"), severity, age group, breathing status, chronic conditions and mobility. A follow-up is asked **only** when the local model is below its confidence gate (0.6), or when a high-risk screen applies. Examples of high-risk screens are high fever with headache (asks about stiff neck or confusion), sweating or palpitations (asks about chest pain), and an infant or elderly person with vomiting (asks whether they are drinking). Safety questions come first, there are at most 4, and each is answerable with one tap. A "yes" to a screening question becomes a red flag. The average is **0.19 questions** on the dev validation split.
- **Triage** (`triage.py`). **Model A** is TF-IDF (word 1–2-grams on the normalised text plus char_wb 2–5-grams on the raw text, which absorbs Hinglish spelling variation) with class-balanced logistic regression, one model for care type and one for urgency. **Model C** is `google/muril-base-cased` fine-tuned with two heads. **Model B** is a hosted LLM given the taxonomy definitions plus k=5 TF-IDF-retrieved labelled examples, returning strict JSON. Its output is validated (labels, red-flag ids) and its reasoning is dropped if it contains any disease or medicine term. Decision rules: if P(emergency) ≥ 0.40 on either head, the case goes to emergency; the LLM is preferred when its output is valid; when urgency disagrees, the **more urgent** label wins; rules always override.
- **Matching** (`matching.py`). Hard filters first: role eligibility (with a specialty filter for specialists, such as an orthopaedic specialist for knee pain), a 20 km cutoff for home visits, and a slot today for same-day cases. Then a weighted score. Home visits weight skill .30, distance .30, availability .20, language .12, rating .08. Teleconsults use distance 0, and the other weights are rebalanced. Every reason is built from the actual score components in the user's language: "Hindi bolte hain, 5 km door, aaj 3 pm free, bukhar ki jaanch mein experience, rating 4.6".
- **Fail-safe** (`pipeline.py`). On any internal error the pipeline returns a conservative same-day consult, or the emergency path if the rules see any risk. Every LLM call has a 6 s timeout and a local fallback. In-process p95 latency without the LLM is about **13 ms**.

## 3. Data
No real patient data is used. (1) **Dev data**, synthetic and self-generated: 600 vignettes from 95 hand-written scenario templates with seeded randomisation (35% English, 25% Hindi, 40% Hinglish, about 15% emergencies, negations, family members, durations), 60 mock Delhi-NCR caregivers, and a taxonomy. (2) **KTAS** (Kaggle): `KTAS_expert` mapped 1–2 → immediate, 3 → same-day, 4–5 → routine, using triage-time fields only (complaint, age, mental state, injury). (3) **Disease-Symptom Description** and **Symptoms-to-Diseases** (Kaggle): symptom lists turned into English sentences, with each disease mapped *internally* to a care type through a reviewable JSON file. The severity weights informed the red-flag lexicon. Public rows get lower sample weights (0.35–0.6) than vignettes. Organiser data drops into `data/official/` and is picked up by one adapter, with column and label names mapped in `config/label_map.json`.

## 4. Results (summary; full tables in `EVAL.md`)
| Set | care macro-F1 | urgency macro-F1 | emergency recall | under-triage |
|---|---|---|---|---|
| Dev validation, full pipeline (n=119) | 0.948 | 0.900 | **1.000** | 0.017 |
| Hand-written challenge v1–v3 (n=130), after fixes | 0.78–0.88 | 0.66–0.88 | **1.000** | ≤ 0.033 |
| Blind first look, challenge v2 / v3 | 0.61 / 0.73 | 0.67 / 0.60 | 0.44 / 0.78 | – |
| KTAS validation (urgency only, n=253) | – | 0.49 | KTAS 1–2: 0.88 | 0.067 |

**Model C (MuRIL, 5 min fine-tune on an RTX 3050, 2.5 GB peak VRAM, 462 MB fp16)** scored 0.86 care-F1 on dev val but only 0.57–0.61 on the challenge sets, against 0.78–0.88 for Model A. With ~600 synthetic vignettes it overfits template style, so **Model A serves**. Model C is re-evaluated automatically after retraining on the official data (`EVAL.md`).

We report the **blind first-look** numbers on purpose. Each new phrasing set exposed red-flag gaps, for example "frothing at the mouth", "sugar 45" and "can't stand up after a fall". Each gap was closed with general patterns and regression tests, giving 181 tests today. A hidden test set will contain phrasings we did not anticipate. The LLM's red flags (unioned with the rules), the asymmetric urgency combination and the low model emergency threshold are the backstops for that.

## 5. Known limitations
- **Synthetic training distribution.** Vignettes are template-generated, so validation on dev data is optimistic. The models are only as good as the coverage of our scenarios until the official data arrives.
- **Rules have finite recall.** They cover common red flags in three languages, but unusual phrasing, typos in Devanagari, or code-switching into other Indian languages can slip through.
- **Over-triage trade-off.** The emergency threshold of 0.40 favours recall. On our blind sets, 2–24% of non-emergencies were escalated to emergency (and are therefore not matched).
- **KTAS mismatch.** KTAS is Korean ED data triaged mainly on vital signs, which a text-only router cannot see. We use it as auxiliary urgency signal only.
- **Labels are our own.** Care-type and urgency conventions in the dev data, such as the boundary between paramedic and GP, are the team's judgement, not clinicians'. They must be re-aligned to the doctor-labelled official set.
- **Voice** depends on the browser's Web Speech API (best in Chrome). Hinglish is transcribed through hi-IN.
- **Mock services.** Caregivers, slots and booking are mock data. No identity, consent or real dispatch is implemented.

## 6. Declarations
All models, APIs, libraries and datasets are listed with links in `docs/DECLARATIONS.md`. All code was written during the event.
