"""Smart intake: slot extraction + follow-up policy (stateless; rebuilt from conversation_history every turn).

A follow-up is asked ONLY when a missing slot could change care_type or urgency and the local model is unsure.
Safety-screening questions come first. Never more than MAX_FOLLOWUPS questions, never after a red flag.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from .config import get_settings
from .lang import clean, normalise

# --- question bank --------------------------------------------------------------------------------
# options: (canonical value, en, hi, hinglish)
QUESTIONS: dict[str, dict] = {
    "breathing": {
        "en": "Is there any difficulty in breathing?",
        "hi": "क्या साँस लेने में तकलीफ हो रही है?",
        "hinglish": "Kya saans lene mein takleef ho rahi hai?",
        "options": [("yes", "Yes", "हाँ", "Haan"), ("no", "No", "नहीं", "Nahi")],
    },
    "chest": {
        "en": "Is there any chest pain or pressure, or pain spreading to the arm or jaw?",
        "hi": "क्या सीने में दर्द या दबाव है, या दर्द बाँह या जबड़े तक जा रहा है?",
        "hinglish": "Kya seene mein dard ya dabav hai, ya dard baah ya jabde tak ja raha hai?",
        "options": [("yes", "Yes", "हाँ", "Haan"), ("no", "No", "नहीं", "Nahi")],
    },
    "neck_confusion": {
        "en": "Is there a stiff neck, confusion or unusual sleepiness?",
        "hi": "क्या गर्दन में अकड़न, भ्रम या असामान्य नींद है?",
        "hinglish": "Kya gardan mein akdan, bhram ya bahut zyada neend hai?",
        "options": [("yes", "Yes", "हाँ", "Haan"), ("no", "No", "नहीं", "Nahi")],
    },
    "drinking": {
        "en": "Is the patient able to drink water and pass urine normally?",
        "hi": "क्या मरीज़ पानी पी पा रहे हैं और पेशाब ठीक से आ रहा है?",
        "hinglish": "Kya mareez paani pee pa rahe hain aur peshaab theek se aa raha hai?",
        "options": [("yes", "Yes", "हाँ", "Haan"), ("no", "No", "नहीं", "Nahi")],
    },
    "main_problem": {
        "en": "What is the main problem? You can say it in your own words.",
        "hi": "मुख्य परेशानी क्या है? अपने शब्दों में बताइए।",
        "hinglish": "Mukhya pareshani kya hai? Apne shabdon mein batayein.",
        "options": [("fever", "Fever", "बुखार", "Bukhar"), ("pain", "Pain", "दर्द", "Dard"),
                    ("injury", "Injury / wound", "चोट / घाव", "Chot / ghaav"),
                    ("care", "Nursing care at home", "घर पर नर्सिंग देखभाल", "Ghar par nursing dekhbhal"),
                    ("other", "Something else", "कुछ और", "Kuch aur")],
    },
    "duration": {
        "en": "Since when is this happening?",
        "hi": "यह कब से हो रहा है?",
        "hinglish": "Yeh kab se ho raha hai?",
        "options": [("hours", "Since today", "आज से", "Aaj se"), ("acute", "1–3 days", "1–3 दिन", "1–3 din"),
                    ("week", "About a week", "लगभग एक हफ्ता", "Lagbhag ek hafta"),
                    ("chronic", "More than a month", "एक महीने से ज़्यादा", "Ek mahine se zyada")],
    },
    "patient": {
        "en": "Who is the patient?",
        "hi": "मरीज़ कौन है?",
        "hinglish": "Mareez kaun hai?",
        "options": [("adult", "Myself / an adult", "मैं / कोई वयस्क", "Main / koi adult"),
                    ("elderly", "Elderly (60+)", "बुज़ुर्ग (60+)", "Buzurg (60+)"),
                    ("child", "Child", "बच्चा", "Bachcha"), ("infant", "Baby (under 1 year)", "शिशु (1 साल से छोटा)", "Baby (1 saal se chhota)")],
    },
    "severity": {
        "en": "How bad is it?",
        "hi": "तकलीफ कितनी ज़्यादा है?",
        "hinglish": "Takleef kitni zyada hai?",
        "options": [("mild", "Mild", "हल्की", "Halki"), ("moderate", "Moderate", "मध्यम", "Madhyam"),
                    ("severe", "Severe", "बहुत ज़्यादा", "Bahut zyada")],
    },
    "mobility": {
        "en": "Can the patient travel to a clinic easily?",
        "hi": "क्या मरीज़ आसानी से क्लिनिक जा सकते हैं?",
        "hinglish": "Kya mareez aasani se clinic ja sakte hain?",
        "options": [("yes", "Yes", "हाँ", "Haan"), ("no", "No", "नहीं", "Nahi")],
    },
}
YES_FLAG = {"breathing": "severe_breathing_difficulty", "chest": "chest_pain", "neck_confusion": "fever_stiff_neck_confusion"}
# canonical sentences fed to the classifier for answered slots (so a bare "haan"/"nahi" carries meaning)
FACT_TEXT = {
    ("breathing", "no"): "no breathing difficulty", ("chest", "no"): "no chest pain",
    ("neck_confusion", "no"): "no stiff neck no confusion", ("drinking", "yes"): "drinking fluids normally",
    ("drinking", "no"): "not able to drink fluids, very weak", ("mobility", "no"): "cannot travel, needs home visit",
    ("mobility", "yes"): "can travel", ("duration", "hours"): "since today", ("duration", "acute"): "for 2 days",
    ("duration", "week"): "for a week", ("duration", "chronic"): "for many months",
    ("patient", "elderly"): "elderly patient", ("patient", "child"): "child", ("patient", "infant"): "baby infant",
    ("patient", "adult"): "adult", ("severity", "mild"): "mild", ("severity", "moderate"): "moderate",
    ("severity", "severe"): "severe",
}

YES = re.compile(r"^\s*(yes|yeah|yep|y|haan|han|ha|haa|hanji|haanji|ji|ji haan|bilkul|sahi|right|correct|हाँ|हां|जी|जी हाँ|हाँ जी|बिल्कुल)\b", re.I)
NO = re.compile(r"^\s*(no|nope|n|nahi|nahin|nhi|nai|na|bilkul nahi|not really|नहीं|ना|नही|न)\b", re.I)


@lru_cache
def intake_cfg() -> dict:
    p = get_settings().config_dir / "intake.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def question_text(qid: str, lang: str) -> str:
    q = QUESTIONS[qid]
    return q.get(lang) or q["en"]


def identify_question(text: str) -> Optional[str]:
    t = clean(text).lower()
    for qid, q in QUESTIONS.items():
        for lang in ("en", "hi", "hinglish"):
            if q[lang].lower() == t or q[lang].lower() in t:
                return qid
    from .pathways import identify_question as pathway_question  # clinical pathway questions count too
    return pathway_question(text)


def parse_answer(qid: str, answer: str) -> Optional[str]:
    if qid not in QUESTIONS:  # pathway questions are parsed by the pathway engine (chips + free text)
        return None
    a = clean(answer)
    al = a.lower()
    for val, *labels in QUESTIONS[qid]["options"]:
        if any(al == l.lower() for l in labels) or al == val:
            return val
    if qid in ("breathing", "chest", "neck_confusion", "drinking", "mobility"):
        if NO.search(al):
            return "no"
        if YES.search(al):
            return "yes"
        return None
    s = extract_slots([a])
    return {"duration": s.duration, "patient": s.age_group, "severity": s.severity}.get(qid)


# --- slot extraction ------------------------------------------------------------------------------
SYMPTOMS: list[tuple[str, str]] = [
    ("high fever", r"high fever|very high temperature|10[2-5]\s*(f|degree)?"),
    ("fever", r"\bfever|temperature|taap|bukh?aa?r|बुखार|ताप"),
    ("cough", r"\bcough|kh?aa?n?si|खांसी|खाँसी"),
    ("cold", r"\bcold\b|runny nose|sneez|cheenk|zukaam|जुकाम|छींक"),
    ("sore throat", r"sore throat|throat pain|gale\s+(mein|me)\s+(dard|kharash)|खराश"),
    ("breathlessness", r"breathless|breathing difficulty|cannot breathe|short(ness)? of breath"),
    ("chest pain", r"chest pain|heart attack"),
    ("headache", r"headache|migraine"),
    ("abdominal pain", r"abdominal pain|stomach (pain|ache)|tummy"),
    ("vomiting", r"vomit|nausea|ji machal|मतली"),
    ("diarrhoea", r"diarrh|loose motion"),
    ("dizziness", r"dizz|vertigo|chakk?ar"),
    ("weakness", r"weak|fatigue|tired|thak"),
    ("rash", r"\brash|daane|dane|दाने|spots on skin|patches|daag|दाग"),
    ("itching", r"itch|khujli|खुजली"),
    ("acidity", r"acidity|heartburn|burning after|gas\b|bloat|pet phool"),
    ("swelling", r"swelling|swollen"),
    ("wound", r"wound|cut\b|dressing|ulcer|bedsore|sore on"),
    ("injury", r"injury|fell|fall\b|slipped|fisal|sprain|twist|moch|मोच|फिसल"),
    ("back pain", r"back pain|kamar\s+(mein|me)?\s*dard|कमर"),
    ("joint pain", r"knee|joint|ghutn|घुटन|jodo|जोड़"),
    ("vision problem", r"vision|blur|dhundhl|धुंधल|eyesight"),
    ("hearing problem", r"hearing|sunai|सुनाई"),
    ("high sugar", r"\bsugar|diabet|glucose|शुगर"),
    ("blood pressure", r"\bbp\b|blood pressure|बीपी"),
    ("low mood", r"\bsad\b|feeling low|udaas|उदास|depress|anxious|ghabrahat|घबराहट"),
    ("sleep problem", r"not sleeping|insomnia|neend nahi|नींद नहीं"),
    ("palpitations", r"palpitation|heartbeat|dhadkan|धड़कन"),
    ("lump", r"\blump|gaanth|गांठ"),
    ("pain", r"\bpain\b|ache|dard|दर्द"),
    ("nursing need", r"injection|drip|\biv\b|catheter|feeding tube|nurse|post[- ]?op|surgery|operation|ऑपरेशन|इंजेक्शन|ड्रिप|stitches|taank|टांक"),
    ("checkup", r"check ?up|blood test|sample|report|test result|जाँच|रिपोर्ट"),
    ("pregnancy", r"pregnan|garbh|गर्भ"),
    ("development", r"not speaking|not walking|speech delay|bolta nahi|बोलता नहीं"),
]
_SYM_C = [(n, re.compile(p, re.I)) for n, p in SYMPTOMS]
RESPIRATORY = {"fever", "high fever", "cough", "cold", "sore throat"}

NUM = r"(\d+|ek|do|teen|char|chaar|paanch|panch|chhe|saat|one|two|three|four|five|six|seven|a|an|एक|दो|तीन|चार|पाँच|पांच|छह|सात|कई|kai|many|few|several)"
AGE_NOT = r"(?![a-zA-Z])(?!\s*-?\s*(ka|ki|ke|old|का|की|के)(\s|$|[,.]))"  # "8 mahine ka baby" is an age, not a duration
DUR_PATTERNS = [
    ("chronic", rf"{NUM}?\s*(months?|mahin[eao]n?|mahina|years?|saal|sal\b|महीनों|महीने|महीना|साल){AGE_NOT}"),
    ("week", rf"{NUM}?\s*(weeks?|hafte|hafta|हफ्ते|हफ़्ते|हफ्ता){AGE_NOT}|\b(5|6|7|8|9|10|11|12|13|14|paanch|panch|saat|das)\s*(days|din|दिन)|पाँच दिन|दस दिन"),
    ("acute", rf"\b(1|2|3|4|ek|do|teen|char|one|two|three|four|couple of)\s*(days?|din|दिन)|kal se|since yesterday|yesterday|कल से|parso|परसों|\bdo din|\bदो दिन|तीन दिन"),
    ("hours", r"today|this morning|since morning|subah se|aaj se|aaj subah|abhi|just now|hours?\b|ghante|घंटे|सुबह से|आज|minutes?|minute"),
]
_DUR_C = [(b, re.compile(p, re.I)) for b, p in DUR_PATTERNS]

AGE_PATTERNS = [
    ("infant", r"\b(baby|infant|newborn|navjaat|shishu)\b|\b\d{1,2}\s*(months?|mahine|mahina)\s*(old|ka|ki|ke)\b|नवजात|शिशु|महीने के बच्चे|महीने का बच्चा"),
    ("elderly", r"grand(father|mother|ma|pa)|\bold\b|elderly|\bdadi|\bdada|\bnani\b|\bnana\b|budh|buzurg|bujurg|बुज़ुर्ग|दादी|दादा|नानी|नाना|\b([6-9]\d)\s*(years?|yrs?|saal|sal|साल)|aged\s+([6-9]\d)"),
    ("child", r"\b(son|daughter|child|kid|boy|girl|beta|bete|beti|bachch?[aei]|bacch?[aei])\b|बेटा|बेटे|बेटी|बच्च|\b([1-9]|1[0-5])\s*(years?|saal|sal|साल)\s*(old|ka|ki|ke|का|की|के)"),
    ("adult", r"\b(i|me|my wife|my husband|wife|husband|brother|sister|mujhe|main|bhai|didi|pati|patni|papa|mummy|father|mother|maa|abba|abbu|ammi)\b|मुझे|पत्नी|पति|भाई|दीदी|पापा|मम्मी"),
]
_AGE_C = [(g, re.compile(p, re.I)) for g, p in AGE_PATTERNS]
SEVERE = re.compile(r"\b(severe|very bad|unbearable|extreme|a lot|bahut|bohot|tez|tej|zyada|jyada)\b|बहुत|तेज़|तेज|ज़्यादा", re.I)
MILD = re.compile(r"\b(mild|slight|little|halka|halki|thoda|thodi|minor)\b|हल्का|हल्की|थोड़ा|थोड़ी", re.I)
IMMOBILE = re.compile(r"bedridden|bistar|बिस्तर|can'?t (walk|travel|go out|move)|cannot (walk|travel|go)|unable to (walk|travel)|"
                      r"bahar nahi ja|chal nahi (pa|sak)|बाहर नहीं जा|चल नहीं", re.I)
CHRONIC_COND = re.compile(r"diabet|sugar|\bbp\b|blood pressure|hypertension|heart|asthma|kidney|dialysis|cancer|thyroid|"
                          r"शुगर|बीपी|दिल|दमा", re.I)
BREATH_OK = re.compile(r"no breathing difficulty|breathing (is )?(fine|ok|normal)|saa?ns (theek|thik|normal|sahi)|"
                       r"breathing difficulty not|साँस ठीक|सांस ठीक", re.I)


def _duration_phrase(raw: str, m: re.Match) -> str:
    """The user's own duration words, extended to a trailing 'se'/'from'/'से' (e.g. 'do din se')."""
    start, end = m.start(), m.end()
    while end < len(raw) and not raw[end].isspace() and raw[end] not in ",.।!?":
        end += 1
    pre = raw[:start].split()
    if pre and pre[-1].lower() in ("for", "since", "last", "past", "about", "ek", "do", "teen", "पिछले"):
        start -= len(pre[-1]) + 1
    post = raw[end:].split()
    if post and post[0].lower().strip(",.") in ("se", "से", "ago", "pehle", "पहले"):
        end += raw[end:].find(post[0]) + len(post[0].strip(",."))
    return raw[start:end].strip(" ,.")


@dataclass
class Slots:
    symptoms: list[str] = field(default_factory=list)
    duration: Optional[str] = None
    duration_text: Optional[str] = None
    severity: Optional[str] = None
    age_group: Optional[str] = None
    patient: Optional[str] = None
    breathing: Optional[str] = None  # "ok" | "difficult" | None
    chronic_condition: bool = False
    can_travel: Optional[bool] = None
    answers: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)  # symptom -> span in the user's words (or the answer it came from)


def extract_slots(user_texts: list[str]) -> Slots:
    raw = " . ".join(clean(t) for t in user_texts if t)
    norm = normalise(raw)
    both = f"{raw.lower()} || {norm}"
    s = Slots()
    for name, rx in _SYM_C:
        if rx.search(both) and name not in s.symptoms:
            if name == "fever" and "high fever" in s.symptoms:
                continue
            if name == "pain" and any(x in s.symptoms for x in ("headache", "abdominal pain", "chest pain", "back pain",
                                                                 "joint pain", "sore throat")):
                continue
            s.symptoms.append(name)
    for b, rx in _DUR_C:
        m = rx.search(raw) or rx.search(both)
        if m:
            s.duration = b
            if rx.search(raw):
                s.duration_text = _duration_phrase(raw, rx.search(raw))
            break
    for g, rx in _AGE_C:
        m = rx.search(both)
        if m:
            s.age_group, s.patient = g, m.group(0)
            break
    s.severity = "severe" if SEVERE.search(both) else ("mild" if MILD.search(both) else None)
    s.chronic_condition = bool(CHRONIC_COND.search(both))
    if IMMOBILE.search(both):
        s.can_travel = False
    if BREATH_OK.search(both):
        s.breathing = "ok"
    return s


# --- conversation parsing -------------------------------------------------------------------------
@dataclass
class IntakeState:
    user_texts: list[str]
    slots: Slots
    asked: list[str]
    n_assistant_questions: int
    extra_flags: list[str]
    model_text: str  # user text + canonical facts, used by the classifier


def build_state(user_input: str, history: list[dict]) -> IntakeState:
    turns = [(t.get("role", "user"), t.get("content", "") or "") for t in history]
    if not turns or turns[-1] != ("user", user_input):
        turns.append(("user", user_input))
    user_texts, asked, extra, facts = [], [], [], []
    answers: dict[str, str] = {}
    n_q = 0
    pending: Optional[str] = None
    for role, content in turns:
        if role == "assistant":
            pending = identify_question(content)
            if pending:  # only real clinical follow-ups count toward the limit (redirects do not)
                n_q += 1
            if pending:
                asked.append(pending)
            continue
        if role != "user" or not content.strip():
            continue
        val = parse_answer(pending, content) if pending else None
        if val is not None:
            answers[pending] = val
            if val == "yes" and pending in YES_FLAG:
                extra.append(YES_FLAG[pending])
            facts.append(FACT_TEXT.get((pending, val), ""))
            if pending == "main_problem" or len(content.split()) > 2:  # free text may carry new symptoms
                user_texts.append(content)
        else:
            user_texts.append(content)
        pending = None
    facts = [f for f in facts if f]
    slots = extract_slots(user_texts + facts)
    slots.answers = answers
    # hallucination control: a symptom stays only with a span in the user's words, or when it comes from the
    # canonical text of one of the user's own answers (e.g. "No" to "able to drink?" -> very weak)
    from . import evidence
    spans: dict[str, dict] = {}
    for sp in evidence.find(user_texts):
        spans.setdefault(sp.label, sp.as_dict())
    from_answers = set(extract_slots(facts).symptoms) if facts else set()
    slots.symptoms = [x for x in slots.symptoms if x in spans or x in from_answers]
    slots.evidence = {x: spans.get(x) or {"kind": "answer", "label": x, "text": None, "start": None, "end": None,
                                          "turn": None} for x in slots.symptoms}
    if answers.get("breathing") == "no":
        slots.breathing = "ok"
    elif answers.get("breathing") == "yes":
        slots.breathing = "difficult"
    if answers.get("mobility") in ("yes", "no"):
        slots.can_travel = answers["mobility"] == "yes"
    for k, attr in (("duration", "duration"), ("patient", "age_group"), ("severity", "severity")):
        if answers.get(k):
            setattr(slots, attr, answers[k])
    model_text = " . ".join(user_texts + facts) or user_input
    return IntakeState(user_texts=user_texts or [user_input], slots=slots, asked=asked,
                       n_assistant_questions=n_q, extra_flags=extra, model_text=model_text)


# --- follow-up policy -----------------------------------------------------------------------------
SCREEN_CHEST = {"palpitations", "low mood", "abdominal pain", "acidity"}  # "ghabrahat", sweating, upper-belly pain


def _confident(probs: Optional[dict]) -> bool:
    if not probs:
        return False
    cfg = intake_cfg()
    pc, pu = probs.get("care_type", {}), probs.get("urgency", {})
    return (max(pc.values(), default=0) >= cfg.get("min_care_conf", 0.5)
            and max(pu.values(), default=0) >= cfg.get("min_urgency_conf", 0.5))


def choose_followup(state: IntakeState, probs: Optional[dict]) -> Optional[str]:
    """Return the id of the single most useful next question, or None to decide now."""
    if state.n_assistant_questions >= get_settings().max_followups:
        return None
    s, asked = state.slots, set(state.asked)
    syms = set(s.symptoms)
    sweaty = bool(re.search(r"sweat|paseen|pasina|पसीना|ghabrah|घबराह|left arm|jaw|jabda", " ".join(state.user_texts), re.I))

    def ok(q: str) -> bool:
        return q not in asked

    if not syms and ok("main_problem"):
        return "main_problem"
    # 1) high-risk screening: asked even when the model is confident, because a "yes" makes it an emergency
    if ("high fever" in syms and ("headache" in syms or s.age_group in ("child", "infant"))) and ok("neck_confusion"):
        return "neck_confusion"
    if (sweaty or ("palpitations" in syms) or (s.age_group == "elderly" and syms & SCREEN_CHEST)) and ok("chest"):
        return "chest"
    if s.age_group == "infant" and syms & RESPIRATORY and s.breathing is None and ok("breathing"):
        return "breathing"
    if s.age_group in ("infant", "elderly") and syms & {"vomiting", "diarrhoea"} and ok("drinking"):
        return "drinking"
    if _confident(probs):
        return None
    # 2) uncertainty-driven: only slots that can move care type or urgency, safety first
    if syms & RESPIRATORY and s.breathing is None and ok("breathing"):
        return "breathing"
    if s.duration is None and ok("duration"):
        return "duration"
    if s.age_group is None and ok("patient"):
        return "patient"
    if s.severity is None and ok("severity"):
        return "severity"
    if s.age_group == "elderly" and s.can_travel is None and ok("mobility"):
        return "mobility"
    return None


def count_initial_followups(text: str) -> int:
    """Used by evaluate.py: would the policy ask a question on the first turn? (0/1)."""
    from . import safety
    from .textclf import best_local_model
    st = build_state(text, [])
    if safety.check(st.user_texts).is_emergency:
        return 0
    m = best_local_model()
    probs = m.predict_proba(st.model_text) if m else None
    return int(choose_followup(st, probs) is not None)
