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

## External APIs
| API | Use |
|---|---|
| _none yet_ | |

## Libraries
| Library | Licence | Use |
|---|---|---|
| FastAPI, Starlette, Uvicorn | MIT / BSD | REST API |
| Pydantic | MIT | Schemas |
| pandas, NumPy | BSD | Data processing |
| scikit-learn, joblib | BSD | Model A |
| pytest | MIT | Tests |
| python-dotenv, httpx | BSD | Config, HTTP client |
