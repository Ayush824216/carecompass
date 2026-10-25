"""Live-chat fixes, as multi-turn transcripts: women's health pathway, pregnancy as context in every pathway,
several complaints in one message, treatment questions, bleeding amount + source, "aap" wording and named conditions."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pathways.engine import TREATMENT_LINE

client = TestClient(app)
LOC = {"lat": 28.5245, "lng": 77.2066}
EMERGENCY = "emergency_referral"


def _post(text, hist=None):
    r = client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist or [], "location": LOC,
                                            "debug": True})
    assert r.status_code == 200
    return r.json()


def _chat(start, answers=()):
    """Run a conversation; returns (final response, [(question_id, question_text, answer)])."""
    hist, text, r, log = [], start, None, []
    answers = list(answers)
    for _ in range(10):
        r = _post(text, hist)
        if not r["follow_up_question"]:
            return r, log
        qid = r["debug"]["followup"].get("question_id")
        opts = r["debug"]["followup"].get("options") or []
        hist += [{"role": "user", "content": text}, {"role": "assistant", "content": r["follow_up_question"]}]
        if answers:
            text = answers.pop(0)
        elif qid == "common.age":
            text = "18–64 saal"
        else:
            text = next((o["label"] for o in opts if o["id"] == "none"), opts[-1]["label"] if opts else "Nahi")
        log.append((qid, r["follow_up_question"], text))
    return r, log


def _specs(r):
    return [m.get("specialty") for m in r["debug"].get("matching", [])]


# ---------------------------------------------------------------- 1. women's health pathway
@pytest.mark.parametrize("start", ["mujhe periods mein bahut dard hota hai", "I have irregular periods",
                                   "safed paani aata hai badboo ke saath", "मेनोपॉज़ के बाद बहुत गर्मी लगती है"])
def test_routine_gynae_goes_to_gynaecologist(start):
    r, log = _chat(start)
    assert log[0][0] == "women.danger"  # danger screen first
    assert r["care_type"] == "specialist_referral" and r["urgency"] in ("routine", "same_day")
    assert _specs(r)[0] == "gynecology"


@pytest.mark.parametrize("start,answers", [
    ("periods bahut heavy hain, har ghante pad bheeg jaata hai", []),
    ("periods mein bahut khoon aa raha hai aur chakkar aa rahe hain", []),
    ("period 2 mahine se nahi aaya aur pet ke neeche left side mein tez dard hai", []),
    ("missed my period and severe pain on the right side of my lower belly", []),
    ("पीरियड नहीं आया और पेट के नीचे एक तरफ तेज़ दर्द है", []),
    ("delivery ke baad 2 hafte ho gaye, bahut khoon aa raha hai aur thakke", []),
    ("periods bahut zyada ho rahe hain", ["Har ghante pad bheeg jaata hai"]),
    ("mujhe periods mein dard hai", ["Pet ke neeche ek taraf tez dard", "Period late hai, ho sakta hai"]),
])
def test_womens_red_flags_are_emergencies(start, answers):
    r, _ = _chat(start, answers)
    assert r["care_type"] == EMERGENCY and r["urgency"] == "immediate"


@pytest.mark.parametrize("start", ["bukhar hai aur pet ke neeche dard hai, white discharge bhi",
                                   "I have fever and pelvic pain since yesterday"])
def test_fever_with_pelvic_pain_is_same_day(start):
    r, _ = _chat(start)
    assert r["care_type"] != EMERGENCY and r["urgency"] == "same_day"


def test_gynaecologists_in_demo_caregivers():
    from app.data_adapter import load_caregivers
    assert sum(1 for c in load_caregivers() if c.get("specialty") == "gynecology") >= 6


# ---------------------------------------------------------------- 2. pregnancy is context in every pathway
@pytest.mark.parametrize("start,not_routine", [("main pregnant hoon, bukhar hai", True), ("I am pregnant and have a cough", False),
                                               ("main pregnant hoon, peshab mein jalan hai", True)])
def test_pregnancy_weeks_asked_once_and_gynae_preferred(start, not_routine):
    r, log = _chat(start)
    asked = [q for q, _, _ in log]
    assert asked.count("common.pregnancy_weeks") == 1
    assert r["care_type"] in ("specialist_referral", EMERGENCY)
    if r["care_type"] == "specialist_referral":
        assert _specs(r)[0] == "gynecology"
        assert r["urgency"] != "routine" or not not_routine


@pytest.mark.parametrize("start,answers", [
    ("main 5 mahine pregnant hoon, sar dard aur dhundhla dikh raha hai", []),
    ("I am pregnant and bleeding a little", []),
    ("pregnant hoon, pet mein bahut tez dard hai", []),
])
def test_pregnancy_warning_signs_are_never_routine(start, answers):
    r, _ = _chat(start, answers)
    assert r["care_type"] == EMERGENCY


def test_pregnancy_weeks_not_asked_when_given():
    _, log = _chat("main 6 mahine ki pregnant hoon, bukhar hai")
    assert "common.pregnancy_weeks" not in [q for q, _, _ in log]


@pytest.mark.parametrize("start,urgency", [
    ("main pregnant hoon aur bahut rona aata hai, mood swings", "same_day"),
    ("delivery ke baad se mood swings rehte hain", None),
])
def test_perinatal_mood_support(start, urgency):
    r, _ = _chat(start)
    assert r["care_type"] == "specialist_referral"
    assert {"psychiatry", "gynecology"} <= set(_specs(r))
    assert "perinatal" in r["reasoning"].lower()
    if urgency:
        assert r["urgency"] == urgency


# ---------------------------------------------------------------- 3. several complaints in one message
@pytest.mark.parametrize("start,lang_word", [
    ("mujhe periods mein dard hai, mood swings hote hain aur rona aata hai", "bataya"),
    ("I have painful periods and I keep crying", "also mentioned"),
])
def test_other_complaints_acknowledged(start, lang_word):
    r, _ = _chat(start)
    others = r["debug"].get("other_concerns") or []
    assert [o["pathway"] for o in others] == ["mood"]
    assert lang_word in r["reasoning"].lower() or lang_word in r["reasoning"]
    assert others[0]["start"]  # the client can start the next conversation from it


def test_most_urgent_complaint_handled_first():
    r, _ = _chat("halki khansi hai aur periods mein har ghante pad bheeg jaata hai")
    assert r["care_type"] == EMERGENCY


# ---------------------------------------------------------------- 4. treatment questions
@pytest.mark.parametrize("start,spec", [("mujhe cancer hai, ilaaj kaise hoga?", "oncology"),
                                        ("sugar ki kaunsi dawai lun?", "endocrinology"),
                                        ("how to cure my asthma", "pulmonology")])
def test_treatment_question_kind_reply_then_triage(start, spec):
    first = _post(start)
    assert first["follow_up_question"] and first["debug"]["domain_class"] == "health_request"
    r, _ = _chat(start)
    assert r["reasoning"].startswith(TREATMENT_LINE["hinglish"]) or r["reasoning"].startswith(TREATMENT_LINE["en"])
    assert spec in _specs(r)


def test_medicine_question_without_a_problem_gets_kind_redirect():
    r = _post("kya dawai lun?")
    assert r["care_type"] is None and r["follow_up_question"].lower().startswith(("ilaaj", "only your doctor"))


# ---------------------------------------------------------------- 5. bleeding: amount + source
@pytest.mark.parametrize("start", ["naak se khoon aa raha hai", "potty mein khoon aaya", "I have some bleeding from a cut"])
def test_bleeding_asks_amount_and_source_first(start):
    r = _post(start)
    assert r["debug"]["followup"]["question_id"] == "common.bleeding"


@pytest.mark.parametrize("start", ["naak se khoon aa raha hai", "मुँह से खून आया"])
def test_heavy_bleeding_answer_is_emergency(start):
    r, _ = _chat(start, ["Bahut zyada, ruk nahi raha"])
    assert r["care_type"] == EMERGENCY


def test_small_bleeding_is_not_emergency():
    r, log = _chat("naak se khoon aa raha hai", ["Thoda sa, kuch boondein, Naak se"])
    assert r["care_type"] != EMERGENCY
    assert [q for q, _, _ in log].count("common.bleeding") == 1


# ---------------------------------------------------------------- 6. wording
@pytest.mark.parametrize("start", ["mujhe bukhar hai", "I have a headache", "मुझे खांसी है"])
def test_self_reference_uses_aap(start):
    _, log = _chat(start)
    age = [t for q, t, _ in log if q == "common.age"]
    assert age and "mareez" not in age[0].lower() and "patient" not in age[0].lower() and "मरीज़" not in age[0]


def test_other_person_keeps_patient_wording():
    _, log = _chat("papa ko bukhar hai")
    age = [t for q, t, _ in log if q == "common.age"]
    assert age and "mareez" in age[0].lower()


@pytest.mark.parametrize("start,word,absent", [("mujhe HIV hai, bukhar hai 3 din se", "HIV", "cancer"),
                                               ("mujhe sugar hai, bukhar hai 3 din se", "sugar", "HIV")])
def test_reason_names_only_the_condition_said(start, word, absent):
    r, _ = _chat(start)
    assert word.lower() in r["reasoning"].lower() and absent.lower() not in r["reasoning"].lower()
