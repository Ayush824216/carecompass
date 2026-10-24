"""Safety rule-engine tests. Written by the team, not taken from any dataset.

Every commit touching backend/app/safety.py must keep these green.
"""
import pytest

from app import safety
from app.lang import detect_language, normalise

# (text, expected flag) — positive cases across English, Hinglish and Hindi
POSITIVE = [
    # chest pain
    ("My father has severe chest pain and is sweating", "chest_pain"),
    ("there is a heavy pressure in my chest since 20 minutes", "chest_pain"),
    ("Papa ke seene mein tez dard ho raha hai", "chest_pain"),
    ("mummy ko chhati mein bahut dard hai", "chest_pain"),
    ("sine me dard ho rha h", "chest_pain"),
    ("दादाजी के सीने में तेज़ दर्द हो रहा है", "chest_pain"),
    ("no fever but chest pain since morning", "chest_pain"),
    # breathing
    ("My mother cannot breathe properly", "severe_breathing_difficulty"),
    ("he is struggling to breathe and gasping", "severe_breathing_difficulty"),
    ("shortness of breath while sitting", "severe_breathing_difficulty"),
    ("Dadi ko saans nahi aa rahi", "severe_breathing_difficulty"),
    ("papa ki saans bahut phool rahi hai, bol nahi pa rahe", "severe_breathing_difficulty"),
    ("bachche ko saans lene mein dikkat ho rahi hai", "severe_breathing_difficulty"),
    ("मम्मी को साँस लेने में बहुत तकलीफ हो रही है", "severe_breathing_difficulty"),
    ("नानी की सांस फूल रही है", "severe_breathing_difficulty"),
    # blue lips
    ("his lips are turning blue", "blue_lips"),
    ("baby ke hont neele pad gaye", "blue_lips"),
    ("बच्चे के होंठ नीले हो गए हैं", "blue_lips"),
    # unconscious
    ("Grandfather fainted and is not responding", "unconscious"),
    ("She collapsed in the kitchen", "unconscious"),
    ("Papa behosh ho gaye hain", "unconscious"),
    ("dadi hosh mein nahi hain, jawab nahi de rahi", "unconscious"),
    ("पापा बेहोश हो गए हैं", "unconscious"),
    # seizure
    ("my son is having a seizure", "seizure"),
    ("She had a fit and her body was jerking", "seizure"),
    ("bete ko daura pad raha hai", "seizure"),
    ("भाई को मिर्गी का दौरा पड़ा है", "seizure"),
    # stroke
    ("his speech is slurred and face is drooping", "stroke_signs"),
    ("suddenly her left side is weak", "stroke_signs"),
    ("nana ji ki awaaz ladkhada rahi hai", "stroke_signs"),
    ("papa ka chehra ek taraf tedha ho gaya hai", "stroke_signs"),
    ("दादी का चेहरा एक तरफ टेढ़ा हो गया और बोली लड़खड़ा रही है", "stroke_signs"),
    # bleeding
    ("He cut his leg and it is bleeding heavily", "heavy_bleeding"),
    ("accident ke baad bahut khoon beh raha hai", "heavy_bleeding"),
    ("khoon ruk nahi raha", "heavy_bleeding"),
    ("पापा को खून की उल्टी हुई", "heavy_bleeding"),
    # allergy
    ("after eating peanuts her face is swelling up", "severe_allergic_reaction"),
    ("uska chehra aur hont sooj gaye hain", "severe_allergic_reaction"),
    ("दवा के बाद चेहरा सूज गया है", "severe_allergic_reaction"),
    # suicidal
    ("I don't want to live anymore", "suicidal_intent"),
    ("my brother is talking about suicide", "suicidal_intent"),
    ("mujhe ab jeena nahi hai", "suicidal_intent"),
    ("wo khud ko khatam karna chahta hai", "suicidal_intent"),
    ("मैं आत्महत्या करना चाहता हूँ", "suicidal_intent"),
    # poisoning
    ("my child swallowed some bleach", "poisoning_overdose"),
    ("she took too many sleeping pills", "poisoning_overdose"),
    ("chachi ne zeher kha liya", "poisoning_overdose"),
    ("बच्चे ने चूहे मारने की दवा खा ली", "poisoning_overdose"),
    ("papa ko saanp ne kaat liya", "poisoning_overdose"),
    # burns
    ("he got badly burned with boiling water on his chest", "severe_burns"),
    ("rasoi mein aag lag gayi, mummy jal gayi", "severe_burns"),
    ("बच्चा गरम तेल से जल गया", "severe_burns"),
    # trauma
    ("bike accident, his leg looks broken", "major_trauma"),
    ("dada ji chhat se gir gaye", "major_trauma"),
    # mental state
    ("grandma is suddenly confused and not recognising us", "altered_mental_state"),
    ("nani behki behki baatein kar rahi hain", "altered_mental_state"),
    # combos
    ("high fever with a stiff neck", "fever_stiff_neck_confusion"),
    ("bete ko tez bukhar hai aur gardan akad gayi hai", "fever_stiff_neck_confusion"),
    ("My 2 month old baby has high fever", "infant_danger_signs"),
    ("3 mahine ka baby doodh nahi pee raha", "infant_danger_signs"),
    ("मेरे दो महीने के बच्चे को तेज़ बुखार है", "infant_danger_signs"),
    ("my wife is pregnant and bleeding", "pregnancy_emergency"),
    ("wife 7 mahine pregnant hai aur bahut tez dard ho raha hai", "pregnancy_emergency"),
    ("मेरी पत्नी गर्भवती है और खून आ रहा है", "pregnancy_emergency"),
    ("he fell and hit his head and now he is vomiting", "severe_head_injury"),
    ("sar par chot lagi aur ulti ho rahi hai", "severe_head_injury"),
]

# benign / negated — must NOT fire any flag
BENIGN = [
    "Papa ko do din se bukhar hai aur khansi bhi",
    "fever and cough for 2 days, no breathing difficulty",
    "saans lene mein dikkat nahi hai, bas khansi hai",
    "saans ki dikkat nahi hai",
    "no chest pain, just acidity after meals",
    "seene mein dard nahi hai, gas ki problem hai",
    "सीने में दर्द नहीं है, बस खांसी है",
    "साँस की दिक्कत नहीं है",
    "mild headache since yesterday",
    "My mother needs a BP and sugar check at home",
    "small cut on finger, thoda khoon nikla tha, dressing chahiye",
    "papa bilkul fit hain, bas checkup karwana hai",
    "my wife is 5 months pregnant and needs a routine checkup",
    "pregnant hai, blood test karwana hai",
    "knee pain for 6 months, worse on stairs",
    "zukaam aur cheenk aa rahi hai",
    "mujhe 3 din se dast ho rahe hain par paani pee raha hoon",
    "dadi ko ghutno mein dard hai",
    "He is not unconscious, he is talking normally",
    "behosh nahi hue, bas chakkar aaya",
    "bachche ko halka bukhar hai, khel raha hai",
    "need wound dressing after surgery",
    "Doctor ne injection bataye hain, roz lagwane hain",
    "khane ke baad seene mein jalan hoti hai",
    "मम्मी को घुटनों में दर्द है",
]


@pytest.mark.parametrize("text,flag", POSITIVE)
def test_positive(text, flag):
    res = safety.check([text])
    assert flag in res.red_flags, (text, res.red_flags)


@pytest.mark.parametrize("text", BENIGN)
def test_benign(text):
    res = safety.check([text])
    assert res.red_flags == [], (text, res.evidence)


def test_counts():
    assert len(POSITIVE) >= 40 and len(BENIGN) >= 15


def test_history_union():
    # red flag mentioned in an earlier user turn is still caught
    res = safety.check(["papa ko bukhar hai", "haan", "aur abhi behosh ho gaye"])
    assert "unconscious" in res.red_flags


def test_combo_across_turns():
    res = safety.check(["bete ko tez bukhar hai", "gardan bhi akad gayi hai"])
    assert "fever_stiff_neck_confusion" in res.red_flags


def test_extra_flags_union():
    res = safety.check(["fever and cough"], extra_flags=["severe_breathing_difficulty"])
    assert res.is_emergency


def test_emergency_reasoning_languages():
    for lang, needle in (("en", "112"), ("hi", "112"), ("hinglish", "108")):
        msg = safety.emergency_reasoning(["chest_pain"], lang)
        assert needle in msg
    assert "14416" in safety.emergency_reasoning(["suicidal_intent"], "en")


@pytest.mark.parametrize("text,lang", [
    ("Papa ko do din se bukhar hai", "hinglish"), ("मुझे बुखार है", "hi"),
    ("My father has fever", "en"), ("sir dard ho raha hai", "hinglish"), ("headache since morning", "en"),
])
def test_detect_language(text, lang):
    assert detect_language(text) == lang


def test_normalise():
    n = normalise("Papa ko do din se bukhar hai aur khansi bhi")
    assert "fever" in n and "cough" in n and "father" in n
    assert "fever" in normalise("दो दिन से बुखार है")


# regressions found on the hand-written challenge set
@pytest.mark.parametrize("text", [
    "My father was discharged after a stroke and needs help with daily care and a feeding tube at home",
    "Didi ko periods mein bahut zyada bleeding ho rahi hai 2 mahine se",
    "Saans phoolti hai seedhi chadhne par, 6 mahine se",
    "My dad's legs have been swelling up for a month and he gets breathless walking",
    "papa ko pichle saal lakwa hua tha, ab physiotherapy chahiye",
])
def test_regression_benign(text):
    assert safety.check([text]).red_flags == [], text


@pytest.mark.parametrize("text,flag", [
    ("बेटे का हाथ टूट गया लगता है, हड्डी टेढ़ी दिख रही है", "major_trauma"),
    ("bete ka haath toot gaya", "major_trauma"),
    ("his arm looks broken after the fall", "major_trauma"),
    ("breathless even while sitting for 2 months, getting worse", "severe_breathing_difficulty"),
    ("he had a stroke last year and now suddenly his speech is slurred again", "stroke_signs"),
])
def test_regression_positive(text, flag):
    assert flag in safety.check([text]).red_flags, text


@pytest.mark.parametrize("text,flag", [
    ("My 3 week old baby has a temperature", "infant_danger_signs"),
    ("navjaat baby ko bukhar hai", "infant_danger_signs"),
    ("तीन हफ्ते के बच्चे को बुखार है", "infant_danger_signs"),
    ("My wife is 8 months pregnant and the baby has not moved since morning", "pregnancy_emergency"),
    ("pregnant hoon, subah se bachcha hil nahi raha", "pregnancy_emergency"),
])
def test_infant_and_pregnancy_extra(text, flag):
    assert flag in safety.check([text]).red_flags, text


def test_older_baby_mild_fever_is_not_flagged():
    assert safety.check(["mere 10 mahine ke bete ko halka bukhar hai, khel raha hai"]).red_flags == []


# regressions from blind challenge set v2 (general phrasings, not the exact sentences)
@pytest.mark.parametrize("text,flag", [
    ("I can't see properly from my right eye since this morning", "sudden_vision_loss"),
    ("papa ko achanak ek aankh se dikhna band ho gaya", "sudden_vision_loss"),
    ("there is a deep cut on his leg, it keeps bleeding through the cloth", "heavy_bleeding"),
    ("the wound is still bleeding after 20 minutes of pressing", "heavy_bleeding"),
    ("a small child is bleeding heavily from the head", "heavy_bleeding"),
    ("my grandmother has a fever and is talking strangely", "fever_stiff_neck_confusion"),
    ("he is shaking all over and frothing at the mouth", "seizure"),
    ("munh se jhaag aa raha hai aur poora sharir akad gaya", "seizure"),
    ("my wife says she wants to end it all", "suicidal_intent"),
    ("bas ab zindagi khatam kar dunga", "suicidal_intent"),
])
def test_regression_v2_positive(text, flag):
    assert flag in safety.check([text]).red_flags, text


@pytest.mark.parametrize("text", [
    "fever with chills, shaking all over from the cold",
    "my vision has been getting blurry slowly for 6 months",
    "small cut on the finger, bleeding a bit",
    "dog bit my son, small wound, thoda khoon nikla",
])
def test_regression_v2_benign(text):
    assert safety.check([text]).red_flags == [], text


@pytest.mark.parametrize("text,flag", [
    ("He suddenly can't lift his right arm and his words are coming out jumbled", "stroke_signs"),
    ("My mom's face has suddenly gone crooked on one side", "stroke_signs"),
    ("papa ek haath utha nahi pa rahe", "stroke_signs"),
    ("Uncle is sweating a lot and has pain going down his left arm", "chest_pain"),
    ("baayein haath mein dard aur paseena", "chest_pain"),
    ("Bacche ne galti se mitti ka tel pee liya", "poisoning_overdose"),
])
def test_regression_v1_rules(text, flag):
    assert flag in safety.check([text]).red_flags, text


def test_left_arm_negated():
    assert safety.check(["no pain in the left arm or jaw, just a sprained wrist"]).red_flags == []


def test_left_arm_pain_alone_is_not_flagged():
    assert safety.check(["left arm pain since I lifted a heavy box yesterday"]).red_flags == []


# regressions from blind challenge set v3
@pytest.mark.parametrize("text,flag", [
    ("Grandma slipped on the floor an hour ago, hip hurts a lot and she can't stand up", "major_trauma"),
    ("dadi gir gayi aur ab khadi nahi ho pa rahi", "major_trauma"),
    ("Papa ko diabetes hai, aaj sugar 45 aa gayi, paseena aa raha hai", "low_blood_sugar"),
    ("his sugar has dropped very low and he is confused", "low_blood_sugar"),
    ("मेरे दादाजी का पेशाब रुक गया है सुबह से", "urinary_retention"),
    ("he hasn't passed urine since last night and his belly hurts", "urinary_retention"),
])
def test_regression_v3_positive(text, flag):
    assert flag in safety.check([text]).red_flags, text


@pytest.mark.parametrize("text", [
    "My mother has bed sores and needs regular dressing, she is paralysed for years",
    "the catheter is not draining, urine nahi aa rahi bag mein",
    "doctor said keep sugar above 70",
    "sugar 300 aa rahi hai 5 din se",
    "slipped in the bathroom, small bruise on the knee, walking fine",
])
def test_regression_v3_benign(text):
    assert safety.check([text]).red_flags == [], text


@pytest.mark.parametrize("text", [
    "khoon ki kami hai, bahut kamzori lagti hai",
    "garbhvati hoon, doctor ne bola khoon ki kami hai",
    "khoon ki jaanch karayi thi, report normal",
    "Gym ke baad chest dabane par dard hota hai, 22 saal",
])
def test_pathway_spec_benign(text):
    assert safety.check([text]).red_flags == [], text


def test_chest_wall_exclusion_keeps_cardiac_features():
    assert "chest_pain" in safety.check(["chest dabane par dard aur bhaari pan, paseena"]).red_flags


@pytest.mark.parametrize("text", [
    "Burning in the chest after meals, 24 years old, nothing else",
    "burning sensation in urine since yesterday",
    "My husband has diabetes and gets chest discomfort on and off, not right now",
    "Didi ko sugar hai, seene mein kabhi kabhi takleef hoti hai, abhi nahi",
    "My old mother has had blurry vision for many months, difficulty reading",
])
def test_vignette_phrasings_benign(text):
    assert safety.check([text]).red_flags == [], text


@pytest.mark.parametrize("text", [
    "chest pain on and off, not right now, but he was sweating a lot",
    "seene mein kabhi kabhi bhaari dabav, abhi nahi",
    "severe burns on the chest and face",
])
def test_vignette_exclusions_keep_real_emergencies(text):
    assert safety.check([text]).red_flags, text
