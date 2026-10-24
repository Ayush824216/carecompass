from app import llm, llm_triage
from app.triage import Decision, combine


def test_validate_rejects_bad_labels():
    assert llm_triage.validate({"care_type": "hospital", "urgency": "routine"}) is None
    assert llm_triage.validate("nope") is None
    ok = llm_triage.validate({"care_type": "gp_teleconsult", "urgency": "routine", "red_flags": ["chest_pain"]})
    assert ok["red_flags"] == ["chest_pain"]


def test_unknown_values_or_keys_reject_everything():
    base = {"care_type": "gp_teleconsult", "urgency": "routine"}
    assert llm_triage.validate({**base, "red_flags": ["made_up", "chest_pain"]}) is None
    assert llm_triage.validate({**base, "symptom_ids": ["fever", "xyzitis"]}) is None
    assert llm_triage.validate({**base, "pattern_ids": ["dengue_like_madeup"]}) is None
    assert llm_triage.validate({**base, "diagnosis": "pneumonia"}) is None
    assert llm_triage.validate({**base, "symptom_ids": ["fever"], "pattern_ids": ["viral"]})["symptom_ids"] == ["fever"]


def test_llm_free_text_never_reaches_the_user():
    out = llm_triage.validate({"care_type": "gp_teleconsult", "urgency": "routine", "red_flags": [],
                               "reasoning": "This looks like pneumonia, take paracetamol."})
    assert "reasoning" not in out


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
