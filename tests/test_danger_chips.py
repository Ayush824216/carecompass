"""Danger chips: one sign per chip, definite_S3 vs needs_confirmation, and the one extra confirmation question."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pathways import engine

client = TestClient(app)
CFG = Path(__file__).resolve().parents[1] / "config" / "pathways"
SEVERITIES = {None, "definite_S3", "needs_confirmation"}


def _post(text, hist=None):
    return client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist or [], "debug": True,
                                                "location": {"lat": 28.5245, "lng": 77.2066}}).json()


def _turns(*steps):
    """Run a conversation: first user text, then answers to each question. Returns (last response, history)."""
    hist, r = [], None
    for text in steps:
        r = _post(text, hist)
        hist += [{"role": "user", "content": text}]
        if r["follow_up_question"]:
            hist += [{"role": "assistant", "content": r["follow_up_question"]}]
    return r, hist


def _questions():
    _, pathways, _ = engine.load()
    for p in pathways.values():
        for q in p.cfg["questions"]:
            yield p.id, q


def test_every_chip_has_a_known_severity():
    for pid, q in _questions():
        for c in q["chips"]:
            assert c.get("severity") in SEVERITIES, (pid, q["id"], c["id"])


def test_danger_and_confirmation_chips_carry_one_sign_each():
    _, _, signs = engine.load()
    for pid, q in _questions():
        if q.get("kind") not in ("danger", "confirm"):
            continue
        for c in q["chips"]:
            assert " / " not in c["label"]["en"] and " + " not in c["label"]["en"], (q["id"], c["label"]["en"])
            assert len([k for k in c["facts"] if k in signs]) <= 1, (q["id"], c["id"])


def test_confirmation_chips_and_needs_confirmation_chips_are_consistent():
    """Every needs_confirmation chip's sign triggers at least one confirmation question."""
    confirms = [q for _, q in _questions() if q.get("kind") == "confirm"]
    for pid, q in _questions():
        for c in q["chips"]:
            if c.get("severity") == "needs_confirmation":
                sign = next(iter(c["facts"]))
                assert any(sign in q2["only_if"] for q2 in confirms), (q["id"], c["id"])


def test_definite_chip_goes_to_emergency_at_once():
    r, _ = _turns("bukhar hai", "Gardan akad gayi")
    assert r["care_type"] == "emergency_referral" and r["follow_up_question"] is None


def test_headache_chip_asks_one_confirmation_then_continues():
    r, hist = _turns("bukhar hai", "Bahut tez sir dard")
    fu = r["debug"]["followup"]
    assert fu["question_id"] == "fever.confirm_headache" and fu["confirmation"] is True
    assert fu["asked_so_far"] == 1  # the confirmation does not count towards the 4
    r2 = _post("Kuch nahi", hist)
    assert r2["care_type"] != "emergency_referral"
    assert r2["debug"]["followup"].get("question_id") != "fever.confirm_headache"


def test_confirmation_with_definite_answer_is_emergency():
    r, _ = _turns("bukhar hai", "Bahut tez sir dard", "Gardan aage nahi jhukti")
    assert r["care_type"] == "emergency_referral"


@pytest.mark.parametrize("answer,emergency", [
    ("Baithe-baithe bhi saans phoolti hai", True), ("Hont ya naakhun neele", True),
    ("Sirf chalne ya seedhi chadhne par", False),
])
def test_breathing_confirmation(answer, emergency):
    r, _ = _turns("bukhar hai", "Chalne par saans phoolti hai", answer)
    assert (r["care_type"] == "emergency_referral") is emergency


def test_breathless_at_rest_in_text_is_emergency_without_questions():
    r = _post("aaram mein bhi saans nahi aa rahi")
    assert r["care_type"] == "emergency_referral" and r["follow_up_question"] is None


def test_text_sign_triggers_the_confirmation_directly():
    r = _post("bukhar aur bahut tez sir dard hai")
    assert r["debug"]["followup"]["question_id"] == "fever.confirm_headache"


def test_only_one_confirmation_and_at_most_four_clinical_questions():
    text, hist, confirms, clinical = "bukhar hai", [], 0, 0
    answers = iter(["Chalne par saans phoolti hai, Bahut tez sir dard", "Sirf chalne ya seedhi chadhne par"])
    for _ in range(8):
        r = _post(text, hist)
        if not r["follow_up_question"]:
            break
        fu = r["debug"]["followup"]
        confirms += bool(fu.get("confirmation"))
        clinical += not fu.get("confirmation")
        hist += [{"role": "user", "content": text}, {"role": "assistant", "content": r["follow_up_question"]}]
        text = next(answers, "Kuch nahi" if fu.get("options") and fu["options"][-1]["id"] == "none" else fu["options"][0]["label"])
    assert r["care_type"] is not None and confirms <= 1 and clinical <= 4


def test_black_stool_confirmation_iron_keeps_s2():
    r, _ = _turns("dast ho rahe hain", "Kaali chipchipi potty", "Haan, iron ki goli")
    assert r["care_type"] != "emergency_referral"
    r, _ = _turns("dast ho rahe hain", "Kaali chipchipi potty", "Iron ki goli nahi")
    assert r["care_type"] == "emergency_referral"


def test_head_injury_confirmation():
    r, _ = _turns("sir dard hai", "Sir par chot")
    assert r["debug"]["followup"]["question_id"] == "headache.confirm_injury"
    r, _ = _turns("sir dard hai", "Sir par chot", "Ulti hui")
    assert r["care_type"] == "emergency_referral"


def test_chip_options_expose_severity():
    r = _post("bukhar hai")
    opts = r["debug"]["followup"]["options"]
    assert {o["severity"] for o in opts} <= SEVERITIES and opts[-1]["id"] == "none"
    assert any(o["severity"] == "definite_S3" for o in opts) and any(o["severity"] == "needs_confirmation" for o in opts)


def test_official_schema_unchanged():
    r = client.post("/api/v1/triage", json={"user_input": "bukhar hai"}).json()
    assert set(r) == {"follow_up_question", "care_type", "urgency", "red_flags", "reasoning", "matched_caregivers"}
