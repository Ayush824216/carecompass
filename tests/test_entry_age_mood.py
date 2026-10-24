"""Entry chips open a pathway (never emergency by themselves), the early age question, age in matching, and the
mood / mental-health pathway with its always-asked self-harm safety question."""
import pytest
from fastapi.testclient import TestClient

from app import safety
from app.main import app

client = TestClient(app)
LOC = {"lat": 28.5245, "lng": 77.2066}


def _post(text, hist=None):
    return client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist or [], "location": LOC,
                                                "debug": True}).json()


def _flow(start, answers):
    """Answer each question in order; when answers run out, 'none' chip (or the first chip) until a decision."""
    hist, text, qids, r = [], start, [], None
    answers = list(answers)
    for _ in range(10):
        r = _post(text, hist)
        qids.append(r["debug"]["followup"].get("question_id"))
        if not r["follow_up_question"]:
            break
        opts = r["debug"]["followup"].get("options") or []
        hist += [{"role": "user", "content": text}, {"role": "assistant", "content": r["follow_up_question"]}]
        if answers:
            text = answers.pop(0)
        elif qids[-1] == "common.age":
            text = "18–64 saal"
        else:
            text = next((o["label"] for o in opts if o["id"] == "none"), opts[-1]["label"] if opts else "Nahi")
    return r, qids


# ---------------------------------------------------------------- entry chips
ENTRY = ["Bukhar / Fever", "Saans ki dikkat", "साँस की दिक्कत", "Chot lagi / Injury", "Buzurg ki dekhbhal",
         "Bacche ki tabiyat", "Dawai/injection ke liye nurse", "Mann / mood", "मन / मूड"]


@pytest.mark.parametrize("chip", ENTRY)
def test_entry_chip_never_emergency(chip):
    assert _post(chip)["care_type"] != "emergency_referral"


def test_breathing_chip_asks_danger_first():
    r = _post("Saans ki dikkat")
    d = r["debug"]["followup"]
    assert d["question_id"] == "breathing.danger" and d["asked_so_far"] == 0
    labels = [o["label"] for o in d["options"]]
    assert labels == ["Aaram mein bhi / bol nahi pa rahe", "Chalne par", "Hoth neele", "Seene mein dard", "Kuch nahi"]
    sev = {o["label"]: o["severity"] for o in d["options"]}
    assert sev["Chalne par"] is None and sev["Hoth neele"] == "definite_S3"


@pytest.mark.parametrize("answer,emergency", [("Aaram mein bhi / bol nahi pa rahe", True), ("Hoth neele", True),
                                              ("Seene mein dard", True), ("Chalne par", False), ("Kuch nahi", False)])
def test_only_definite_breathing_answers_are_emergency(answer, emergency):
    r, _ = _flow("Saans ki dikkat", [answer])
    assert (r["care_type"] == "emergency_referral") is emergency


@pytest.mark.parametrize("text", ["saans nahi aa rahi", "I cannot breathe", "साँस नहीं आ रही"])
def test_typed_breathing_emergency_still_immediate(text):
    r = _post(text)
    assert r["care_type"] == "emergency_referral" and r["follow_up_question"] is None


# ---------------------------------------------------------------- age
def test_age_asked_early_and_not_counted():
    r = _post("Kuch nahi", [{"role": "user", "content": "mujhe bukhar hai"},
                            {"role": "assistant", "content": "Bukhar ke saath inme se kuch ho raha hai?"}])
    d = r["debug"]["followup"]
    assert d["question_id"] == "common.age" and d["asked_so_far"] == 1 and d["multi"] is False
    assert [o["label"] for o in d["options"]] == ["1 saal se chhota", "1–5 saal", "6–17 saal", "18–64 saal", "65+ saal"]


@pytest.mark.parametrize("text,group", [("8 mahine ke baby ko bukhar hai", "infant"), ("75 saal ke papa ko bukhar hai", "elderly"),
                                        ("mere 30 saal ke bhai ko khansi hai", "adult")])
def test_age_prefilled_from_text(text, group):
    r, qids = _flow(text, [])
    assert "common.age" not in qids
    assert r["debug"]["age"]["group"] == group and r["debug"]["age"]["label"]


def test_age_chip_feeds_decision_and_matching():
    r, _ = _flow("Saans ki dikkat", ["Chalne par", "65+ saal"])
    assert r["debug"]["age"]["group"] == "elderly" and r["debug"]["age"]["source"] == "answer"
    assert r["care_type"] != "gp_teleconsult"  # 65+: home visit over teleconsult
    assert "elderly_care" in r["debug"]["matching_filters"].get("needed_skills", ["elderly_care"])


def test_child_age_prefers_paediatrics():
    r, _ = _flow("Bukhar / Fever", ["Kuch nahi", "6–17 saal"])
    assert r["debug"]["age"]["group"] == "child"
    top = r["debug"]["matching"][0] if r["debug"]["matching"] else {}
    assert top and ("pediatrics_basic" in top["skills_hit"] or "child_health" in top["skills_hit"]
                    or top.get("specialty") == "pediatrics")


# ---------------------------------------------------------------- mood
@pytest.mark.parametrize("text", ["Mann / mood", "mujhe bahut ghabrahat hoti hai", "I feel sad and low all the time",
                                  "मन बहुत उदास रहता है", "mood baar baar badalta hai aur gussa aata hai"])
def test_mood_always_asks_safety_first(text):
    r = _post(text)
    assert r["debug"]["followup"]["question_id"] == "mood.safety"


@pytest.mark.parametrize("answer", ["Haan, aise khayal aate hain", "Haan, aur tarika bhi socha hai"])
def test_self_harm_answer_is_crisis_screen(answer):
    r, _ = _flow("Mann / mood", [answer])
    assert r["care_type"] == "emergency_referral" and "suicidal_intent" in r["red_flags"]
    assert "112" in r["reasoning"] and "14416" in r["reasoning"]


@pytest.mark.parametrize("text", ["mujhe marne ka khayal aata hai", "I have thoughts of ending my life",
                                  "मुझे मरने के विचार आते हैं", "khud ko nuksan pahunchane ka mann karta hai"])
def test_typed_self_harm_is_crisis(text):
    r = _post(text)
    assert r["care_type"] == "emergency_referral" and "14416" in r["reasoning"]


@pytest.mark.parametrize("text", ["udaas rehta hoon, marne ka koi khayal nahi", "I feel low but no thoughts of suicide",
                                  "मन उदास है, मरने का कोई ख्याल नहीं", "ghabrahat hai, khud ko nuksan pahunchane ka koi khayal nahi"])
def test_negated_self_harm_is_not_crisis(text):
    assert not safety.check([text]).is_emergency
    r = _post(text)
    assert r["care_type"] != "emergency_referral"
    assert r["debug"]["followup"]["question_id"] == "mood.safety"  # still asked, gently


@pytest.mark.parametrize("answers,care,urg", [
    (["Nahi, aise khayal nahi", "18–64 saal", "Kuch dino se", "Koi khaas asar nahi"], ("gp_teleconsult",), "routine"),
    (["Nahi, aise khayal nahi", "18–64 saal", "Kai mahino se", "Thoda asar"], ("specialist_referral",), "routine"),
    (["Nahi, aise khayal nahi", "18–64 saal", "Kai mahino se", "Roz ka kaam nahi ho paata"], ("specialist_referral",), "same_day"),
])
def test_mood_routing_by_severity(answers, care, urg):
    r, _ = _flow("Mann / mood", answers)
    assert r["care_type"] in care and r["urgency"] == urg


def test_mood_has_no_disease_labels_or_medicines():
    from app import llm_triage
    r, _ = _flow("Mann / mood", ["Nahi, aise khayal nahi", "18–64 saal", "Kai mahino se", "Thoda asar"])
    card = r["debug"]["assessment"]
    assert card["sections"]["causes"]["items"] == [] and card["sections"]["tests"]["items"] == []
    text = r["reasoning"] + " ".join(card["sections"]["precautions"]["items"])
    assert not llm_triage._blocklist().search(text)
    assert not any(w in text.lower() for w in ("depression", "anxiety disorder", "bipolar", "tablet", "dawai lein"))
