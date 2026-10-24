# SwasthMitra: multilingual care routing with safety-first triage

> SwasthMitra is our solution to the CareCompass problem statement (CAI, IIIT-Delhi).

**Team OCTUPUS (KIET Group of Institutions) · HackIIITD 2026, AI for Healthcare Access**

## 1. Problem and approach
Families, often elderly or with low literacy, describe a health need in English, Hindi or Hinglish ("Papa ko do din se bukhar hai aur khansi bhi"). SwasthMitra answers three questions: **what care** (paramedic home visit, nurse home visit, GP teleconsult, specialist referral, emergency referral), **how urgent** (routine, same-day, immediate) and **who should go** (a ranked caregiver with a reason). It is a **routing** tool. It never diagnoses, never prescribes, and never shows disease or medicine names.

The design principle is *deterministic safety, clinical pathways, learned routing*. Auditable rules catch emergencies before and after the models. Mentor-specified pathways grade the five most common complaints. A learned model handles everything else.

## 2. Pipeline
`lang → normalise → safety → domain guard → clinical pathways → (emergency | follow-up | triage → merge → safety re-check → matching)`. The API is stateless: the client sends the full `conversation_history` every turn.

- **Language** (`lang.py`). Script and function words identify Hindi or Hinglish. A normaliser maps about 120 symptom and family terms, with spelling variants (bukhar/bukhaar/bukar, चक्कर), to English. Questions, reasoning and caregiver reasons come back in the user's language.
- **Safety** (`safety.py`). There are 20 red-flag categories, such as cardiac chest pain, severe breathlessness, stroke signs, heavy bleeding, suicidal intent, infant danger signs and pregnancy emergencies, each with English, Devanagari and Hinglish patterns. Negation is clause-scoped ("seene mein dard *nahi* hai"). Exclusions stop over-triage of history ("discharged after a stroke"), chest-wall pain, sensations ("burning in the chest" is not a burn) and "khoon ki kami / jaanch" (anaemia, a blood test). Any flag gives `emergency_referral` + `immediate`, no questions, no matching, and call-for-help steps (112 / 108). Suicidal intent also gets the Tele-MANAS 14416 helpline.
- **Clinical pathways** (`pathways/`; rules in `config/pathways/*.json`; spec in `docs/CLINICAL_PATHWAYS.md`). Fever, cough, stomach, chest pain and headache are graded on a ladder: **S0** routine, **S1** same-day, **S2** same-day with the right professional, **S3** emergency. A slot parser reads temperature (°C/°F, "tez bukhar"), durations ("parso se", weeks), age in months or years, platelets ("40k", "40 hazaar", "0.4 lakh"), BP ("180/110") and counts ("10 baar ulti"). It sets aside someone else's illness and past history, and it never confirms a disease the user names. Some risk modifiers force S3: a baby under 3 months with fever, a child under 5 with a danger sign, new confusion at 65+, and pain or bleeding in pregnancy. Age 65+ or a long-term condition raises the stage by one, and raises never stack. Every pathway runs and the most severe leads. Final urgency is the more urgent of pathway and model. Care type comes from the pathway when explicit rules set the stage, otherwise from the model, and missing information never lowers urgency. Concern patterns ("dengue-like") stay internal. They appear only in the debug block, labelled "not a diagnosis". The decision panel shows the stage and what moved it: "Fever pathway · S2 · platelets 80,000 + abdominal pain".
- **Questions** (`intake.py`, pathways). Inside a pathway, questions follow a senior doctor's order. A multi-select danger screen comes first, where "Kuch nahi / None" is exclusive. Then come duration, associated signs and who the patient is. Answered slots are skipped and questioning stops at S3. Outside a pathway, a question is asked only below the model's confidence gate (0.6) or for a high-risk screen. The cap is 4 questions, free text and voice work as answers, and the average is **0.28** first-turn questions.
- **Triage** (`triage.py`). **Model A** (serving) is TF-IDF over word 1–2-grams and char_wb 2–5-grams (which absorbs Hinglish spelling), with class-balanced logistic regression for each head. **Model C** is fine-tuned `google/muril-base-cased`. **Model B** is an optional hosted LLM with k=5 retrieved examples and strictly validated JSON. Its reasoning is dropped if it names a disease or medicine. Emergency wins if P(emergency) ≥ 0.40, the more urgent label wins on disagreement, and rules always override.
- **Matching** (`matching.py`). Hard filters come first: role and specialty, 20 km for home visits, and a slot today for same-day cases. Home visits are then scored on skill .30, distance .30, availability .20, language .12 and rating .08. Reasons are built from the real components: "Hindi bolte hain, 5 km door, aaj 3 pm free, rating 4.6".
- **Fail-safe** (`pipeline.py`). An internal error gives a conservative same-day consult, or the emergency path if the rules see risk. LLM calls time out at 6 s and fall back locally. p95 latency without the LLM is about **10 ms**.

## 3. Data
No real patient data is used. (1) **Dev data**, synthetic and self-generated: 1,027 vignettes (34% English, 29% Hindi, 37% Hinglish, 26% emergencies). 565 come from 80 generic templates. 462 are **pathway vignettes** from 78 templates labelled from the mentor's stage tables, covering pathway × S0–S3 × risk modifier × language. They replace generic rows inside a pathway, so the two label sources never disagree. Every row has a `template_id`, and train and validation never share a template. Model A is not fitted on pathway S3 rows, which the engine routes deterministically: training on them taught spurious emergency cues, and false emergencies on the challenge sets rose from 6% to 16%. Dev data also has 74 mock Delhi-NCR caregivers. (2) **KTAS** (Kaggle): `KTAS_expert` 1–2 → immediate, 3 → same-day, 4–5 → routine, from triage-time fields only. (3) **Disease-Symptom Description** and **Symptoms-to-Diseases** (Kaggle): symptom lists as English sentences, with diseases mapped *internally* to care types. Public rows carry lower weights (0.35–0.6). Organiser data drops into `data/official/` behind one adapter (`config/label_map.json`).

## 4. Results (summary; full tables in `EVAL.md`)
| Set | care macro-F1 | urgency macro-F1 | emergency recall | under-triage |
|---|---|---|---|---|
| Dev validation, unseen templates, full pipeline (n=233) | 0.918 | 0.936 | **1.000** | 0.000 |
| Hand-written challenge v1–v3 (n=130), full pipeline | 0.72–0.81 | 0.56–0.81 | **1.000** | ≤ 0.033 |
| Blind first look, challenge v2 / v3 | 0.61 / 0.73 | 0.67 / 0.60 | 0.44 / 0.78 | – |
| KTAS validation (urgency only, n=255) | – | 0.50 | KTAS 1–2: 0.86 | 0.067 |

**Clinical pathways.** On 93 vignettes from unseen templates, the engine stage is correct for all of them and **S3 recall is 1.000 in every pathway**, with zero under-triage. The full pipeline matches the authored care type and urgency on 96–100%. All 62 worked examples and the 20 edge cases from the spec pass at stage level (`tests/test_pathways.py`). End to end, 7 S0 examples come out same-day rather than routine, because the spec's "more urgent of pathway and model" rule lets the model raise them.

**Model C** (MuRIL, 5 min fine-tune on an RTX 3050) scored 0.57–0.61 care-F1 on the challenge sets, against 0.71–0.80 for Model A. It overfits template style, so Model A serves. Model C is re-evaluated automatically on official data.

We report **blind first-look** numbers on purpose. Each new phrasing set exposed gaps ("frothing at the mouth", "sugar 45"). Each gap was closed with general patterns and regression tests, and there are 370 tests today. The LLM's red flags, the asymmetric urgency combination and the low emergency threshold are the backstops for phrasings we did not anticipate.

## 5. Known limitations
- **Synthetic data.** Template-generated vignettes make dev validation optimistic. Pathway sign patterns were tuned while the pathway vignettes were written, so the hand-written challenge sets are the fairer estimate.
- **Rules have finite recall.** Unusual phrasing, Devanagari typos or other Indian languages can slip through.
- **Over-triage trade-off.** The 0.40 emergency threshold and the "more urgent wins" rule favour recall. On the challenge sets, 2–19% of non-emergencies were escalated.
- **Labels are our own** (e.g. the boundary between paramedic and GP). They must be re-aligned to the doctor-labelled official set. KTAS is Korean ED data triaged on vital signs, so it is auxiliary signal only.
- **Mock services.** Caregivers, slots and booking are mock data. Voice depends on the browser's Web Speech API.

## 6. Clinical references (pathway thresholds and danger signs)
- WHO. *Dengue: Guidelines for Diagnosis, Treatment, Prevention and Control*, new edition, 2009: warning signs and severe-dengue criteria.
- National Center for Vector Borne Diseases Control (NCVBDC), Govt. of India: dengue, malaria and chikungunya guidance.
- WHO. *Integrated Management of Childhood Illness (IMCI)* chart booklet: general danger signs in children.
- NICE NG143, *Fever in under 5s: assessment and initial management* (2019): traffic-light system.
- National TB Elimination Programme (NTEP), India: cough of 2 weeks or more as presumptive TB.
- Standard emergency chest pain red flags (e.g. NICE CG95, *Chest pain of recent onset*) and the stroke FAST signs.

These sources informed the mentor's thresholds. SwasthMitra uses them only to choose the care type and urgency, never to diagnose.

## 7. Declarations
All models, APIs, libraries, datasets and the references above are listed in `docs/DECLARATIONS.md`. All code was written during the event.
