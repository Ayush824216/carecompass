# Declarations: models, APIs, libraries, datasets

All code was written during the event by team OCTUPUS. Open-source components are used under their licences.

## Datasets
| Dataset | Use | Link |
|---|---|---|
| CareCompass dev data (`dev_data/`) | **Synthetic, self-generated** by `scripts/make_dev_data.py` (templates + seeded randomisation, no LLM, no real patients). Development/validation only. | this repo |
| KTAS emergency triage (Kaggle, ilkeryildiz) | Urgency model training/validation (`KTAS_expert`), red-flag recall checks. Triage-time fields only. | https://www.kaggle.com/datasets/ilkeryildiz/emergency-service-triage-application |
| Disease Symptom Description (Kaggle, itachi9604) | `Symptom-severity.csv` weights for the severity lexicon; `dataset.csv` symptom lists as extra English training text (disease mapped internally to care type). Precautions are **not** used. | https://www.kaggle.com/datasets/itachi9604/disease-symptom-description-dataset |
| Symptoms to Diseases (Kaggle, abhishekgodara) | Sampled symptom lists (20 per disease) as extra English care-type training text; diseases mapped internally via `config/disease_to_care_type.json`, never shown to users. | https://www.kaggle.com/datasets/abhishekgodara/symptoms-to-diseases |

No real patient data is used.

## Models
| Model | Use |
|---|---|
| Rule engine (`backend/app/safety.py`) | Deterministic red-flag detection (EN/HI/Hinglish), written by the team. |
| Model A: TF-IDF (word 1-2 + char_wb 2-5 grams) + Logistic Regression (scikit-learn) | Care type and urgency classifiers, trained by us on dev data + processed public data. |
| Model C: [google/muril-base-cased](https://huggingface.co/google/muril-base-cased) (Apache-2.0), fallback [xlm-roberta-base](https://huggingface.co/FacebookAI/xlm-roberta-base) (MIT) | Multilingual encoder fine-tuned by us with two classification heads (optional, GPU). |
| Hosted LLM (Model B), provider/model set via `LLM_PROVIDER` / `LLM_MODEL` | Few-shot routing with taxonomy definitions and 5 retrieved examples; output strictly validated; never sees personal identifiers. Exact provider and model are recorded below once configured. |

## External APIs
| API | Use |
|---|---|
| Hosted LLM API (provider TBD: OpenAI-compatible / Gemini / Anthropic) | Model B triage call, 6 s timeout, local fallback. |
| Browser Web Speech API (SpeechRecognition, speechSynthesis) | Voice input (hi-IN / en-IN) and read-aloud in the frontend; runs in the user's browser. |
| OpenStreetMap tile servers | Map tiles in the web app (© OpenStreetMap contributors, ODbL). |
| Google Fonts (Plus Jakarta Sans, Source Sans 3, Noto Sans Devanagari, JetBrains Mono; SIL OFL) | Web fonts. |
| Browser Geolocation API | User location for caregiver distance (fallback: central Delhi). |

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
| Leaflet, react-leaflet | BSD-2 / Hippocratic-2.1 | Caregiver maps |
| Playwright (dev only) | Apache-2.0 | Screenshot-based responsive / accessibility audit |
| Vite, @vitejs/plugin-react | MIT | Frontend build |
| nginx (Docker image) | BSD-2 | Serving the built frontend |
| Docker, Docker Compose | Apache-2.0 | Packaging |
