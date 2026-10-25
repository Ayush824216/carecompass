"""The patient is an animal -> "please contact a vet" (no clinical question, no emergency, not counted as a question).
A person bitten, scratched or stung by an animal is a normal human health request."""
import pytest
from fastapi.testclient import TestClient

from app import domain_guard
from app.main import app

client = TestClient(app)
LOC = {"lat": 28.5245, "lng": 77.2066}


def _post(text, hist=None):
    r = client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist or [], "location": LOC,
                                            "debug": True})
    assert r.status_code == 200
    return r.json()


def _final(start):
    hist, text, r = [], start, None
    for _ in range(8):
        r = _post(text, hist)
        if not r["follow_up_question"]:
            return r
        q = r["debug"]["followup"]
        opts = q.get("options") or []
        hist += [{"role": "user", "content": text}, {"role": "assistant", "content": r["follow_up_question"]}]
        text = "18–64 saal" if q.get("question_id") == "common.age" else \
            next((o["label"] for o in opts if o["id"] == "none"), opts[-1]["label"] if opts else "Nahi")
    return r


@pytest.mark.parametrize("text,lang", [
    ("kutte ke dil mein heart attack", "hinglish"), ("ullu ki aankh mein dard", "hinglish"), ("meri billi ko bukhar", "hinglish"),
    ("my dog is vomiting", "en"), ("gaay bimaar hai", "hinglish"), ("मेरी बिल्ली को बुखार है", "hi"),
])
def test_animal_patient_gets_vet_reply(text, lang):
    r = _post(text)
    assert r["follow_up_question"] is None and r["care_type"] is None and r["urgency"] is None and not r["red_flags"]
    assert r["reasoning"] == domain_guard.VET_TEXT[lang]
    assert r["debug"]["domain_class"] == "animal_patient"


def test_vet_reply_is_not_counted_and_does_not_leak_into_human_triage():
    hist = [{"role": "user", "content": "kutte ke dil mein heart attack"},
            {"role": "assistant", "content": domain_guard.VET_TEXT["hinglish"]}]
    r = _post("papa ko bukhar hai", hist)
    assert r["care_type"] != "emergency_referral" and r["follow_up_question"]
    assert r["debug"]["followup"]["asked_so_far"] == 0


@pytest.mark.parametrize("text,urgency", [("kutte ne kaata", "same_day"), ("billi ne nakhoon maara", "same_day"),
                                          ("a dog bit my son", "same_day"), ("madhumakkhi ne kaata", None)])
def test_animal_bites_are_human_health(text, urgency):
    assert not domain_guard.is_animal_patient(text)
    r = _final(text)
    assert r["care_type"] not in (None, "emergency_referral")
    if urgency:
        assert r["urgency"] == urgency


@pytest.mark.parametrize("text", ["saanp ne kaata", "snake bit my father", "बिच्छू ने काटा"])
def test_snake_and_scorpion_bites_are_emergencies(text):
    assert _post(text)["care_type"] == "emergency_referral"
