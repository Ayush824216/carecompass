"""The eight symptom categories (docs/SYMPTOM_CATEGORIES.md): new pathways (breathing, urinary), the stomach split
(abdominal pain, vomiting and loose motions), headache with dizziness, cough and fever additions."""
import pytest
from fastapi.testclient import TestClient

from app import safety
from app.main import app
from app.pathways import engine as e

client = TestClient(app)
GP, PM, NU, SP = "gp_teleconsult", "paramedic_home_visit", "nurse_home_visit", "specialist_referral"
EM = ("emergency_referral", "immediate")
R, SD = "routine", "same_day"


def _res(pid, text):
    o = e.run([text])
    return {r.pathway: r for r in o.results}.get(pid)


BREATHING = [
    ("Aaram mein bhi saans phool rahi hai", "S3", *EM),
    ("My father is breathless even sitting still", "S3", *EM),
    ("होंठ नीले पड़ रहे हैं और साँस फूल रही है", "S3", *EM),
    ("Achanak saans lene mein dikkat ho rahi hai", "S3", *EM),
    ("Sudden shortness of breath since an hour", "S3", *EM),
    ("Chalne par saans phoolti hai, 3 din se", "S1", GP, SD),
    ("I get breathless when climbing stairs since 2 days", "S1", GP, SD),
    ("सीढ़ी चढ़ने पर साँस फूलती है", "S1", GP, SD),
    ("chalne pe sans fulti h 2 din se", "S1", GP, SD),
    ("Letne par saans phoolti hai aur pairon mein sujan", "S2", SP, SD),
    ("Seeti jaisi awaaz aati hai saans mein, asthma hai", "S2", SP, SD),
    ("साँस में सीटी जैसी आवाज़ और सीना जकड़ा लगता है", "S2", SP, SD),
    ("Breathless on walking with fever for 2 days", "S2", PM, SD),
    ("Hafton se dheere-dheere chalne par saans phoolne lagi hai", "S2", SP, SD),
]
URINARY = [
    ("Peshab mein jalan aur baar baar peshab aa raha hai", "S1", GP, SD),
    ("Burning while passing urine since yesterday", "S1", GP, SD),
    ("पेशाब में जलन और बार-बार पेशाब", "S1", GP, SD),
    ("peshab me jalan ho rhi h", "S1", GP, SD),
    ("Bahut pyaas lagti hai aur baar baar peshab", "S1", GP, SD),
    ("Peshab mein jalan, bukhar aur kamar ke side mein dard", "S2", GP, SD),
    ("Fever with chills and pain in the side of the back, burning urine", "S2", GP, SD),
    ("पेशाब में खून आ रहा है", "S2", GP, SD),
    ("6 saal ke bete ko peshab mein jalan", "S2", GP, SD),
    ("72 saal ke papa ki peshab ki dhaar kamzor hai", "S2", SP, SD),
    ("Peshab bilkul nahi ho raha, pet ke neeche dard", "S3", *EM),
    ("I can't pass urine since morning", "S3", *EM),
    ("Pregnant hoon, bukhar aur peshab mein jalan", "S3", *EM),
]
ABDOMINAL = [
    ("Pet mein halka dard hai aaj se", "S0", GP, R),
    ("Pet mein dard hai 2 din se", "S1", GP, SD),
    ("पेट में दर्द है", "S1", GP, SD),
    ("Stomach pain since yesterday", "S1", GP, SD),
    ("pet me dard h kal se", "S1", GP, SD),
    ("Pet ke upar dard khaane ke baad", "S1", GP, SD),  # never auto-labelled as acidity: a doctor today
    ("Pet mein bahut tez dard", "S2", GP, SD),
    ("Pain in the lower right of the belly since morning", "S2", GP, SD),
    ("Pet dard badhta ja raha hai", "S2", GP, SD),
    ("Upper right belly pain with yellow eyes", "S2", GP, SD),
    ("पेट दर्द और बुखार 2 दिन से", "S2", GP, SD),
    ("Naabhi ke paas se dard daayein neeche aa gaya, chalne par badhta hai", "S3", *EM),
    ("Pet patthar jaisa sakht ho gaya hai", "S3", *EM),
    ("Pregnant hoon aur pet mein dard", "S3", *EM),
]
VOMITING = [
    ("Aaj subah se 3 baar dast, paani pee raha hoon", "S0", GP, R),
    ("ulty ho rhi h subah se 2 baar, pani pi rha hu", "S0", GP, R),
    ("2 din se dast aur halka bukhar", "S1", PM, SD),
    ("Loose motions for 3 days", "S1", PM, SD),
    ("Vomited 10 times and cannot keep water down", "S2", NU, SD),
    ("मम्मी को 10 बार उल्टी हुई, पानी भी नहीं रुक रहा", "S2", NU, SD),
    ("दादी को 2 दिन से दस्त", "S2", NU, SD),
    ("Dast ke saath khade hone par chakkar", "S2", NU, SD),
    ("Potty mein khoon aur bukhar", "S2", GP, SD),
    ("Dast 3 hafte se", "S2", GP, SD),
    ("Khoon ki ulti hui", "S3", *EM),
    ("Bacche ne 12 ghante se peshab nahi kiya, dast ho rahe", "S3", *EM),
    ("8 mahine ke baby ko dast aur doodh nahi pee raha", "S3", *EM),
]
DIZZINESS = [
    ("Khade hone par chakkar aata hai", "S1", GP, SD),
    ("खड़े होने पर चक्कर आता है", "S1", GP, SD),
    ("I feel dizzy when I stand up", "S1", GP, SD),
    ("Sab ghoomta hua lagta hai", "S1", GP, SD),
    ("72 saal ki mummy ko chakkar aata hai", "S2", "paramedic_home_visit", SD),  # 65+: home visit over teleconsult
]


@pytest.mark.parametrize("pid,text,stage,care,urg", [("breathing", *c) for c in BREATHING] + [("urinary", *c) for c in URINARY]
                         + [("abdominal", *c) for c in ABDOMINAL] + [("vomiting", *c) for c in VOMITING]
                         + [("headache", *c) for c in DIZZINESS])
def test_category_stage(pid, text, stage, care, urg):
    r = _res(pid, text)
    assert r is not None, f"{pid} not triggered: {text}"
    assert (r.stage, r.care_type, r.urgency) == (stage, care, urg), (text, r.as_dict())


def test_every_s3_case_reaches_emergency_end_to_end():
    for text, stage, *_ in BREATHING + URINARY + ABDOMINAL + VOMITING:
        if stage != "S3":
            continue
        r = client.post("/api/v1/triage", json={"user_input": text}).json()
        assert r["care_type"] == "emergency_referral" and r["follow_up_question"] is None, text


def test_severe_breathlessness_asks_no_question():
    for text in ("aaram mein bhi saans nahi aa rahi", "achanak saans lene mein dikkat", "बैठे-बैठे भी साँस फूल रही है"):
        r = client.post("/api/v1/triage", json={"user_input": text, "debug": True}).json()
        assert r["care_type"] == "emergency_referral" and r["follow_up_question"] is None, text


def test_breathing_never_reassured_as_routine():
    for text in ("thodi saans phoolti hai chalne par", "seeti jaisi awaaz aati hai saans mein", "chest feels tight sometimes"):
        r = _res("breathing", text)
        assert r is not None and r.stage != "S0", text


def test_stomach_split_both_categories_run():
    o = e.run(["pet mein dard aur ulti ho rahi hai 2 din se"])
    assert {"abdominal", "vomiting"} <= {r.pathway for r in o.results}


def test_abdominal_never_asks_pregnancy_unprompted():
    _, pathways, _ = e.load()
    for q in pathways["abdominal"].cfg["questions"]:
        assert not any("pregnant" in c["facts"] for c in q["chips"]), q["id"]
    assert _res("abdominal", "Pregnant hoon aur pet mein dard").stage == "S3"  # voluntarily disclosed: used


def test_cough_tb_contact_is_exposure_not_patient():
    o = e.run(["3 hafte se khansi, ghar mein dadi ko TB hai"])
    c = {r.pathway: r for r in o.results}["cough"]
    assert o.facts["tb_contact"] and o.slots.age_group is None and c.stage == "S2" and "tb_test" in c.notes


@pytest.mark.parametrize("text,stage", [("khansi aur seeti jaisi awaaz", "S1"), ("baar baar khansi hoti hai har sardi mein", "S1"),
                                        ("Khansi ke saath seena jakda lagta hai", "S1")])
def test_cough_wheeze_tightness_recurring(text, stage):
    assert _res("cough", text).stage == stage


def test_blood_in_cough_streaks_vs_large():
    assert not safety.check(["khansi mein khoon"]).red_flags  # amount is asked, not assumed
    o = e.run(["khansi mein khoon"])
    assert e.next_question(o, 0)["id"] == "cough.blood_amount"
    assert _res("cough", "balgam mein khoon ke dhaage").stage == "S2"
    assert _res("cough", "khansi mein chammach bhar khoon").stage == "S3"
    assert safety.check(["khansi mein bahut khoon aa raha"]).red_flags


@pytest.mark.parametrize("answer,qid", [("Khansi", "fever.sub_breath"), ("Pet dard", "fever.sub_stomach"),
                                        ("Badan mein bahut dard", "fever.sub_ache"), ("Thand lagkar kapkapi", "fever.sub_chills")])
def test_fever_subtree_depends_on_previous_answer(answer, qid):
    hist = [{"role": "user", "content": "bukhar hai 2 din se, thermometer mein 101"},
            {"role": "assistant", "content": "Bukhar ke saath kya-kya hai?"}]
    o = e.run([h["content"] for h in hist if h["role"] == "user"] + [answer], history=hist, user_input=answer)
    asked = set(o.answers.asked) | {"fever.danger", "common.age"}
    o.answers.asked = list(asked)
    q = e.next_question(o, 2)
    assert q is not None and q["id"] == qid, (answer, q and q["id"])


def test_no_non_definite_chip_trips_the_safety_layer():
    """A chip that is not definite_S3 must never trigger the emergency path by its label alone,
    or its confirmation question could never be asked."""
    _, pathways, _ = e.load()
    for pid, p in pathways.items():
        for q in p.cfg["questions"]:
            for c in q["chips"]:
                if c.get("severity") == "definite_S3":
                    continue
                for lang in ("en", "hi", "hinglish"):
                    assert not safety.check([c["label"][lang]]).red_flags, (pid, q["id"], c["id"], c["label"][lang])


def test_urinary_flow_end_to_end():
    r = client.post("/api/v1/triage", json={"user_input": "peshab mein jalan ho rahi hai", "debug": True}).json()
    assert r["follow_up_question"] and r["debug"]["followup"]["pathway"] == "urinary"


def test_vomiting_dehydration_flow_end_to_end():
    text, hist = "mummy ko 10 baar ulti hui, paani bhi nahi ruk raha, chakkar aa rahe", []
    for _ in range(6):
        r = client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist, "debug": True,
                                                "location": {"lat": 28.5245, "lng": 77.2066}}).json()
        if not r["follow_up_question"]:
            break
        assert r["debug"]["followup"]["pathway"] == "vomiting"
        opts = r["debug"]["followup"]["options"]
        hist += [{"role": "user", "content": text}, {"role": "assistant", "content": r["follow_up_question"]}]
        if r["debug"]["followup"]["question_id"] == "common.age":
            text = "18–64 saal"
        else:
            text = "Kuch nahi" if opts[-1]["id"] == "none" else opts[0]["label"]
    assert r["care_type"] == NU and r["urgency"] == SD and r["debug"]["assessment"]["category"] == "vomiting"
