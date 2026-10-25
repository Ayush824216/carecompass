"""Local intent / plausibility (no LLM): jokes and song lines, heartbreak idioms, animal / deceased / non-living
"patients", hypotheticals. A red-flag word is never dismissed: one confirmation with 112 / 108, and clear red flags
without a joke context still go straight to emergency."""
import pytest
from fastapi.testclient import TestClient

from app import domain_guard, safety
from app.main import app

client = TestClient(app)
LOC = {"lat": 28.5245, "lng": 77.2066}
EMERGENCY = "emergency_referral"
CONFIRMS = {safety.confirm_text(f, l) for f in safety.FLAG_LABELS for l in ("en", "hi", "hinglish")}


def _post(text, hist=None):
    r = client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist or [], "location": LOC,
                                            "debug": True})
    assert r.status_code == 200
    return r.json()


def _answer(text, label):
    r1 = _post(text)
    hist = [{"role": "user", "content": text}, {"role": "assistant", "content": r1["follow_up_question"]}]
    return r1, _post(label, hist)


@pytest.mark.parametrize("text", ["dil mein mere hai dard disco", "dil to pagal hai 😂", "tujhe dekha to ye jaana sanam",
                                  "mere phone ko bukhar hai"])
def test_joke_lyric_absurd_gets_playful_reply_not_a_question(text):
    r = _post(text)
    assert r["follow_up_question"] is None and r["care_type"] is None and not r["red_flags"]
    assert r["reasoning"] in {v for k in (domain_guard.JOKE, domain_guard.ABSURD) for v in domain_guard.INTENT_TEXT[k].values()}


@pytest.mark.parametrize("text", ["mera dil toot gaya", "my heart is broken", "मेरा दिल टूट गया"])
def test_heartbreak_idiom_offers_mood_support_not_cardiac(text):
    r = _post(text)
    assert r["care_type"] is None and not r["red_flags"] and r["debug"]["domain_class"] == domain_guard.HEARTBREAK
    assert "mood" in r["reasoning"].lower() or "मूड" in r["reasoning"]


def test_animal_patient_gets_vet_reply():
    r = _post("kutte ke dil mein heart attack")
    assert r["care_type"] is None and r["debug"]["domain_class"] == "animal_patient"


@pytest.mark.parametrize("text,no_reply", [
    ("mari hui dadi ko heart attack", domain_guard.DECEASED),
    ("dil mein dard hai disco 😂", domain_guard.JOKE),
    ("uski yaad mein dil mein dard hai", domain_guard.HEARTBREAK),
])
def test_red_flag_in_unlikely_context_is_confirmed_never_dismissed(text, no_reply):
    r1, r_no = _answer(text, "Nahi")
    assert r1["care_type"] is None and r1["follow_up_question"] in CONFIRMS
    assert r1["debug"]["followup"]["kind"] == "site_confirm"  # 112 / 108 shown with it
    assert r_no["care_type"] != EMERGENCY and r_no["reasoning"] == domain_guard.INTENT_TEXT[no_reply]["hinglish"]
    _, r_yes = _answer(text, "Haan, abhi")
    assert r_yes["care_type"] == EMERGENCY


def test_hypothetical_is_not_an_emergency():
    r = _post("agar saans ruk jaaye to?")
    assert r["care_type"] != EMERGENCY and not r["red_flags"]


@pytest.mark.parametrize("text,emergency", [
    ("seene mein dard ho raha hai", True), ("papa ko abhi heart attack aaya hai", True), ("saans nahi aa rahi", True),
    ("haha seene mein dard ho raha hai abhi", True), ("dadi ki death ke baad se papa ko seene mein dard rehta hai", True),
    ("mere dil ki dhadkan bahut tez hai", False), ("dadi ko 3 din se bukhar hai", False), ("gaana gaate gaate gala kharab ho gaya", False),
    ("breakup ke baad se neend nahi aati aur bahut udaas rehti hoon", False), ("lol mujhe 3 din se bukhar hai", False),
])
def test_real_cases_are_never_dismissed(text, emergency):
    r = _post(text)
    assert r["debug"]["domain_class"] == "health_request"
    assert r["reasoning"] not in {v for m in domain_guard.INTENT_TEXT.values() for v in m.values()}
    if emergency:
        assert r["care_type"] == EMERGENCY
    else:
        assert r["care_type"] != EMERGENCY and (r["follow_up_question"] or r["care_type"])
