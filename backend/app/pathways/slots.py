"""Numeric and contextual slot parser for the clinical pathways (spec section 0.4 / 0.5 / 6).

Extracts from free text in English, Hinglish and Devanagari:
  temperature (°C/°F auto-detect, "tez bukhar" without a number), duration in days ("parso se", "kal raat se",
  weeks, months), age (months/years, family words), platelets ("40k", "40 hazaar", "0.4 lakh"), BP ("180/110"),
  counts ("10 baar ulti"), hours without urine, blood amount, pregnancy (+ weeks), comorbidities, bedridden.
Also separates context that must NOT count as the patient's current symptoms:
  someone else's illness ("padosi ko dengue hua tha"), past history ("pichle saal malaria hua tha"), and
  diseases the user names ("mujhe lagta hai dengue hai"), which are recorded internally and never confirmed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..lang import clean

NUMW = {
    "ek": 1, "one": 1, "a": 1, "an": 1, "do": 2, "two": 2, "teen": 3, "three": 3, "char": 4, "chaar": 4, "four": 4,
    "paanch": 5, "panch": 5, "five": 5, "chhe": 6, "chhah": 6, "che": 6, "six": 6, "saat": 7, "seven": 7, "aath": 8,
    "eight": 8, "nau": 9, "nine": 9, "das": 10, "ten": 10, "gyarah": 11, "barah": 12, "pandrah": 15,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5, "छह": 6, "छः": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
}
NUM = r"(\d+(?:\.\d+)?|" + "|".join(sorted((re.escape(k) for k in NUMW), key=len, reverse=True)) + r")"
DEVA_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _num(s: Optional[str], default: float = 1.0) -> float:
    if s is None:
        return default
    s = s.strip().lower()
    if s in NUMW:
        return float(NUMW[s])
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return default


def _rx(p: str) -> re.Pattern:
    return re.compile(p, re.I)


# ---------------------------------------------------------------- context filters
THIRD_PARTY = _rx(r"\b(padosi|padosan|pados|neighbou?rs?|dost|friends?|colleague|mohall\w*|society\s+mein|area\s+mein|"
                  r"unke\s+ghar|kisi\s+aur|someone\s+else)\b|पड़ोसी|पड़ोस|दोस्त")
PAST = _rx(r"\b(pichle|pichhle|last)\s+(saal|sal|year|mahine|month)\b|\b\d+\s+(saal|years?|mahine|months?)\s+"
           r"(pehle|ago)\b|\bhistory\s+of\b|\bhad\s+\w+\s+(last|before|ago)\b|पिछले\s+साल|साल\s+पहले")
# "hua tha" marks past history only when the clause also names a disease ("bukhar 3 din pehle shuru hua tha" is current)
PAST_DISEASE = _rx(r"\b(hua|hui|hue)\s+(tha|thi|the)\b|हुआ\s+था|हुई\s+थी|\bhad\b")
END = r"(?![\wऀ-ॿ])"  # word end that also works after Devanagari vowel signs
# clause splitter that keeps decimals ("100.8", "0.4 lakh") and thousands ("40,000") intact
SPLIT = re.compile(r"(?<!\d)[.,](?!\d)|(?<=\d)[.,](?!\d)|(?<!\d)[.,](?=\d)|[;!?।|\n]+|\s(?:but|however|although|lekin|magar|par\s+ab|लेकिन|मगर)\s", re.I)


def split_clauses(text: str) -> list[str]:
    return [c.strip() for c in SPLIT.split(text) if c and c.strip()]
# words that keep a "past" clause relevant (known conditions are risk factors, not current symptoms)
NAMED = {
    "dengue": r"\bdengue|डेंगू", "malaria": r"\bmalaria|मलेरिया", "typhoid": r"\btyphoid|टाइफाइड",
    "chikungunya": r"chikun?gunya|चिकनगुनिया", "jaundice": r"\bjaundice|\bhepatitis", "tuberculosis": r"\btb\b|tuberculosis|टीबी",
    "pneumonia": r"pneumonia|निमोनिया", "covid": r"\bcovid|\bcorona", "uti": r"\buti\b|urine\s+infection",
}
NAMED_C = {k: _rx(v) for k, v in NAMED.items()}
CORRECTION = _rx(r"\b(nahi|nahin|no)\s*,?\s*(ruko|wait|actually)\b|\bactually\b|\bi\s+mean\b|\bmatlab\b|\bnahi\s+nahi\b|असल में|रुको")


@dataclass
class Slots:
    temp_f: Optional[float] = None
    high_fever_reported: bool = False
    mild_fever_reported: bool = False
    duration_days: Optional[float] = None
    age_years: Optional[float] = None
    age_group: Optional[str] = None  # infant | child | adult | elderly
    platelets: Optional[int] = None
    bp_sys: Optional[int] = None
    bp_dia: Optional[int] = None
    bp_high_reported: bool = False
    vomit_count: Optional[int] = None
    stool_count: Optional[int] = None
    urine_absent_hours: Optional[float] = None
    blood_amount: Optional[str] = None  # small | large
    pregnant: bool = False
    pregnancy_weeks: Optional[float] = None
    comorbidities: list[str] = field(default_factory=list)
    hypertension: bool = False
    smoker: bool = False
    bedridden: bool = False
    named_diseases: list[str] = field(default_factory=list)      # current, user-named (never confirmed)
    context_diseases: list[str] = field(default_factory=list)    # someone else's / past history
    patient_clauses: list[str] = field(default_factory=list)     # clauses about the patient, now
    correction: bool = False

    @property
    def effective_temp_f(self) -> Optional[float]:
        """Measured value, else 102°F when the user says 'tez bukhar' without a number (spec edge case 4)."""
        if self.temp_f is not None:
            return self.temp_f
        return 102.0 if self.high_fever_reported else None


# ---------------------------------------------------------------- individual parsers
FEVER_WORD = _rx(r"fever|bukh?aa?r|bukar|bhukar|temperature|\btemp\b|taap|tapman|बुखार|तापमान|ताप")
NOT_TEMP_AFTER = _rx(r"^\s*(-|to|se)?\s*\d*\s*(saal|sal|years?|yrs?|din|days?|baar|bar|times|hafte|weeks?|mahin\w*|months?|"
                     r"ghante|hours?|k\b|hazaa?r|thousand|lakh|lac|/|%|mg|kg|min|bpm|ml|साल|दिन|बार|हफ्त|महीन|घंटे|हज़ार|हजार|लाख)")
NOT_TEMP_BEFORE = _rx(r"(bp|blood\s+pressure|platelets?|plate\s*let|plt|sugar|hb|wbc|age|umar|aged|बीपी|प्लेटलेट|शुगर)\s*\S{0,6}\s*$")
TEMP = _rx(r"(?<![\d/.,])(\d{2,3}(?:\.\d{1,2})?)\s*(°\s*[cf]?|deg\w*|fahrenheit|celsius|\bf\b|\bc\b)?")
HIGH_FEVER = _rx(r"\b(tez|tej|bahut\s+tez|bahut|high|very\s+high|severe|heavy)\s+(bukh?aa?r|bukar|fever|temperature|temp)\b|"
                 r"\b(bukh?aa?r|fever)\s+(bahut\s+)?(tez|tej|high)\b|तेज़?\s*बुखार|बहुत\s*बुखार|बुखार\s*बहुत")
MILD_FEVER = _rx(r"\b(halka|halki|thoda|mild|low|slight)\s+(sa\s+)?(bukh?aa?r|fever|temperature)\b|हल्का\s*बुखार")


def parse_temperature(text: str) -> tuple[Optional[float], bool, bool]:
    t = text.lower()
    best: Optional[float] = None
    for m in TEMP.finditer(t):
        v = float(m.group(1))
        unit = (m.group(2) or "").lower()
        if NOT_TEMP_AFTER.match(t[m.end():]) or NOT_TEMP_BEFORE.search(t[max(0, m.start() - 16):m.start()]):
            continue
        near_fever = bool(FEVER_WORD.search(t[max(0, m.start() - 40):m.end() + 30]))
        if not unit and not near_fever:
            continue
        if 35 <= v <= 43 and "f" not in unit:
            f = v * 9 / 5 + 32
        elif 95 <= v <= 110:
            f = v
        else:
            continue
        best = f if best is None else max(best, f)
    return (round(best, 1) if best is not None else None), bool(HIGH_FEVER.search(t)), bool(MILD_FEVER.search(t))


NOT_PREG = r"(?!\s*(ki\s+|ka\s+|se\s+)?(pregnan|garbh|गर्भ|प्रेग्))"
DURATION_RULES: list[tuple[re.Pattern, object]] = [
    (_rx(r"\bparso\s*(raat|subah|shaam)?\s*se\b|day\s+before\s+yesterday|परसों"), 2.0),
    (_rx(r"\bkal\s*(raat|subah|shaam|dopahar)?\s*se\b|since\s+(last\s+night|yesterday)|\byesterday\b|कल\s*(रात|सुबह|शाम)?\s*से"), 1.0),
    (_rx(r"\baaj\s*(subah|subha|dopahar|shaam)?\s*se\b|\bsubh?ah?\s+se\b|since\s+(this\s+)?morning|\btoday\b|आज\s*(सुबह)?\s*से|सुबह\s*से"), 0.3),
    (_rx(rf"{NUM}\s*(?:-|–|to|se)\s*{NUM}\s*(din|dino|days?|दिन)"), "range_days"),
    (_rx(rf"{NUM}\s*(din|dino|dinon|days?|दिन)(?!\s*-?\s*(ka|ki|ke|old|का|की|के){END})"), "days"),
    (_rx(r"\b(hafte|hafta)\s+bhar\b|a\s+week"), 7.0),
    (_rx(rf"{NUM}?\s*(hafte|hafta|haftey|weeks?|हफ्ते|हफ़्ते|हफ्ता)(?!\s*-?\s*(ka|ki|ke|old|का|की|के){END}){NOT_PREG}"), "weeks"),
    (_rx(r"\bmahine\s+bhar\b|a\s+month"), 30.0),
    (_rx(rf"{NUM}?\s*(mahine|mahina|mahino|months?|महीने|महीना|महीनों)(?![a-z])(?!\s*-?\s*(ka|ki|ke|old|का|की|के){END}){NOT_PREG}"), "months"),
    (_rx(rf"{NUM}\s*(saal|sal|years?|साल)\s*(se|से|for|since)\b"), "years"),
    (_rx(rf"{NUM}\s*(ghante|ghanton|hours?|hrs?|घंटे)"), "hours"),
]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_duration(text: str, today: Optional[datetime] = None) -> Optional[float]:
    t = text.lower()
    found: list[float] = []
    for rx, kind in DURATION_RULES:
        for m in rx.finditer(t):
            if isinstance(kind, float):
                found.append(kind)
            elif kind == "range_days":
                found.append(max(_num(m.group(1)), _num(m.group(2))))
            elif kind == "days":
                found.append(_num(m.group(1)))
            elif kind == "weeks":
                found.append(7 * _num(m.group(1)))
            elif kind == "months":
                found.append(30 * _num(m.group(1)))
            elif kind == "years":
                found.append(365 * _num(m.group(1)))
            elif kind == "hours":
                found.append(_num(m.group(1)) / 24)
    m = re.search(r"since\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", t)
    if m:
        today = today or datetime.now()
        diff = (today.weekday() - WEEKDAYS.index(m.group(1))) % 7 or 7
        found.append(float(diff))
    return max(found) if found else None


AGE_YEARS = [
    _rx(rf"{NUM}\s*(saal|sal|years?|yrs?|साल)\s*(ka|ki|ke|old|का|की|के|ki\s+umar|of\s+age)\b"),
    _rx(rf"\b(umar|umr|age|aged|उम्र)\s*(hai\s+|is\s+|:\s*)?{NUM}"),
    _rx(rf"(?:^|[,.;]\s*){NUM}\s*(saal|sal|years?|yrs?|साल)\s*(?=[,.;]|$)"),
    _rx(rf"{NUM}\s*(saal|sal|years?|साल)\s+(ke|ki|ka|के|की)?\s*(papa|mummy|dada|dadi|nana|nani|father|mother|patient|aunt|uncle)"),
    _rx(rf"\b{NUM}\s*-?\s*(year|yr)\s*-?\s*old\b"),
]
AGE_MONTHS = _rx(rf"{NUM}\s*-?\s*(mahine|mahina|months?|महीने|महीना)\s*-?\s*(ka|ki|ke|old|का|की|के){END}")
AGE_WEEKS = _rx(rf"{NUM}\s*-?\s*(hafte|weeks?|din|days?|हफ्ते|दिन)\s*-?\s*(ka|ki|ke|old|का|की|के){END}")
INFANT_W = _rx(r"\b(newborn|new\s+born|navjaat|infant|shishu)\b|नवजात|शिशु")
CHILD_W = _rx(r"\b(baby|bachch?[aei]|bacch?[aei]|bachchi|beta|bete|beti|child|kid|son|daughter|toddler|school\s+jaane\s+wala)\b|बच्च|बेटा|बेटे|बेटी")
ELDER_W = _rx(r"\b(buzurg|bujurg|elderly|old\s+(man|woman|mother|father)|grand(father|mother|ma|pa)|dadi|daadi|dada|daada|"
              r"nani|naani|nana|naana)\b|बुज़ुर्ग|बुजुर्ग|दादी|दादा|नानी|नाना")


def parse_age(text: str) -> tuple[Optional[float], Optional[str]]:
    t = text.lower()
    m = AGE_MONTHS.search(t)
    if m:
        return round(_num(m.group(1)) / 12, 3), "infant" if _num(m.group(1)) < 12 else "child"
    m = AGE_WEEKS.search(t)
    if m and re.search(r"bach|baby|बच्च|infant|navjaat", t):
        unit = m.group(2)
        days = _num(m.group(1)) * (7 if unit.startswith(("h", "w", "ह")) else 1)
        return round(days / 365, 3), "infant"
    for rx in AGE_YEARS:
        m = rx.search(t)
        if m:
            g = [x for x in m.groups() if x and re.fullmatch(NUM, x)]
            if g:
                y = _num(g[0])
                if 0 < y < 115:
                    return y, ("child" if y < 12 else "elderly" if y >= 65 else "adult")
    if INFANT_W.search(t):
        return 0.05, "infant"
    if ELDER_W.search(t):
        return None, "elderly"
    if CHILD_W.search(t):
        return None, "child"
    return None, None


PLT = _rx(r"(?:platelets?|plate\s*lets?|platlets?|pletlets?|plt|प्लेटलेट[ऀ-ॿ]*)\s*(?:count)?\s*(?:is|hai|h|aaye|aayi|aaya|aa\s+gaye|ho\s+gaye|:|-|=|ab)?\s*"
          r"(\d+(?:[.,]\d+)*)\s*(k\b|thousand|hazaa?r|hajaar|हज़ार|हजार|lakh|lac|लाख)?")
PLT_REV = _rx(r"(\d+(?:[.,]\d+)*)\s*(k\b|thousand|hazaa?r|hajaar|हज़ार|हजार|lakh|lac|लाख)?\s*(?:platelets?|plate\s*lets?|प्लेटलेट)")


def parse_platelets(text: str) -> Optional[int]:
    for rx in (PLT, PLT_REV):
        m = rx.search(text.lower())
        if m:
            raw, unit = m.group(1), (m.group(2) or "").lower()
            v = float(raw.replace(",", "")) if raw.count(",") or "." not in raw else float(raw)
            if unit in ("k", "thousand", "hazaar", "hazar", "hajaar", "हज़ार", "हजार"):
                v *= 1000
            elif unit in ("lakh", "lac", "लाख"):
                v *= 100000
            elif v < 1000:
                v *= 1000  # "platelets 80" in a report means 80,000
            return int(round(v))
    return None


BP = _rx(r"(?<![\d.])(\d{2,3})\s*(?:/|by|over|बटा)\s*(\d{2,3})(?![\d.])")
BP_HIGH = _rx(r"\bbp\s+(bahut\s+)?(high|badh|badha|zyada|jyada)|\bhigh\s+bp\b|blood\s+pressure\s+(is\s+)?(high|badh)|बीपी\s*(हाई|बढ़|ज़्यादा)")


def parse_bp(text: str) -> tuple[Optional[int], Optional[int], bool]:
    for m in BP.finditer(text):
        s, d = int(m.group(1)), int(m.group(2))
        if 80 <= s <= 260 and 40 <= d <= 160 and s > d:
            return s, d, bool(BP_HIGH.search(text)) or s >= 140
    return None, None, bool(BP_HIGH.search(text))


COUNT_V = [_rx(rf"{NUM}(?:\s*(?:-|–|to|se)\s*{NUM})?\s*(?:baar|bar|times|dafa|बार)\s*(?:ki\s+|se\s+)?(?:ulti|ultee|vomit\w*|उल्टी)"),
           _rx(rf"(?:ulti|ultee|vomit\w*|उल्टी)\w*\s+(?:\S+\s+){{0,3}}{NUM}(?:\s*(?:-|–|to)\s*{NUM})?\s*(?:baar|bar|times|बार)")]
COUNT_S = [_rx(rf"{NUM}(?:\s*(?:-|–|to|se)\s*{NUM})?\s*(?:baar|bar|times|dafa|बार)\s*(?:ki\s+|se\s+)?(?:dast|loose|potty|motion|latrine|stool|दस्त)"),
           _rx(rf"(?:dast|loose\s+motions?|potty|motions?|diarrh\w*|दस्त)\s+(?:\S+\s+){{0,3}}{NUM}(?:\s*(?:-|–|to)\s*{NUM})?\s*(?:baar|bar|times|बार)")]
GENERIC_COUNT = _rx(rf"(?:din\s+(?:mein|me)\s+|a\s+day\s+)?{NUM}(?:\s*(?:-|–|to)\s*{NUM})?\s*(?:baar|bar|times|बार)")


def _count(rules: list[re.Pattern], text: str) -> Optional[int]:
    for rx in rules:
        m = rx.search(text)
        if m:
            vals = [_num(g) for g in m.groups() if g]
            return int(max(vals))
    return None


URINE_ABSENT = [_rx(rf"{NUM}\s*(?:ghante|ghanton|hours?|hrs?|घंटे)\s*(?:se\s+)?(?:\S+\s+){{0,2}}(?:peshab|pishab|urine|pee|पेशाब)\s*(?:\S+\s+){{0,2}}(?:nahi|nhi|not|no|नहीं)"),
                _rx(rf"(?:peshab|pishab|urine|पेशाब)\s+(?:\S+\s+){{0,3}}(?:nahi|nhi|not|नहीं)\s+(?:\S+\s+){{0,3}}{NUM}\s*(?:ghante|hours?|घंटे)"),
                _rx(rf"(?:not|no|haven'?t|hasn'?t)\s+(?:passed\s+)?(?:any\s+)?urine\s+(?:\S+\s+){{0,3}}{NUM}\s*hours?")]
BLOOD_SMALL = _rx(r"dhaag|dhage|streak|thoda\s*sa|thodi\s*si|thoda|halka|lakeer|spots?|specks?|धागे|थोड़ा|थोड़ी")
BLOOD_LARGE = _rx(r"chammach|spoon|cup|katori|bahut|zyada|jyada|baar[- ]baar|repeated|clots?|thakke|bhar\s+ke|lots?\s+of|a\s+lot|चम्मच|बहुत|ज़्यादा|बार-बार")
BLOOD_WORD = _rx(r"kh[oo]+n|khun|blood|bleed|खून|ख़ून")

PREG = _rx(r"pregnan|pregnent|garbh|garbhvati|garbhwati|pet\s+se\s+(hai|hoon|hun)|expecting|गर्भ|प्रेग्नेंट")
PREG_M = _rx(rf"{NUM}\s*(?:mahine|mahina|months?|महीने)\s*(?:ki\s+|ka\s+|se\s+)?(?:pregnan|pregnent|garbh|गर्भ|प्रेग्)")
PREG_W = _rx(rf"{NUM}\s*(?:hafte|weeks?|हफ्ते)\s*(?:ki\s+|ka\s+)?(?:pregnan|pregnent|garbh|गर्भ)|pregnan\w*\s+(?:\S+\s+)?{NUM}\s*weeks?")
PREG_LEAD = _rx(rf"(?:pregnancy|garbh)\s+(?:ka|ki)\s+{NUM}\w*\s*(?:mahina|month)")
COMORB = {
    "diabetes": _rx(r"\bsugar\s+(hai|h\b|ki\s+bimari|patient|ke\s+mareez|ki\s+mareez|wale|wali)|\bdiabet\w*|madhumeh|शुगर\s*(है|की)|डायबिटीज|मधुमेह|sugar\s+patient"),
    "heart": _rx(r"heart\s+(patient|disease|problem|ki\s+bimari)|dil\s+(ki|ke)\s+(bimari|mareez|marij|patient)|\bstent|bypass|angioplasty|दिल\s*की\s*बीमारी|हृदय\s*रोग"),
    "kidney": _rx(r"kidney\s+(patient|disease|problem|ki\s+bimari|failure)|dialysis|गुर्दे|किडनी"),
    "liver": _rx(r"liver\s+(disease|problem|ki\s+bimari)|cirrhosis|लीवर\s*की\s*बीमारी"),
    "cancer": _rx(r"\bcancer|chemo\w*|कैंसर|कीमो"),
    "steroids": _rx(r"steroid|prednisolone|स्टेरॉयड"),
    "hiv": _rx(r"\bhiv\b|\baids\b"),
}
HTN = _rx(r"\bbp\s+(ki\s+)?(bimari|patient|ke\s+mareez|ki\s+mareez|hai\b|ki\s+dawai)|hypertension|\bhigh\s+bp\b|बीपी\s*(की|है)")
SMOKER = _rx(r"\bsmok\w*|cigarette|beedi|bidi|सिगरेट|बीड़ी")
BEDRIDDEN = _rx(r"bedridden|bed\s*ridden|bistar\s+(par|pe)|बिस्तर\s*पर|wheelchair|chal\s+nahi\s+(sakte|sakti|pate|paati)|cannot\s+(walk|travel)|can'?t\s+(walk|travel)")


def patient_clauses(text: str) -> tuple[list[str], list[str]]:
    """Split into clauses about the patient now vs context (someone else / past history)."""
    keep, context = [], []
    for cl in split_clauses(text):
        named = any(rx.search(cl) for rx in NAMED_C.values())
        if THIRD_PARTY.search(cl) or PAST.search(cl) or (named and PAST_DISEASE.search(cl)):
            context.append(cl)
        else:
            keep.append(cl)
    return keep, context


def parse(texts: list[str], today: Optional[datetime] = None) -> Slots:
    raw = " . ".join(clean(t).translate(DEVA_DIGITS) for t in texts if t)
    keep, context = patient_clauses(raw)
    now_text = " . ".join(keep)
    s = Slots(patient_clauses=keep)
    s.temp_f, s.high_fever_reported, s.mild_fever_reported = parse_temperature(now_text)
    s.duration_days = parse_duration(now_text, today)
    s.age_years, s.age_group = parse_age(raw)  # age words can sit in any clause
    s.platelets = parse_platelets(now_text)
    s.bp_sys, s.bp_dia, s.bp_high_reported = parse_bp(now_text)
    low = now_text.lower()
    s.vomit_count = _count(COUNT_V, low)
    s.stool_count = _count(COUNT_S, low)
    if s.vomit_count is None and s.stool_count is None:
        m = GENERIC_COUNT.search(low)
        if m:
            n = int(max(_num(g) for g in m.groups() if g))
            if re.search(r"ulti|vomit|उल्टी", low):
                s.vomit_count = n
            elif re.search(r"dast|loose|potty|motion|दस्त", low):
                s.stool_count = n
    for rx in URINE_ABSENT:
        m = rx.search(low)
        if m:
            s.urine_absent_hours = _num(next(g for g in m.groups() if g))
            break
    blood_cl = [c for c in keep if BLOOD_WORD.search(c) and not re.search(r"(kh[oo]+n|खून)\s*(ki|की)\s*(kami|कमी|jaa?n?ch|जाँच|जांच|test)|blood\s+(test|report)", c, re.I)]
    if blood_cl:
        j = " ".join(blood_cl)
        s.blood_amount = "large" if BLOOD_LARGE.search(j) else ("small" if BLOOD_SMALL.search(j) else None)
    s.pregnant = bool(PREG.search(raw))
    for rx, mult in ((PREG_M, 4.33), (PREG_W, 1.0), (PREG_LEAD, 4.33)):
        m = rx.search(raw.lower())
        if m:
            s.pregnancy_weeks = round(_num(next(g for g in m.groups() if g)) * mult, 1)
            s.pregnant = True
            break
    s.comorbidities = [k for k, rx in COMORB.items() if rx.search(raw)]
    s.hypertension = bool(HTN.search(raw))
    s.smoker = bool(SMOKER.search(raw))
    s.bedridden = bool(BEDRIDDEN.search(raw))
    ctx_text = " . ".join(context)
    s.named_diseases = [k for k, rx in NAMED_C.items() if rx.search(now_text)]
    s.context_diseases = [k for k, rx in NAMED_C.items() if rx.search(ctx_text)]
    s.correction = bool(CORRECTION.search(raw))
    return s
