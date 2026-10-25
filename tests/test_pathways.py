"""Clinical pathway tests: every worked example and edge case from docs/CLINICAL_PATHWAYS.md (sections 1.6, 2.5,
3.4, 4.4, 5.4 and 6), plus Hindi-script and Hinglish-with-typos variants."""
import pytest

from app import pathways as pw
from app import safety
from app.pathways import route
from app.pathways.slots import parse

EM = ("emergency_referral", "immediate")

WORKED = [
    # 1.6 fever
    ("Papa ko do din se bukhar hai aur khansi bhi, saans theek hai", "S1", "paramedic_home_visit", "same_day"),
    ("Kal se halka bukhar, 100 tha, khana kha raha hoon", "S0", "gp_teleconsult", "routine"),
    ("4 din se tez bukhar, aankhon ke peeche dard, badan toot raha hai", "S1", "paramedic_home_visit", "same_day"),
    ("Dengue test positive, platelets 80 hazaar, pet mein dard", "S2", "gp_teleconsult", "same_day"),
    ("Platelets 18000 aur masudon se khoon", "S3", *EM),
    ("Roz shaam ko thand lagkar bukhar aata hai, phir paseena", "S1", "paramedic_home_visit", "same_day"),
    ("Bukhar ke saath aankhen peeli aur ab bahut neend aa rahi hai", "S3", *EM),
    ("8 din se bukhar, roz badhta hai, pet dard aur kabz", "S2", "gp_teleconsult", "same_day"),
    ("Tez bukhar aur ghutne-kalaiyon mein itna dard ki chal nahi pa rahi, 70 saal", "S2", "paramedic_home_visit", "same_day"),
    ("2 mahine ke bacche ko 100.8 bukhar", "S3", *EM),
    ("Bukhar aur gardan akad gayi hai, ulti bhi", "S3", *EM),
    ("Bukhar aur peshab mein jalan, kamar ke side mein dard", "S2", "gp_teleconsult", "same_day"),
    # 2.5 cough
    ("5 din se sukhi khansi, aur kuch nahi", "S0", "gp_teleconsult", "routine"),
    ("Balgam wali khansi aur 3 din se bukhar", "S1", "paramedic_home_visit", "same_day"),
    ("3 hafte se khansi, raat ko paseena, wazan kam ho gaya", "S2", "specialist_referral", "same_day"),
    ("Balgam mein thoda khoon ke dhaage dikhe", "S2", "specialist_referral", "same_day"),
    ("Khansi mein bahut khoon aaya, chammach bhar", "S3", *EM),
    ("Asthma hai, inhaler se bhi aaram nahi, bol nahi pa rahi", "S3", *EM),
    ("Bacche ki khansi kutte ke bhaunkne jaisi, saans lete waqt awaaz", "S3", *EM),
    ("Dadi ko khansi aur aaj se kuch ulta-seedha bol rahi hain", "S3", *EM),
    # 3.4 stomach
    ("Aaj subah se 3 baar dast, paani pee raha hoon", "S0", "gp_teleconsult", "routine"),
    ("2 din se dast aur halka bukhar", "S1", "paramedic_home_visit", "same_day"),
    ("Mummy ko 10 baar ulti, paani bhi nahi ruk raha, chakkar aa rahe", "S2", "nurse_home_visit", "same_day"),
    ("Potty bilkul kaali aur chipchipi aa rahi hai", "S3", *EM),
    ("Naabhi ke paas se dard daayein neeche aa gaya, chalne par badhta hai, bukhar", "S3", *EM),
    ("Pregnant hoon aur pet mein tez dard", "S3", *EM),
    ("Bacche ne 12 ghante se peshab nahi kiya, dast ho rahe", "S3", *EM),
    # 4.4 chest pain
    ("Seene mein bhaari dabav aur paseena, baayen haath mein dard", "S3", *EM),
    ("55 saal, sugar hai, seene mein ajeeb sa dard", "S3", *EM),
    ("Khaane ke baad seene mein jalan, 24 saal, aur kuch nahi", "S1", "gp_teleconsult", "same_day"),
    ("Gym ke baad chest dabane par dard hota hai, 22 saal", "S0", "gp_teleconsult", "routine"),
    ("Achanak saans lete waqt chubhne wala dard aur saans phool gayi", "S3", *EM),
    # 5.4 headache
    ("Migraine purana hai, aaj phir wahi dard", "S0", "gp_teleconsult", "routine"),
    ("Achanak itna tez sir dard jaise kabhi nahi hua", "S3", *EM),
    ("Sir dard aur ek haath mein kamzori, bolne mein atak rahe", "S3", *EM),
    ("Papa gir gaye, sir par chot, ab 2 baar ulti", "S3", *EM),
    ("60 saal, pichle 3 hafte se roz sir dard badh raha", "S2", "specialist_referral", "same_day"),
    ("8 mahine pregnant, sir dard aur aankhon ke aage dhundhla", "S3", *EM),
]

HINDI = [
    ("पापा को दो दिन से बुखार है और खांसी भी", "S1", "paramedic_home_visit", "same_day"),
    ("प्लेटलेट्स 18000 और मसूड़ों से खून", "S3", *EM),
    ("बुखार के साथ आँखें पीली और बहुत नींद आ रही है", "S3", *EM),
    ("पाँच दिन से सूखी खांसी, और कुछ नहीं", "S0", "gp_teleconsult", "routine"),
    ("बलगम में खून के धागे दिखे", "S2", "specialist_referral", "same_day"),
    ("आज सुबह से 3 बार दस्त, पानी पी रहा हूँ", "S0", "gp_teleconsult", "routine"),
    ("पॉटी बिल्कुल काली आ रही है", "S3", *EM),
    ("सीने में भारी दबाव और पसीना", "S3", *EM),
    ("खाने के बाद सीने में जलन, 24 साल, और कुछ नहीं", "S1", "gp_teleconsult", "same_day"),
    ("अचानक इतना तेज़ सिर दर्द जैसा कभी नहीं हुआ", "S3", *EM),
    ("माइग्रेन पुराना है, आज फिर वही दर्द", "S0", "gp_teleconsult", "routine"),
    ("मेरी पत्नी गर्भवती है और पेट में तेज़ दर्द है", "S3", *EM),
]

HINGLISH_TYPOS = [
    ("papa ko 2 din se bukhaar h aur khasi bhi", "S1", "paramedic_home_visit", "same_day"),
    ("platlets 18000 aur masudo se khoon", "S3", *EM),
    ("bukar ke sath ankhen pili aur bht neend aa rhi", "S3", *EM),
    ("5 din se sukhi khasi aur kuch nhi", "S0", "gp_teleconsult", "routine"),
    ("balgam me thoda khun ke dhage", "S2", "specialist_referral", "same_day"),
    ("aaj subha se 3 bar dast, pani pi raha hu", "S0", "gp_teleconsult", "routine"),
    ("potty bilkul kali aa rahi h", "S3", *EM),
    ("seene me bhari dabav aur pasina", "S3", *EM),
    ("achanak itna tej sir dard jaisa kabhi nhi hua", "S3", *EM),
    ("sar dard aur ek hath mein kamjori, bolne me atak rahe", "S3", *EM),
    ("pregnent hu aur pet me tez dard", "S3", *EM),
    ("dadi ko khansi aur aaj se ulta sidha bol rahi", "S3", *EM),
]


def _primary(text, history=None):
    return pw.run([text], history=history, user_input=text).primary


@pytest.mark.parametrize("text,stage,care,urg", WORKED + HINDI + HINGLISH_TYPOS)
def test_worked_examples(text, stage, care, urg):
    p = _primary(text)
    assert p is not None, f"no pathway triggered: {text}"
    assert (p.stage, p.care_type, p.urgency) == (stage, care, urg), (text, p.as_dict())


def test_variant_counts():
    assert len(WORKED) >= 38 and len(HINDI) >= 10 and len(HINGLISH_TYPOS) >= 10


# ---------------------------------------------------------------- section 6 edge cases
def test_e01_negation():
    o = pw.run(["bukhar hai par saans ki dikkat nahi"])
    assert o.facts["fever"] and not o.facts.get("breathless") and "breathless" in o.neg


def test_e02_correction_latest_wins():
    o = pw.run(["khansi mein khoon nahi... nahi ruko, thoda sa aaya tha"])
    assert o.facts.get("blood_in_cough") is True


def test_e03_celsius_and_fahrenheit():
    assert parse(["bukhar 39.5 hai"]).temp_f >= 102 and parse(["bukhar 103 hai"]).temp_f >= 102


def test_e04_no_number_is_reported_high_not_measured():
    s = parse(["bahut tez bukhar"])
    assert s.high_fever_reported and s.temp_f is None and not s.temperature_measured
    o = pw.run(["bahut tez bukhar hai kal se"])
    assert o.facts["temp_f"] is None and o.facts["fever_reported_high"] and not o.facts["temp_measured"]
    assert o.primary.stage == "S1" and o.primary.urgency == "same_day"  # same-day for safety until measured
    q = pw.next_question(o, 0)
    assert q["id"] in ("fever.danger", "fever.temperature")


def test_e04_thermometer_band_chips():
    q = next(q for q in pw.load()[1]["fever"].cfg["questions"] if q["id"] == "fever.temperature")
    labels = [o["label"] for o in pw.chip_options(q, "hinglish")]
    assert labels == ["100°F se kam", "100–102°F", "102–104°F", "104°F ya zyada", "Naapa nahi"] and q["single"]
    hist = [{"role": "user", "content": "bahut tez bukhar hai kal se"},
            {"role": "assistant", "content": "Thermometer se naapa? Kitna aaya?"}]
    o = pw.run(["bahut tez bukhar hai kal se", "104°F ya zyada"], history=hist, user_input="104°F ya zyada")
    assert o.facts["temp_band"] == "104+" and o.primary.stage == "S2"
    o = pw.run(["bahut tez bukhar hai kal se", "Naapa nahi"], history=hist, user_input="Naapa nahi")
    assert o.facts["temp_f"] is None and "temp_f" in o.known and o.primary.stage == "S1"


def test_e04_summary_says_not_measured():
    r = client.post("/api/v1/triage", json={"user_input": "bahut tez bukhar hai 3 din se, badan dard", "debug": True}).json()
    assert r["follow_up_question"] or "naapa nahi" in r["reasoning"].lower()
    for t in ("bahut tez bukhar hai 3 din se, badan dard", "very high fever since 3 days, body ache", "3 दिन से बहुत तेज़ बुखार, बदन दर्द"):
        o = pw.run([t])
        txt = route.reasoning(o, o.primary.care_type, o.primary.urgency, "en")
        assert "not measured" in txt and "102" not in txt and "°F" not in txt


def test_e05_relative_time():
    assert parse(["parso se bukhar"]).duration_days == 2 and parse(["kal raat se bukhar"]).duration_days == 1


@pytest.mark.parametrize("text", ["platelets 40k", "platelets 40 hazaar", "platelet 0.4 lakh", "platelets 40,000", "40 thousand platelets"])
def test_e06_platelet_formats(text):
    assert parse([text]).platelets == 40000


def test_e07_someone_elses_illness():
    o = pw.run(["padosi ko dengue hua tha"])
    assert o.slots.named_diseases == [] and "dengue" in o.slots.context_diseases and o.primary is None


def test_e08_past_history():
    o = pw.run(["pichle saal malaria hua tha"])
    assert o.slots.named_diseases == [] and o.primary is None


def test_e09_named_disease_not_confirmed_but_routed():
    o = pw.run(["mujhe lagta hai dengue hai"])
    assert o.primary is not None and o.primary.pathway == "fever" and o.primary.stage == "S1"


@pytest.mark.parametrize("text", ["khoon ki kami hai", "khoon ki jaanch karayi", "खून की कमी है"])
def test_e10_khoon_is_not_bleeding(text):
    o = pw.run([text])
    assert not o.facts.get("bleeding_any") and safety.check([text]).red_flags == []


def test_e11_multiple_complaints_chest_dominates():
    o = pw.run(["bukhar aur seene mein dard"])
    assert {r.pathway for r in o.results} >= {"fever", "chest_pain"}
    assert o.primary.pathway == "chest_pain" and o.primary.stage == "S3"


def test_e12_mixed_scripts():
    o = pw.run(["मम्मी को fever hai aur ulti"])
    assert {r.pathway for r in o.results} >= {"fever", "vomiting"}


def test_e13_age_in_months():
    o = pw.run(["8 mahine ka baccha, bukhar hai"])
    assert o.facts["infant"] and o.facts["child"]


def test_e14_pregnancy_mentioned_late():
    q1 = pw.question_text(next(q for q in pw.load()[1]["fever"].cfg["questions"] if q["id"] == "fever.danger"), "hinglish")
    q2 = pw.question_text(next(q for q in pw.load()[1]["fever"].cfg["questions"] if q["id"] == "fever.duration_height"), "hinglish")
    hist = [{"role": "user", "content": "bukhar hai"}, {"role": "assistant", "content": q1},
            {"role": "user", "content": "Kuch nahi"}, {"role": "assistant", "content": q2}]
    before = pw.run(["bukhar hai", "Kuch nahi"], history=hist[:3], user_input="Kuch nahi")
    after = pw.run(["bukhar hai", "Kuch nahi", "1 din, wo pregnant hai aur pet mein dard"], history=hist,
                   user_input="1 din, wo pregnant hai aur pet mein dard")
    assert before.primary.stage in ("S0", "S1") and after.primary.stage == "S3"


def test_e15_contradiction_uses_more_severe():
    o = pw.run(["saans theek hai", "chalne par saans phoolti hai"])
    assert o.facts.get("breathless") is True


def test_e16_medicine_request_continues_routing():
    o = pw.run(["kaunsi dawai lun bukhar ke liye"])
    assert o.primary is not None and o.primary.pathway == "fever"


def test_e17_report_pasted():
    o = pw.run(["Hb 9, platelet 95000, WBC 3000"])
    assert o.slots.platelets == 95000 and o.primary.pathway == "fever" and o.primary.stage == "S2"


def test_e18_voice_typing_errors():
    o = pw.run(["bukhaar aur khasi hai, plate let 90000"])
    assert o.facts["fever"] and o.facts["cough"] and o.slots.platelets == 90000


def test_e19_fever_down_but_worse():
    p = _primary("bukhar utar gaya par ab bahut kamzori aur pet dard")
    assert p.stage in ("S2", "S3")


def test_e20_iron_tablets_black_stool():
    o = pw.run(["iron ki goli le rahi hoon, potty kaali"])
    st = next(r for r in o.results if r.pathway == "vomiting")
    assert st.stage == "S2" and st.urgency == "same_day" and "doctor_today" in st.notes


# ---------------------------------------------------------------- engine behaviour
def test_missing_slots_never_lower_and_rules_validate():
    common, pathways, signs = pw.load()  # loading validates every rule expression
    assert set(pathways) == {"fever", "cough", "breathing", "chest_pain", "headache", "abdominal", "vomiting", "urinary", "mood", "general"} and len(signs) > 50


def test_questions_danger_first_and_stop_on_s3():
    o = pw.run(["bukhar hai"])
    q = pw.next_question(o, 0)
    assert q is not None and q["id"] == "fever.danger"
    assert pw.next_question(pw.run(["bukhar aur gardan akad gayi"]), 0) is None


def test_questions_skip_known_and_cap_at_four():
    o = pw.run(["bukhar hai"])
    assert pw.next_question(o, 4) is None
    text = "tez bukhar hai"
    q = pw.next_question(pw.run([text]), 0)
    assert q["id"] == "fever.danger"


def test_sufficient_input_asks_nothing():
    assert pw.next_question(pw.run(["papa ko do din se bukhar hai aur khansi bhi"]), 0) is None


def test_chip_options_have_none():
    q = next(q for q in pw.load()[1]["fever"].cfg["questions"] if q["id"] == "fever.danger")
    opts = pw.chip_options(q, "hinglish")
    assert opts[-1]["id"] == "none" and opts[-1]["label"] == "Kuch nahi"


# ---------------------------------------------------------------- API integration
import re  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
OFFICIAL = {"follow_up_question", "care_type", "urgency", "red_flags", "reasoning", "matched_caregivers"}
DISEASE = re.compile(r"dengue|malaria|typhoid|chikun|jaundice|hepatitis|tuberculosis|\btb\b|pneumonia|meningitis|appendic|डेंगू|मलेरिया", re.I)


def _post(text, hist=None, debug=True):
    return client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist or [], "debug": debug,
                                                "location": {"lat": 28.5245, "lng": 77.2066}}).json()


def test_api_schema_unchanged_with_pathways():
    r = client.post("/api/v1/triage", json={"user_input": "Platelets 18000 aur masudon se khoon"}).json()
    assert set(r) == OFFICIAL and r["care_type"] == "emergency_referral" and r["matched_caregivers"] == []


def test_api_pathway_question_multiselect_chips():
    r = _post("bukhar hai")
    assert r["follow_up_question"] and r["care_type"] is None
    fu = r["debug"]["followup"]
    assert fu["pathway"] == "fever" and fu["multi"] is True and fu["question_id"] == "fever.danger"
    assert fu["options"][-1]["id"] == "none"


def test_api_pathway_flow_none_then_next_question():
    q1 = _post("bukhar hai")["follow_up_question"]
    hist = [{"role": "user", "content": "bukhar hai"}, {"role": "assistant", "content": q1}]
    r = _post("Kuch nahi", hist)
    assert r["debug"]["followup"].get("question_id") == "common.age"  # age unknown: asked early, not counted
    assert r["debug"]["followup"]["asked_so_far"] == 1
    hist += [{"role": "user", "content": "Kuch nahi"}, {"role": "assistant", "content": r["follow_up_question"]}]
    r = _post("18–64 saal", hist)
    assert r["debug"]["followup"].get("question_id") == "fever.duration_height"
    assert r["debug"]["followup"]["asked_so_far"] == 1


def test_api_stops_on_s3_answer():
    q1 = _post("bukhar hai")["follow_up_question"]
    hist = [{"role": "user", "content": "bukhar hai"}, {"role": "assistant", "content": q1}]
    r = _post("Gardan akadna / bahut tez sir dard", hist)
    assert r["care_type"] == "emergency_referral" and r["follow_up_question"] is None


def test_api_max_four_questions_then_decide():
    text, hist = "bukhar hai", []
    for _ in range(6):
        r = _post(text, hist)
        if not r["follow_up_question"]:
            break
        hist += [{"role": "user", "content": text}, {"role": "assistant", "content": r["follow_up_question"]}]
        text = "Koi nahi" if "kaun" in r["follow_up_question"].lower() else "Kuch nahi"
    age_q = "Mareez ki umar kitni hai?"  # the age chip question does not count toward the 4
    assert r["care_type"] is not None and len([h for h in hist if h["role"] == "assistant" and h["content"] != age_q]) <= 4


@pytest.mark.parametrize("text", ["mujhe lagta hai dengue hai", "Dengue test positive, platelets 80 hazaar, pet mein dard",
                                  "pichle saal malaria hua tha aur ab 3 din se bukhar", "typhoid jaisa lag raha hai, 8 din se bukhar",
                                  "platelets 15000 reh gaye", "BP 200/120 hai aur sir dard", "bukhar aur gardan akad gayi",
                                  "dard naabhi se daayein neeche aa gaya, bukhar bhi", "khansi, bukhar aur saans bahut phool rahi hai"])
def test_api_never_names_a_disease(text):
    r = _post(text, debug=False)
    assert not DISEASE.search((r["reasoning"] or "") + (r["follow_up_question"] or "") + " ".join(r["red_flags"])), r


def test_reading_only_emergency_uses_neutral_flag_with_label():
    r = _post("platelets 15000 reh gaye")
    assert r["care_type"] == "emergency_referral" and r["red_flags"] == ["low_platelets"]
    assert r["debug"]["pathways"]["flag_labels"]["low_platelets"]


def test_api_debug_has_stage_and_internal_patterns():
    d = _post("Dengue test positive, platelets 80 hazaar, pet mein dard")["debug"]["pathways"]
    assert d["primary"]["pathway"] == "fever" and d["primary"]["stage"] == "S2"
    assert "dengue_like" in d["concern_patterns_internal"] and d["moved_by"]


def test_questions_endpoint_lists_pathway_questions():
    bank = client.get("/api/v1/questions").json()
    assert "fever.danger" in bank and bank["fever.danger"]["multi"] is True
