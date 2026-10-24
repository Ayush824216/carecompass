"""Write dev_data/schema.json (request/response JSON Schema) from the Pydantic models."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.schemas import TriageRequest, TriageResponse  # noqa: E402

out = {
    "_note": "Indicative contract for POST /api/v1/triage (self-written dev version, not the official schema).",
    "endpoint": "POST /api/v1/triage",
    "request": TriageRequest.model_json_schema(),
    "response": TriageResponse.model_json_schema() | {"required": list(TriageResponse.model_fields)},
}
(ROOT / "dev_data" / "schema.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("wrote dev_data/schema.json")
