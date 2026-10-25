"""Over-abstention fix: a broad medical lexicon with typo matching, disease aliases (Hindi / Hinglish) and the General
pathway. A disease name is a health request, never confirmed or denied, and never sets urgency by itself."""
import pytest
from fastapi.testclient import TestClient

from app import domain_guard, lexicon
from app.main import app
from app.schemas import URGENCY_RANK

client = TestClient(app)
LOC = {"lat": 28.5245, "lng": 77.2066}
EMERGENCY = "emergency_referral"


def _post(text, hist=None):
    r = client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist or [], "location": LOC,
                                            "debug": True})
    assert r.status_code == 200
    return r.json()


def _flow(start, answers=()):
    hist, text, r = [], start, None
    answers = list(answers)
    for _ in range(10):
        r = _post(text, hist)
        if not r["follow_up_question"]:
            return r
        qid = r["debug"]["followup"].get("question_id")
        opts = r["debug"]["followup"].get("options") or []
        hist += [{"role": "user", "content": text}, {"role": "assistant", "content": r["follow_up_question"]}]
        if answers:
            text = answers.pop(0)
        elif qid == "common.age":
            text = "18–64 saal"
        else:
            text = next((o["label"] for o in opts if o["id"] == "none"), opts[-1]["label"] if opts else "Nahi")
    return r


REPORTED = ["aakh pili h meri", "aankje peeli hai meri", "mujhe jaundice hai", "mujhe aids hai", "mujhe cnacer hai"]
VARIANTS = ["aankh peeli ho gayi hai", "ankhen pili hain", "mujhe jaundise hai", "peeliya ho gaya hai", "पीलिया है",
            "आँखें पीली हो गई हैं", "mujhe cancr hai", "HIV positive hoon", "mujhe tapedik hai", "dama ki bimari hai",
            "daant me bahut dard hai", "kaan se paani aa raha hai", "aankh laal ho gayi", "twacha pe khujli hai"]


@pytest.mark.parametrize("text", REPORTED + VARIANTS)
def test_disease_and_body_complaints_are_health_requests(text):
    assert domain_guard.classify(text) == domain_guard.HEALTH
    r = _post(text)
    assert r["debug"]["domain_class"] == "health_request"
    assert r["care_type"] != EMERGENCY
    if r["follow_up_question"]:  # a clinical question, never the "no health problem found" redirect
        assert r["follow_up_question"] not in domain_guard.REDIRECT_TEXTS


@pytest.mark.parametrize("text", ["abba dabba jabba", "asdfgh", "xyzitis", "qwrtzp lkjhg"])
def test_true_gibberish_still_abstains(text):
    r = _post(text)
    assert r["debug"]["domain_class"] != "health_request" and r["care_type"] is None


@pytest.mark.parametrize("typo,canonical", [("aakh", "aankh"), ("aankje", "aankh"), ("pilli", "peela"), ("cnacer", "cancer"),
                                            ("cancr", "cancer"), ("jaundise", "jaundice")])
def test_fuzzy_matching(typo, canonical):
    h = lexicon.hits(typo)
    assert h and h[0].fuzzy and h[0].canonical == canonical


@pytest.mark.parametrize("word", ["kaam", "naam", "kids", "gaya", "meri", "pani"])
def test_everyday_words_never_fuzzy_match(word):
    assert lexicon.fuzzy(word) is None


@pytest.mark.parametrize("text,word", [("mujhe cancer hai", "cancer"), ("mujhe aids hai", "aids"), ("mujhe tapedik hai", "tapedik"),
                                       ("mujhe jaundice hai", "jaundice")])
def test_disease_name_never_repeated_back(text, word):
    r = _post(text)
    shown = " ".join(filter(None, [r["follow_up_question"], r["reasoning"]])).lower()
    assert word not in shown


def test_known_sugar_is_not_an_emergency():
    r = _flow("mujhe sugar hai")
    assert r["care_type"] != EMERGENCY and r["urgency"] != "immediate"


@pytest.mark.parametrize("text", ["papa ko lakwa maar gaya abhi", "abhi dil ka daura aaya hai", "mirgi ka daura pad raha hai abhi"])
def test_emergency_condition_happening_now(text):
    r = _post(text)
    assert r["care_type"] == EMERGENCY and r["urgency"] == "immediate"


@pytest.mark.parametrize("text", ["mujhe mirgi hai", "papa ko pichle saal lakwa hua tha", "I have epilepsy, need a check-up"])
def test_emergency_condition_name_alone_is_not_an_emergency(text):
    assert _post(text)["care_type"] != EMERGENCY


# ---------------------------------------------------------------- General pathway
@pytest.mark.parametrize("text", ["aakh pili h meri", "mujhe jaundice hai", "आँखें पीली हो गई हैं"])
def test_yellow_eyes_is_same_day(text):
    r = _flow(text)
    assert r["care_type"] != EMERGENCY and r["urgency"] == "same_day"


@pytest.mark.parametrize("text,answers", [
    ("aankh peeli hai aur bahut sust hain, behki behki baatein kar rahe hain", []),
    ("mujhe jaundice hai", ["Khoon aana"]),
    ("skin yellow ho gayi hai", ["Baar-baar ulti"]),
])
def test_yellow_eyes_with_danger_sign_is_emergency(text, answers):
    r = _flow(text, answers)
    assert r["care_type"] == EMERGENCY


def test_general_asks_what_is_happening_now_first():
    r = _post("mujhe cnacer hai")
    assert r["debug"]["followup"]["question_id"] == "general.danger"
    assert r["debug"]["followup"]["pathway"] == "general"


def test_condition_name_alone_never_sets_urgency():
    for text in ("mujhe cancer hai", "mujhe tapedik hai", "mujhe thyroid hai", "mujhe mirgi hai"):
        assert _flow(text)["urgency"] == "routine"


def test_serious_chronic_raises_a_current_problem():
    plain = _flow("daant me bahut dard hai")
    chronic = _flow("mujhe cancer hai, daant me bahut dard hai")
    assert URGENCY_RANK[chronic["urgency"]] >= URGENCY_RANK[plain["urgency"]]
    assert chronic["debug"]["pathways"]["primary"]["stage"] in ("S2", "S3") or chronic["urgency"] == "same_day"


def test_general_default_is_gp_teleconsult():
    r = _flow("kaan se paani aa raha hai")
    assert r["care_type"] in ("gp_teleconsult", "paramedic_home_visit", "specialist_referral")


def test_hiv_is_never_offered_for_saving():
    r = _flow("mujhe HIV hai, daant me dard hai")
    ids = {c["id"] for c in r["debug"].get("memory_candidates") or []}
    assert "hiv_sti" not in ids and r["debug"].get("memory_summary") is None
