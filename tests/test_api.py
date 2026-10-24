import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import CARE_TYPES, URGENCIES, TriageResponse

client = TestClient(app)
SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "dev_data" / "schema.json").read_text(encoding="utf-8"))


def _check_contract(body: dict) -> None:
    TriageResponse.model_validate(body)
    for k in SCHEMA["response"]["required"]:
        assert k in body, k
    assert body["care_type"] in (None, *CARE_TYPES)
    assert body["urgency"] in (None, *URGENCIES)
    if body["follow_up_question"] is not None:
        assert body["care_type"] is None and body["urgency"] is None
    for m in body["matched_caregivers"]:
        assert set(m) == {"caregiver_id", "score", "reason"} and 0 <= m["score"] <= 1


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


@pytest.mark.parametrize("text", ["papa ko do din se bukhar hai aur khansi bhi", "मुझे सिर दर्द है",
                                  "my father has severe chest pain", "x"])
def test_triage_contract(text):
    r = client.post("/api/v1/triage", json={"user_input": text, "language": "auto",
                                            "location": {"lat": 28.54, "lng": 77.27}, "conversation_history": []})
    assert r.status_code == 200
    _check_contract(r.json())


def test_triage_minimal_request():
    r = client.post("/api/v1/triage", json={"user_input": "headache"})
    assert r.status_code == 200
    _check_contract(r.json())


def test_caregiver_lookup():
    assert client.get("/api/v1/caregivers/CG_001").status_code == 200
    assert client.get("/api/v1/caregivers/NOPE").status_code == 404


def test_book():
    r = client.post("/api/v1/book", json={"caregiver_id": "CG_001", "care_type": "paramedic_home_visit"})
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    r = client.post("/api/v1/book", json={"caregiver_id": "CG_001", "care_type": "emergency_referral"})
    assert r.json()["status"] == "rejected"


def test_lenient_request_shapes():
    r = client.post("/api/v1/triage", json={
        "user_input": "haan", "language": "Hindi", "location": {"latitude": 28.5, "longitude": 77.2},
        "conversation_history": ["mujhe khansi hai", {"speaker": "bot", "text": "Kya saans lene mein takleef ho rahi hai?"}]})
    assert r.status_code == 200
    body = r.json()
    _check_contract(body)
    assert body["care_type"] == "emergency_referral"  # "haan" to the breathing screen


def test_unknown_language_and_long_input():
    r = client.post("/api/v1/triage", json={"user_input": "fever " * 2000, "language": "fr"})
    assert r.status_code == 200
    _check_contract(r.json())


BODY = {"user_input": "papa ko do din se bukhar hai aur khansi bhi", "language": "auto",
        "location": {"lat": 28.54, "lng": 77.27}, "conversation_history": []}
OFFICIAL_KEYS = {"follow_up_question", "care_type", "urgency", "red_flags", "reasoning", "matched_caregivers"}


def test_default_response_has_exactly_official_keys():
    for body in (BODY, {**BODY, "user_input": "seene mein tez dard"}, {**BODY, "user_input": "tabiyat kharab"}):
        r = client.post("/api/v1/triage", json=body)
        assert set(r.json()) == OFFICIAL_KEYS


def test_debug_flag_adds_only_debug_key():
    for r in (client.post("/api/v1/triage", json={**BODY, "debug": True}),
              client.post("/api/v1/triage?debug=true", json=BODY)):
        body = r.json()
        assert set(body) == OFFICIAL_KEYS | {"debug"}
        _check_contract({k: v for k, v in body.items() if k != "debug"})
        d = body["debug"]
        for k in ("detected_language", "normalised_text", "extracted_slots", "safety_checks", "model_used",
                  "per_stage_latency_ms"):
            assert k in d, k
        assert d["detected_language"] == "hinglish" and "fever" in d["normalised_text"]
        assert d["per_stage_latency_ms"]["total"] >= 0


def test_debug_does_not_change_decision():
    a = client.post("/api/v1/triage", json=BODY).json()
    b = client.post("/api/v1/triage", json={**BODY, "debug": True}).json()
    b.pop("debug")
    assert a == b


def test_debug_emergency_trace():
    d = client.post("/api/v1/triage", json={**BODY, "user_input": "papa behosh ho gaye", "debug": True}).json()["debug"]
    assert d["model_used"] == "rules" and "unconscious" in d["safety_checks"]["red_flags"]


def test_list_caregivers():
    r = client.get("/api/v1/caregivers")
    assert r.status_code == 200 and len(r.json()) >= 10


def test_persistent_skin_rash_goes_to_dermatology():
    body = {**BODY, "user_input": "skin pe rash hai 2 hafte se", "debug": True}
    r = client.post("/api/v1/triage", json=body).json()
    assert r["care_type"] == "specialist_referral"
    specs = [m["specialty"] for m in r["debug"]["matching"]]
    assert len(r["matched_caregivers"]) >= 3 and specs[0] == "dermatology" and specs.count("dermatology") >= 3


def test_every_decided_case_returns_caregivers():
    for text in ("papa ko do din se bukhar hai aur khansi bhi", "diabetic father needs wound dressing", "beta ko halka cold hai"):
        r = client.post("/api/v1/triage", json={**BODY, "user_input": text}).json()
        assert r["care_type"] != "emergency_referral" and len(r["matched_caregivers"]) >= 3, text
