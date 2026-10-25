# Declarations: models, APIs, libraries, datasets

All code was written during the event by team OCTUPUS. Open-source components are used under their licences.

## Datasets
| Dataset | Use | Link |
|---|---|---|
| SwasthMitra dev data (`dev_data/`) | **Synthetic, self-generated** by `scripts/make_dev_data.py` (templates + seeded randomisation, no LLM, no real patients). Includes the clinical pathway vignettes from `scripts/pathway_vignettes.py`, hand-labelled by the team from the stage tables in `docs/CLINICAL_PATHWAYS.md`. Development/validation only. | this repo |
| KTAS emergency triage (Kaggle, ilkeryildiz) | Urgency model training/validation (`KTAS_expert`), red-flag recall checks. Triage-time fields only. | https://www.kaggle.com/datasets/ilkeryildiz/emergency-service-triage-application |
| Disease Symptom Description (Kaggle, itachi9604) | `Symptom-severity.csv` weights for the severity lexicon; `dataset.csv` symptom lists as extra English training text (disease mapped internally to care type). Precautions are **not** used. | https://www.kaggle.com/datasets/itachi9604/disease-symptom-description-dataset |
| Symptoms to Diseases (Kaggle, abhishekgodara) | Sampled symptom lists (20 per disease) as extra English care-type training text; diseases mapped internally via `config/disease_to_care_type.json`, never shown to users. | https://www.kaggle.com/datasets/abhishekgodara/symptoms-to-diseases |
| ICD-10-CM code descriptions, FY2026 (CMS / CDC NCHS, public domain) | 3-character category names (A00–U85; external-cause V–Y and Z codes excluded) added to the broad medical lexicon `config/medical_lexicon.json` (built by `scripts/build_lexicon.py`) so a named condition is recognised as a health request. Codes are never shown and never used as a diagnosis. Raw files in `data/public/icd10/` (gitignored). | https://www.cms.gov/medicare/coding-billing/icd-10-codes |
| Medical lexicon and aliases (team-curated) | Symptom and disease names from the two Kaggle datasets above plus ICD-10-CM categories; Hindi / Hinglish body parts, abnormal descriptors and condition names (`config/disease_aliases.json`, tagged emergency_condition / serious_chronic / common). Names only, no records. | this repo |

No real patient data is used.

## Clinical references
The clinical pathway thresholds and danger signs (`docs/CLINICAL_PATHWAYS.md`, `config/pathways/*.json`) were specified by our mentor from the sources below. They are used only to choose care type and urgency, never to diagnose. No text from these documents is reproduced in the product.

| Reference | Used for |
|---|---|
| WHO, *Dengue: Guidelines for Diagnosis, Treatment, Prevention and Control*, new edition (2009) | Fever pathway: dengue warning signs and severe-dengue criteria (platelet and warning-sign stages). |
| National Center for Vector Borne Diseases Control (NCVBDC), Govt. of India: dengue, malaria and chikungunya guidance | Fever pathway: India-specific vector-borne fever patterns. |
| WHO, *Integrated Management of Childhood Illness (IMCI)* chart booklet | General danger signs in children (cannot drink, vomits everything, convulsions, lethargy): child modifiers and S3 rules. |
| NICE guideline NG143, *Fever in under 5s: assessment and initial management* (2019) | Traffic-light approach; any fever under 3 months is high risk (infant modifier). |
| National TB Elimination Programme (NTEP), India | Cough pathway: cough of 2 weeks or more as presumptive TB (S2, specialist). |
| Standard emergency chest pain red flags (e.g. NICE CG95, *Chest pain of recent onset*) and stroke FAST signs | Chest pain and headache pathway S3 rules. |

## Models
| Model | Use |
|---|---|
| Rule engine (`backend/app/safety.py`) | Deterministic red-flag detection (EN/HI/Hinglish), written by the team. |
| Clinical pathway engine (`backend/app/pathways/`, `config/pathways/*.json`) | Deterministic S0–S3 severity staging for fever, cough, stomach, chest pain and headache, from the mentor's specification; written by the team. |
| Model A: TF-IDF (word 1-2 + char_wb 2-5 grams) + Logistic Regression (scikit-learn) | Care type and urgency classifiers, trained by us on dev data + processed public data. |
| Model C: [google/muril-base-cased](https://huggingface.co/google/muril-base-cased) (Apache-2.0), fallback [xlm-roberta-base](https://huggingface.co/FacebookAI/xlm-roberta-base) (MIT) | Multilingual encoder fine-tuned by us with two classification heads (optional, GPU). |
| Hosted LLM (Model B), provider/model set via `LLM_PROVIDER` / `LLM_MODEL` | Few-shot routing with taxonomy definitions and 5 retrieved examples; output strictly validated; never sees personal identifiers. Exact provider and model are recorded below once configured. |

## External APIs
| API | Use |
|---|---|
| Hosted LLM API (provider TBD: OpenAI-compatible / Gemini / Anthropic) | Model B triage call, 6 s timeout, local fallback. |
| Google Gemini API (`gemini-flash-lite-latest`, optional, `GEMINI_API_KEY`) | **Intent classification only**: one closed label per user turn (genuine_health, joke_or_song_lyric, hypothetical, absurd_or_impossible, animal_patient, deceased_patient, past_event, non_medical_off_topic, gibberish, prompt_injection). Temperature 0, strict JSON, 4 s timeout, PII redacted first, no call in Incognito or LOCAL_ONLY. It never writes user-facing text and can never lower urgency or dismiss a red flag; without it the local rules and classifier decide. |
| Browser Web Speech API (SpeechRecognition, speechSynthesis) | Voice input (hi-IN / en-IN) and read-aloud in the frontend; runs in the user's browser. |
| Google Maps Platform: Maps JavaScript API, Places API (Place Autocomplete, India only), Geocoding API | Maps (location picker, caregiver map, emergency screen), "Search your area" and the area name for a GPS fix or dropped pin. Called from the user's browser with `VITE_GOOGLE_MAPS_API_KEY` (frontend/.env, never committed); our server never sees the location. Optional: without a key, or if Google fails to load, the app uses Leaflet + OpenStreetMap. |
| OpenStreetMap tile servers | Fallback map tiles when Google Maps is not configured (© OpenStreetMap contributors, ODbL; attribution shown on the map). |
| Google Fonts (Plus Jakarta Sans, Source Sans 3, Noto Sans Devanagari, JetBrains Mono; SIL OFL) | Web fonts. |
| Browser Geolocation API | User location for caregiver distance, asked only after the user taps "Allow location" (https or localhost only); otherwise search, a locality list or a map pin. |

## Libraries
| Library | Licence | Use |
|---|---|---|
| FastAPI, Starlette, Uvicorn | MIT / BSD | REST API |
| Pydantic | MIT | Schemas |
| pandas, NumPy | BSD | Data processing |
| scikit-learn, joblib | BSD | Model A |
| pytest | MIT | Tests |
| python-dotenv, httpx | BSD | Config, HTTP client |
| PyTorch | BSD | Model C training/inference (optional) |
| Hugging Face Transformers, Accelerate, SentencePiece | Apache-2.0 | Model C (optional) |
| React, React DOM | MIT | Frontend |
| react-router-dom | MIT | Multi-page routing |
| Tailwind CSS, PostCSS, Autoprefixer | MIT | Styling / design tokens |
| framer-motion | MIT | Subtle animations (respects prefers-reduced-motion) |
| lucide-react | ISC | Icons |
| @googlemaps/js-api-loader | Apache-2.0 | Loads the Google Maps JavaScript API once |
| Leaflet, react-leaflet | BSD-2 / Hippocratic-2.1 | Fallback maps (no Google key / Google failed) |
| Playwright (dev only) | Apache-2.0 | Screenshot-based responsive / accessibility audit |
| Vite, @vitejs/plugin-react | MIT | Frontend build |
| nginx (Docker image) | BSD-2 | Serving the built frontend |
| Docker, Docker Compose | Apache-2.0 | Packaging |

| Input-type classifier (`models/input_type.joblib`) | Ours: scikit-learn TF-IDF + calibrated logistic regression, trained by `scripts/train_input_type.py` on our synthetic vignettes, sampled public Symptoms-to-Diseases text and generated gibberish / maths / off-topic lines. |
| Knowledge base (`kb/chunks.jsonl`) | Ours: chunks of our own pathway configs, docs and curated precautions, retrieved with scikit-learn TF-IDF. No external text, no embeddings model. |
