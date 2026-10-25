"""Anatomically impossible red flags ("kidney mein heart attack") get one confirmation with 112 / 108 on screen, not an
emergency by keyword. "Haan" -> emergency; "Nahi" -> normal triage. Clear red flags still go straight to emergency."""
import pytest
from fastapi.testclient import TestClient

from app import safety
from app.main import app

client = TestClient(app)
LOC = {"lat": 28.5245, "lng": 77.2066}
EMERGENCY = "emergency_referral"


def _post(text, hist=None):
    r = client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist or [], "location": LOC,
                                            "debug": True})
    assert r.status_code == 200
    return r.json()


IMPOSSIBLE = [
    "kidney mein heart attack", "brain mein saans nahi aa rahi", "pair mein heart attack",  # reported
    "heart attack in my kidney", "aankh mein heart attack aa gaya", "dimaag mein saans ruk gayi",
    "दिमाग में साँस नहीं आ रही", "pet mein lakwa maar gaya",
]


@pytest.mark.parametrize("text", IMPOSSIBLE)
def test_impossible_site_asks_one_confirmation(text):
    r = _post(text)
    assert r["care_type"] is None and r["urgency"] is None
    fu = r["debug"]["followup"]
    assert fu["kind"] == "site_confirm" and fu["question_id"].startswith("confirm.site:")
    assert [o["id"] for o in fu["options"]] == ["yes", "no"]
    assert r["follow_up_question"] in {t for v in safety.SITE_CONFIRM.values() for t in v.values()}


@pytest.mark.parametrize("text", ["kidney mein heart attack", "brain mein saans nahi aa rahi", "दिमाग में साँस नहीं आ रही"])
def test_yes_opens_emergency(text):
    r1 = _post(text)
    hist = [{"role": "user", "content": text}, {"role": "assistant", "content": r1["follow_up_question"]}]
    yes = next(o["label"] for o in r1["debug"]["followup"]["options"] if o["id"] == "yes")
    r2 = _post(yes, hist)
    assert r2["care_type"] == EMERGENCY and r2["urgency"] == "immediate" and r2["red_flags"]


@pytest.mark.parametrize("text", ["kidney mein heart attack", "pair mein heart attack", "brain mein saans nahi aa rahi"])
def test_no_continues_normal_triage(text):
    r1 = _post(text)
    hist = [{"role": "user", "content": text}, {"role": "assistant", "content": r1["follow_up_question"]}]
    no = next(o["label"] for o in r1["debug"]["followup"]["options"] if o["id"] == "no")
    r2 = _post(no, hist)
    assert r2["care_type"] != EMERGENCY
    assert r2["debug"]["followup"].get("kind") != "site_confirm"  # asked once only


@pytest.mark.parametrize("text", ["seene mein heart attack jaisa dard", "saans nahi aa rahi", "papa ko heart attack aaya",
                                  "pair mein dard aur saans nahi aa rahi", "kidney mein heart attack, aur seene mein dard bhi",
                                  "I can't breathe", "सीने में तेज़ दर्द है"])
def test_clear_red_flags_still_go_straight_to_emergency(text):
    r = _post(text)
    assert r["care_type"] == EMERGENCY and not r["follow_up_question"]


def test_aag_inside_a_word_is_not_a_burn():
    assert "severe_burns" not in safety.check(["dimaag mein dard hai"]).red_flags
    assert "severe_burns" in safety.check(["ghar mein aag lag gayi, papa jal gaye"]).red_flags
