"""Central settings: every path and knob comes from env vars (see .env.example)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[2]
if load_dotenv:
    load_dotenv(ROOT / ".env")
# "LLM_PROVIDER=     # e.g. groq" is read by python-dotenv as the value "# e.g. groq": an empty value with a comment
for _k, _v in list(os.environ.items()):
    if _v.lstrip().startswith("#"):
        os.environ[_k] = ""


def _p(name: str, default: str) -> Path:
    v = Path(os.getenv(name, default))
    return v if v.is_absolute() else ROOT / v


class Settings:
    def __init__(self) -> None:
        self.data_dir = _p("DATA_DIR", "data")
        self.official_dir = _p("OFFICIAL_DIR", "data/official")
        self.public_dir = _p("PUBLIC_DIR", "data/public")
        self.processed_dir = _p("PROCESSED_DIR", "data/processed")
        self.dev_data_dir = _p("DEV_DATA_DIR", "dev_data")
        self.models_dir = _p("MODELS_DIR", "models")
        self.config_dir = _p("CONFIG_DIR", "config")
        self.llm_provider = os.getenv("LLM_PROVIDER", "").strip().lower() or "none"
        self.llm_model = os.getenv("LLM_MODEL", "").strip()
        self.llm_api_key = os.getenv("LLM_API_KEY", "").strip()
        self.llm_timeout_s = float(os.getenv("LLM_TIMEOUT_S", "6"))
        self.use_transformer = os.getenv("USE_TRANSFORMER", "auto").lower()
        self.cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
        self.max_followups = int(os.getenv("MAX_FOLLOWUPS", "4"))
        # "Your assessment" card: educational possible causes (never a diagnosis); off -> section hidden
        self.show_possible_causes = os.getenv("SHOW_POSSIBLE_CAUSES", "true").strip().lower() in ("1", "true", "yes", "on")
        # local development only: when true the server log may include raw user text. Default false (DPDP Act 2023)
        # consistency: identical requests within this many seconds get the identical cached answer (0 = off)
        self.response_cache_ttl_s = float(os.getenv("RESPONSE_CACHE_TTL_S", "900"))
        # fixed sampling seed for LLM providers that support one (temperature is always 0)
        self.llm_seed = int(os.getenv("LLM_SEED", "7"))
        # no external API calls at all (LLM off); the decision panel shows "Processed locally"
        self.local_only = os.getenv("LOCAL_ONLY", "false").strip().lower() in ("1", "true", "yes", "on")
        self.debug_log_text = os.getenv("DEBUG_LOG_TEXT", "false").strip().lower() in ("1", "true", "yes", "on")

    def __repr__(self) -> str:  # never leak the key
        return f"Settings(provider={self.llm_provider}, model={self.llm_model}, key={'set' if self.llm_api_key else 'unset'})"


@lru_cache
def get_settings() -> Settings:
    return Settings()
