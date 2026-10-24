"""Consistency: the same request must give the same answer (judge feedback, round 2).

25 inputs x 20 runs each: identical care_type, urgency, red_flags, follow_up_question and caregiver order.
Runs (1) with the response cache off, which tests that the decision path itself is deterministic, (2) with the
cache on, and (3) with a deliberately random fake LLM plus the cache, which shows the cache pins LLM output.
"""
import random

import pytest
from fastapi.testclient import TestClient

from app import cache, llm, llm_triage
from app.main import app

client = TestClient(app)
LOC = {"lat": 28.5245, "lng": 77.2066}
RUNS = 20

INPUTS = [
    ("Papa ko do din se bukhar hai aur khansi bhi", []),
    ("mujhe 3 din se bukhar hai", []),
    ("My mother has had a cough for 3 weeks", []),
    ("dadi ko chalne par saans phoolti hai", []),
    ("seene mein tez dard hai aur paseena aa raha hai", []),
    ("hello, papa behosh ho gaye", []),
    ("bachche ko 2 din se dast ho rahe hain", []),
    ("mummy ko 10 baar ulti hui", []),
    ("sir dard ho raha hai subah se", []),
    ("peshab mein jalan hai 2 din se", []),
    ("pet mein dard hai kal se", []),
    ("need a nurse at home for injections", []),
    ("dadaji gir gaye, ghutne mein chot hai", []),
    ("मुझे दो दिन से बुखार है", []),
    ("बच्चे को खांसी और जुकाम है", []),
    ("platelets 15000 reh gaye", []),
    ("abba ko bukhar hai", []),
    ("abba dabba jabba", []),
    ("2+2", []),
    ("mujhe xyzitis hai", []),
    ("kaise ho", []),
    ("I have had acne on the face for 6 months", []),
    ("papa ki tabiyat theek nahi hai", []),
    ("Bukhar / Fever", [{"role": "user", "content": "tabiyat kharab hai"},
                        {"role": "assistant", "content": "Mukhya pareshani kya hai? Apne shabdon mein batayein."}]),
    ("Kuch nahi", [{"role": "user", "content": "mujhe 3 din se bukhar hai"},
                   {"role": "assistant", "content": "Bukhar ke saath inme se kuch ho raha hai?"}]),
]
FIELDS = ("care_type", "urgency", "red_flags", "follow_up_question")


def _sig(text, hist):
    r = client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist, "location": LOC}).json()
    return tuple(r[f] if not isinstance(r[f], list) else tuple(r[f]) for f in FIELDS) + \
        (tuple(m["caregiver_id"] for m in r["matched_caregivers"]),)


def consistency_rate() -> float:
    same = 0
    for text, hist in INPUTS:
        sigs = {_sig(text, hist) for _ in range(RUNS)}
        same += len(sigs) == 1
    return same / len(INPUTS)


def test_suite_size():
    assert len(INPUTS) >= 25 and RUNS >= 20


def test_deterministic_without_cache_llm_disabled(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    monkeypatch.setattr(cache, "response_cache", lambda: cache.ResponseCache(0))
    assert consistency_rate() == 1.0


def test_identical_with_cache(monkeypatch):
    rc = cache.ResponseCache(900)
    monkeypatch.setattr(cache, "response_cache", lambda: rc)
    assert consistency_rate() == 1.0
    assert rc.hits >= len(INPUTS) * (RUNS - 1)


def test_cache_pins_a_random_llm(monkeypatch):
    """Even a non-deterministic LLM cannot change a repeated answer: the first answer is served again."""
    rng = random.Random()

    def noisy(text, lang, history=""):
        from app.triage import Decision
        return Decision(rng.choice(["gp_teleconsult", "nurse_home_visit", "specialist_referral"]),
                        rng.choice(["routine", "same_day"]), "llm", 0.9, None)

    monkeypatch.setattr(llm_triage, "llm_decision", noisy)
    rc = cache.ResponseCache(900)
    monkeypatch.setattr(cache, "response_cache", lambda: rc)
    assert consistency_rate() == 1.0


def test_cache_key_changes_with_state():
    from app.schemas import TriageRequest
    a = TriageRequest(user_input="mujhe bukhar hai")
    b = TriageRequest(user_input="  Mujhe   bukhar hai ")
    c = TriageRequest(user_input="mujhe bukhar hai", assessment_state={"x": 1})
    d = TriageRequest(user_input="mujhe bukhar hai", location=LOC)
    assert cache.key(a, False) == cache.key(b, False)  # normalised input
    assert len({cache.key(a, False), cache.key(c, False), cache.key(d, False), cache.key(a, True)}) == 4


@pytest.mark.parametrize("ttl", [0])
def test_cache_off(ttl):
    rc = cache.ResponseCache(ttl)
    rc.put("k", {"a": 1})
    assert rc.get("k") is None
