from app import explain, intake

CONF = {"care_type": {"gp_teleconsult": 0.9, "paramedic_home_visit": 0.1}, "urgency": {"routine": 0.9, "same_day": 0.1}}
UNSURE = {"care_type": {"gp_teleconsult": 0.4, "paramedic_home_visit": 0.35}, "urgency": {"routine": 0.5, "same_day": 0.45}}


def test_slots_example():
    s = intake.extract_slots(["Papa ko do din se bukhar hai aur khansi bhi"])
    assert {"fever", "cough"} <= set(s.symptoms) and s.duration == "acute" and s.duration_text == "do din se"


def test_age_not_duration():
    s = intake.extract_slots(["mere 8 mahine ke bachche ko khansi hai"])
    assert s.age_group == "infant" and s.duration is None


def test_no_question_when_confident():
    st = intake.build_state("papa ko do din se bukhar hai aur khansi bhi", [])
    assert intake.choose_followup(st, CONF) is None


def test_vague_input_asks_main_problem():
    st = intake.build_state("tabiyat kharab hai", [])
    assert intake.choose_followup(st, UNSURE) == "main_problem"


def test_safety_question_first_when_unsure():
    st = intake.build_state("mujhe khansi hai", [])
    assert intake.choose_followup(st, UNSURE) == "breathing"


def test_high_risk_screen_even_if_confident():
    st = intake.build_state("I have acidity and sweating", [])
    assert intake.choose_followup(st, CONF) == "chest"


def test_yes_to_breathing_raises_flag():
    h = [{"role": "user", "content": "bachche ko khansi hai"},
         {"role": "assistant", "content": intake.question_text("breathing", "hinglish")}]
    st = intake.build_state("haan", h)
    assert "severe_breathing_difficulty" in st.extra_flags


def test_no_to_breathing_becomes_fact():
    h = [{"role": "user", "content": "bachche ko khansi hai"},
         {"role": "assistant", "content": intake.question_text("breathing", "en")}]
    st = intake.build_state("No", h)
    assert st.slots.breathing == "ok" and "no breathing difficulty" in st.model_text and not st.extra_flags


def test_max_followups():
    h = []
    for q in ("duration", "patient", "severity", "mobility"):
        h += [{"role": "user", "content": "pata nahi"}, {"role": "assistant", "content": intake.question_text(q, "en")}]
    st = intake.build_state("pata nahi", h)
    assert st.n_assistant_questions == 4 and intake.choose_followup(st, UNSURE) is None


def test_question_not_repeated():
    h = [{"role": "user", "content": "mujhe khansi hai"}, {"role": "assistant", "content": intake.question_text("breathing", "hi")}]
    st = intake.build_state("नहीं", h)
    assert intake.choose_followup(st, UNSURE) != "breathing"


def test_reasoning_languages_no_diagnosis():
    s = intake.extract_slots(["Papa ko do din se bukhar hai aur khansi bhi"])
    for lang in ("en", "hi", "hinglish"):
        r = explain.reasoning(s, "paramedic_home_visit", "same_day", lang)
        assert r and "pneumonia" not in r.lower()
    assert "do din se" in explain.reasoning(s, "paramedic_home_visit", "same_day", "hinglish").lower()
