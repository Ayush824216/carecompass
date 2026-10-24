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
