import os
import sys
from pathlib import Path

# tests see every request fresh; tests/test_consistency.py turns the response cache on explicitly
os.environ.setdefault("RESPONSE_CACHE_TTL_S", "0")
# Gemini off in tests (an empty value is kept: python-dotenv never overrides it); test_gemini_intent mocks it
os.environ["GEMINI_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
