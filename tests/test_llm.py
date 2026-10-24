from app import llm, llm_triage
from app.triage import Decision, combine


def test_validate_rejects_bad_labels():
    assert llm_triage.validate({"care_type": "hospital", "urgency": "routine"}) is None
    assert llm_triage.validate("nope") is None
    ok = llm_triage.validate({"care_type": "gp_teleconsult", "urgency": "routine", "red_flags": ["made_up", "chest_pain"],
                              "reasoning": "Mild cold for 2 days."})
    assert ok["red_flags"] == ["chest_pain"] and ok["reasoning"]


def test_reasoning_with_diagnosis_is_dropped():
    out = llm_triage.validate({"care_type": "gp_teleconsult", "urgency": "routine", "red_flags": [],
                               "reasoning": "This looks like pneumonia, take paracetamol."})
    assert out["reasoning"] == ""


def test_llm_unavailable_returns_none(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    assert llm_triage.llm_decision("fever", "en") is None


def test_llm_mocked(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {"care_type": "paramedic_home_visit", "urgency": "same_day",
                                                           "red_flags": [], "reasoning": "Fever with cough for 2 days."})
    d = llm_triage.llm_decision("papa ko do din se bukhar hai", "hinglish")
    assert d.care_type == "paramedic_home_visit" and d.urgency == "same_day"


def test_combine_takes_more_urgent():
    local = Decision("gp_teleconsult", "same_day", "a")
    l = Decision("gp_teleconsult", "routine", "llm")
    assert combine(local, l).urgency == "same_day"
    assert combine(Decision("emergency_referral", "immediate", "a"), l).care_type == "emergency_referral"
