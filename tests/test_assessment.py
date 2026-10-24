"""'Your assessment' card, echoed assessment state, contradictions and the approved S0 rule."""
import csv

import pytest
from fastapi.testclient import TestClient

from app import assessment
from app.config import get_settings
from app.main import app
from app.pathways import engine, route
from app.triage import Decision

client = TestClient(app)
OFFICIAL = {"follow_up_question", "care_type", "urgency", "red_flags", "reasoning", "matched_caregivers"}
LAST = {"en": "Do not take any medicine without asking a doctor.", "hinglish": "Koi bhi dawai doctor se pooche bina na lein.",
        "hi": "कोई भी दवाई डॉक्टर से पूछे बिना न लें।"}


def _post(text, hist=None, state=None):
    body = {"user_input": text, "conversation_history": hist or [], "debug": True, "location": {"lat": 28.5245, "lng": 77.2066}}
    if state is not None:
        body["assessment_state"] = state
    return client.post("/api/v1/triage", json=body).json()


def _decide(first):
    """Answer every question with None / the first chip until a decision."""
    hist, text = [], first
    for _ in range(8):
        r = _post(text, hist)
        if not r["follow_up_question"]:
            return r
        opts = r["debug"]["followup"].get("options") or []
        hist += [{"role": "user", "content": text}, {"role": "assistant", "content": r["follow_up_question"]}]
        text = "Kuch nahi" if opts and opts[-1]["id"] == "none" else opts[0]["label"]
    return r


@pytest.mark.parametrize("text", ["papa ko do din se bukhar hai aur khansi bhi", "3 hafte se khansi, raat ko paseena",
                                  "dast ho rahe hain 2 din se", "sir dard hai, pehle bhi aisa hota hai",
                                  "khaane ke baad seene mein jalan, 24 saal"])
def test_card_on_non_emergency_decision(text):
    r = _decide(text)
    assert r["care_type"] not in (None, "emergency_referral")
    card = r["debug"]["assessment"]
    s = card["sections"]
    assert set(s) == {"symptoms", "why", "causes", "tests", "precautions", "call_112", "next"}
    assert all(i["status"] in ("present", "absent", "not_asked", "not_measured", "measured") for i in s["symptoms"]["items"])
    assert len(s["causes"]["items"]) >= 2 and "not a diagnosis" in s["causes"]["title"].lower() or "diagnosis nahi" in s["causes"]["title"].lower()
    assert all(c["strength"] in ("strong", "moderate", "weak") for c in s["causes"]["items"])
    assert s["precautions"]["items"][-1] in LAST.values()
    assert all(not assessment.is_medicine(p) for p in s["precautions"]["items"][:-1])
    assert s["call_112"]["items"]
    assert set(r) - {"debug"} == OFFICIAL


def test_no_card_on_emergency():
    r = _post("platelets 15000 reh gaye")
    assert r["care_type"] == "emergency_referral" and "assessment" not in r["debug"]


def test_card_language_and_not_measured():
    r = _decide("3 din se bahut tez bukhar hai, badan dard")
    s = r["debug"]["assessment"]["sections"]
    temp = next(i for i in s["symptoms"]["items"] if i["id"] == "temperature")
    assert temp["status"] in ("not_measured", "measured")
    assert s["precautions"]["items"][-1] == LAST["hinglish"]
    r = _decide("मुझे तीन दिन से बुखार है और खांसी")
    assert r["debug"]["assessment"]["sections"]["precautions"]["items"][-1] == LAST["hi"]


def test_cough_tb_note_never_concludes():
    r = _decide("4 hafte se khansi, raat ko paseena aur wazan kam ho gaya")
    s = r["debug"]["assessment"]["sections"]
    notes = " ".join(s["causes"]["notes"]).lower()
    assert "formal test" in notes or "pakki jaanch" in notes
    labels = [c["label"] for c in s["causes"]["items"]]
    assert len(labels) >= 2  # TB is one option among several, never the verdict
    low = r["reasoning"].lower()  # guidance about formal testing, never a conclusion
    assert ("pakka nahi" in low or "never confirm" in low) and "aapko tb" not in low and "you have tb" not in low


def test_possible_causes_flag_off(monkeypatch):
    monkeypatch.setattr(get_settings(), "show_possible_causes", False)
    r = _decide("papa ko do din se bukhar hai aur khansi bhi")
    c = r["debug"]["assessment"]["sections"]["causes"]
    assert c["shown"] is False and c["items"] == []


def test_csv_precautions_never_include_medicine():
    p = get_settings().public_dir / "symptom_severity" / "symptom_precaution.csv"
    if not p.exists():
        pytest.skip("public CSV not present")
    flagged = [x.strip() for row in csv.reader(open(p, encoding="utf-8")) for x in row[1:]
               if x.strip() and assessment.is_medicine(x)]
    assert "chew or swallow asprin" in flagged and "take otc pain reliver" in flagged and "medication" in flagged
    for d, items in assessment.csv_precautions().items():
        assert all(not assessment.is_medicine(x) and x in assessment.CSV_SAFE for x in items), d


def test_assessment_state_is_echoed_and_only_adds():
    r = _post("bukhar hai")
    st = r["debug"]["assessment_state"]
    assert st["v"] == 1 and st["category"] == "fever" and "answered" in st
    # history trimmed by the client, answer present only in the echoed state -> still counted (definite chip)
    r2 = _post("bukhar abhi bhi hai", hist=[], state={**st, "answered": {"fever.danger": ["neck"]}})
    assert r2["care_type"] == "emergency_referral"
    # a "none" in the state can never lower what the text says
    r3 = _post("bukhar aur gardan akad gayi", state={**st, "answered": {"fever.danger": ["none"]}})
    assert r3["care_type"] == "emergency_referral"


def test_contradiction_asks_once_then_uses_answer():
    hist = [{"role": "user", "content": "bukhar hai 2 din se, saans theek hai"}]
    r = _post("chalne par saans phoolti hai", hist)
    assert r["debug"]["followup"]["question_id"] == "confirm.contradiction:breathless"
    assert r["debug"]["assessment_state"]["contradictions"] == ["breathless"]
    o = engine.run(["bukhar hai 2 din se, saans theek hai", "chalne par saans phoolti hai"])
    assert o.facts["breathless"] is True  # the more severe statement is used until confirmed


def test_approved_s0_rule():
    o = engine.run(["5 din se sukhi khansi, aur kuch nahi"])
    assert o.primary.stage == "S0" and o.primary.explicit
    low = Decision("gp_teleconsult", "same_day", "tfidf_lr", 0.6, {"urgency": {"routine": 0.4, "same_day": 0.6, "immediate": 0.0}})
    high = Decision("gp_teleconsult", "same_day", "tfidf_lr", 0.8, {"urgency": {"routine": 0.2, "same_day": 0.8, "immediate": 0.0}})
    assert route.merge(low, o).urgency == "routine"
    assert route.merge(high, o).urgency == "same_day"
    o2 = engine.run(["papa ko do din se bukhar hai aur khansi bhi"])  # not S0: the model may always raise
    assert route.merge(Decision("paramedic_home_visit", "same_day", "x", 0.5, {"urgency": {"same_day": 0.5}}), o2).urgency == "same_day"
