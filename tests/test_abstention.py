"""Abstention: no clinical question without health evidence in the user's own words (judge feedback, round 2)."""
import pytest
from fastapi.testclient import TestClient

from app import domain_guard as dg
from app import evidence
from app.main import app

client = TestClient(app)


def _post(text, hist=None):
    return client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist or [], "debug": True}).json()


NON_HEALTH = [
    ("abba dabba jabba", dg.UNCLEAR), ("asdfgh", dg.UNCLEAR), ("zzz", dg.UNCLEAR), ("papa", dg.UNCLEAR),
    ("mummy ko", dg.UNCLEAR), ("abba", dg.UNCLEAR), ("la la la la", dg.UNCLEAR), ("\U0001F600\U0001F600\U0001F600", dg.UNCLEAR),
    ("कखग घचछ", dg.UNCLEAR), ("2+2", dg.MATH), ("12*7=?", dg.MATH), ("what is 5 times 3", dg.MATH),
    ("print('hello')", dg.MATH), ("def f(x): return x", dg.MATH), ("mujhe xyzitis hai", dg.UNKNOWN_TERM),
    ("I have blorbosis", dg.UNKNOWN_TERM), ("who won the cricket match yesterday", dg.OFF_TOPIC),
    ("kaise ho", dg.GREETING), ("tum kaun ho", dg.GREETING), ("early morning walk", dg.UNCLEAR),
]


@pytest.mark.parametrize("text,expected", NON_HEALTH)
def test_class(text, expected):
    assert dg.classify(text) == expected


@pytest.mark.parametrize("text", [t for t, _ in NON_HEALTH])
def test_never_a_clinical_question(text):
    r = _post(text)
    d = r["debug"]
    assert r["care_type"] is None and r["urgency"] is None and r["matched_caregivers"] == []
    assert d["domain_class"] != dg.HEALTH and d["followup"]["question_id"] is None
    assert r["follow_up_question"] in dg.REDIRECT_TEXTS


def test_person_mention_is_not_evidence():
    for text in ("abba", "papa", "mummy", "dadi ji", "my father", "patient", "मरीज़"):
        assert not evidence.has_evidence([text]), text


def test_father_with_fever_is_health():
    r = _post("abba ko bukhar hai")
    assert r["debug"]["domain_class"] == dg.HEALTH
    assert r["debug"]["extracted_slots"]["patient"] == "abba"
    assert any(e["label"] == "fever" and e["text"] == "bukhar" for e in r["debug"]["evidence"])


def test_red_flag_in_messy_message_is_emergency():
    for text in ("hello, papa behosh ho gaye", "asdf qwer papa behosh ho gaye", "2+2 seene mein tez dard hai"):
        r = _post(text)
        assert r["care_type"] == "emergency_referral" and r["urgency"] == "immediate", text


def test_specific_messages():
    assert _post("abba dabba jabba")["follow_up_question"] == dg.REDIRECTS[dg.UNCLEAR]["en"]
    assert _post("mujhe xyzitis hai")["follow_up_question"] == "Main is naam ko nahi pehchaanta. Apne symptoms batayein."
    assert _post("2+2")["follow_up_question"] == dg.REDIRECTS[dg.MATH]["en"]


def test_give_up_after_three_unclear_turns():
    hist = []
    for i, text in enumerate(("abba dabba jabba", "2+2", "asdfgh")):
        r = _post(text, hist)
        if i < 2:
            assert r["follow_up_question"] in dg.REDIRECT_TEXTS
            hist += [{"role": "user", "content": text}, {"role": "assistant", "content": r["follow_up_question"]}]
    assert r["debug"]["domain_class"] == dg.GIVE_UP and r["follow_up_question"] is None and r["care_type"] is None
    assert "112" in r["reasoning"]
    hist.append({"role": "user", "content": "asdfgh"})
    # a real complaint afterwards is handled normally, and the redirects did not use up clinical questions
    r = _post("mujhe khansi hai", hist)
    assert r["debug"]["domain_class"] == dg.HEALTH and r["debug"]["followup"]["asked_so_far"] == 0


def test_evidence_spans_point_at_user_text():
    text = "Papa ko 3 din se bukhar hai aur khansi bhi"
    for sp in evidence.find([text]):
        assert text[sp.start:sp.end] == sp.text
