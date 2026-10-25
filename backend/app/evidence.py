"""Evidence spans: the exact words in the user's own text that show a health problem.

A clinical follow-up may be asked only when at least one span exists in the current or an earlier user turn.
A person mention alone ("abba", "papa", "mummy", "patient") is never health evidence. Offsets are character
positions in the cleaned user text (Unicode NFC, runs of whitespace collapsed), which is what the user typed for
ordinary input. Anything the pipeline extracts without a span here is dropped (see `supported`).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .lang import _DEVA_RULES, _LATIN_COMPILED, clean

# canonical words from the language rules that are people or time, not complaints
NOT_HEALTH = {"father", "mother", "grandmother", "grandfather", "infant", "child", "not", "days", "week", "months", "years"}
# care / complaint words beyond the symptom slots (EN, Hinglish, Devanagari); people and statuses are left out
COMPLAINT = re.compile(
    r"\b(sick|ill|unwell|not\s+well|not\s+feeling\s+well|symptom|doctor|dr\.?|nurse|paramedic|caregiver|hospital|clinic|"
    r"ambulance|check[- ]?up|blood\s+test|vitals?|bp|sugar|diabet|pregnan|injection|dressing|wound|surgery|operation|"
    r"treatment|therapy|physio|bedridden|hurt|hurting|ache|aching|sore|bleed|fell|fall|injur|accident|crying|not\s+eating|"
    r"not\s+sleeping|tired|weak|faint|vomit|fever|cough|cold|pain|breath|dizzy|rash|itch|swell|phlegm|asthma|wheez|inhaler|"
    r"stool|constipat|acne|pimple|period|urin|burn|poison|seizure|fit|stroke|lump|numb|tremor|shaking|thirst|platelet|"
    r"oxygen|spo2|pulse|temperature|"
    r"suicid|kill\s+myself|end(ing)?\s+my\s+life|don'?t\s+want\s+to\s+live|"
    r"tabiyat|tabiyet|tabeeyat|bimar|beemar|bimaar|takleef|taklif|dard|bukhar|khansi|zukaam|ulti|dast|chakkar|kamzori|chot|"
    r"ghaav|khoon|sujan|soojan|khujli|jalan|peshab|latrine|pet\s+kharab|thik\s+nahi|theek\s+nahi|thik\s+nhi|theek\s+nhi|ilaaj|"
    r"ilaj|dekhbhal|daktar|davakhana|aspatal|haspatal|garbh|pregnent|ro\s+raha|ro\s+rahi|khana\s+nahi|neend\s+nahi|gir\s+gay|"
    r"gir\s+gai|behosh|hosh|saans|sans|sar\s+dard|sir\s+dard|kamar|ghutn|kabz|muhas|mahwari|balgam|seeti\s+jaisi|potty|"
    r"chhale|lakwa|daura|kaanp|sunn|gaanth|pyaas|zeher|zahar|tezaab|jhatka|sust|pehchaan\s+nahi|doodh\s+(pina|peena)\s+band|"
    r"jeena\s+nahi|khud\s+ko\s+khatam|cut|patti|concentrat|dhyaan|irritab|chidchid|forget|bhool|gets\s+lost|light-?headed|"
    r"racing|dhadkan|palpitat|watery|beh\s+rah|chehr|ghutn)\w*"
    # body parts (whole words): a problem located on the body is a complaint; a body part is not a person mention
    r"|\b(aankh|eyes?|kaan|ears?|naak|nose|gala|throat|daant|tooth|teeth|skin|chamdi|nails?|stomach|tummy|belly|"
    r"head|face|mouth|muh|munh|lips?|hont|tongue|haath|hands?|arms?|pair|legs?|foot|feet|chest|seen[ae]|heart|dil|"
    r"knees?|joints?|sar\s+garam)\b"
    r"|तबीयत|बीमार|तकलीफ|दर्द|बुखार|खांसी|खाँसी|जुकाम|उल्टी|दस्त|चक्कर|कमज़ोरी|कमजोरी|चोट|घाव|खून|सूजन|खुजली|जलन|पेशाब|इलाज|"
    r"देखभाल|डॉक्टर|नर्स|अस्पताल|गर्भ|साँस|सांस|बेहोश|होश|ठीक नहीं|सिर|पेट|घुटन|कमर|इंजेक्शन|ड्रेसिंग|कब्ज|बलगम|दमा|इनहेलर|सीटी|"
    r"पॉटी|सुस्त|पहचान नहीं|लकवा|दौरा|ज़हर|जहर|काँप|कांप|सुन्न|गांठ|प्यास|छाले|पीरियड|त्वचा|आँख|आंख|दिल|सीने|सीना|"
    r"कट|पट्टी|ध्यान|चिड़चिड़|मुहांसे|कान|नाक|गला|दाँत|दांत|हाथ|पैर|पीठ|चेहरा|चेहरे|मुँह|मुंह|होंठ|जीभ|शरीर|बदन|हड्डी|टूट|भूल",
    re.I)


@dataclass(frozen=True)
class Span:
    kind: str   # symptom | complaint | sign | red_flag | lexicon
    label: str  # symptom id, canonical term, red-flag id, or "complaint"
    text: str   # the user's own words
    start: int
    end: int
    turn: int   # index of the user turn

    def as_dict(self) -> dict:
        return asdict(self)


def _symptom_patterns():
    from .intake import _SYM_C  # local import: intake imports nothing from here
    return _SYM_C


def _sign_patterns():
    from .pathways.engine import _compiled_signs
    return _compiled_signs()


def _labels(canon: str) -> list[str]:
    """A canonical term and the intake symptom ids it stands for ("cannot breathe" -> breathlessness)."""
    return [canon] + [n for n, rx in _symptom_patterns() if n != canon and rx.search(canon)]


def find(user_texts: list[str]) -> list[Span]:
    """All evidence spans in the user turns, in text order, one per (turn, start, end, label)."""
    from . import safety
    out: dict[tuple[int, int, int, str], Span] = {}

    def add(kind: str, label: str, turn: int, s: str, a: int, b: int) -> None:
        if b > a and (turn, a, b, label) not in out:
            out[(turn, a, b, label)] = Span(kind, label, s[a:b], a, b, turn)

    for i, raw in enumerate(user_texts):
        s = clean(raw)
        low = s.lower()
        for name, rx in _symptom_patterns():
            for m in rx.finditer(low):
                add("symptom", name, i, s, m.start(), m.end())
        for rx, canon in _LATIN_COMPILED:
            if canon in NOT_HEALTH:
                continue
            for m in rx.finditer(low):
                for lab in _labels(canon):
                    add("symptom", lab, i, s, m.start(), m.end())
        for word, canon in _DEVA_RULES:
            if canon in NOT_HEALTH:
                continue
            j = low.find(word)
            while j >= 0:
                for lab in _labels(canon):
                    add("symptom", lab, i, s, j, j + len(word))
                j = low.find(word, j + 1)
        for m in COMPLAINT.finditer(s):
            add("complaint", "complaint", i, s, m.start(), m.end())
        for sid, pats in _sign_patterns().items():  # clinical pathway signs (config/pathways), affirmed or denied
            for p in pats:
                for m in p.finditer(low):
                    add("sign", sid, i, s, m.start(), m.end())
        # broad medical lexicon (config/medical_lexicon.json, disease aliases), typos included: "aakh pili", "cnacer"
        from . import lexicon
        for h in lexicon.evidence_hits(s):
            add("lexicon", f"{h.kind}:{h.canonical}", i, s, h.start, h.end)
        res = safety.check([s])
        for flag, ev in res.evidence.items():
            first = str(ev).split(" | ")[0].strip()
            j = low.find(first.lower()) if first else -1
            if j >= 0:
                add("red_flag", flag, i, s, j, j + len(first))
            else:  # matched on the normalised text: point at the whole turn rather than invent a narrower span
                add("red_flag", flag, i, s, 0, len(s))
    return sorted(out.values(), key=lambda x: (x.turn, x.start, -x.end))


def has_evidence(user_texts: list[str]) -> bool:
    return bool(find(user_texts))


def supported(value: str, user_texts: list[str]) -> bool:
    """True when a value (a number, a word) literally appears in the user's text: used to drop unsupported values."""
    v = str(value).strip().lower()
    return bool(v) and any(v in clean(t).lower() for t in user_texts)


# ---------------------------------------------------------------- values and signs (clinical pathways)
def _span_dict(kind: str, label: str, turn: int, s: str, a: int, b: int) -> dict:
    return {"kind": kind, "label": label, "text": s[a:b], "start": a, "end": b, "turn": turn}


def _value_rules():
    from .pathways import slots as S
    return {
        "temp_f": (lambda t: S.parse_temperature(t)[0], [S.TEMP]),
        "platelets": (S.parse_platelets, [S.PLT, S.PLT_REV]),
        "bp_sys": (lambda t: S.parse_bp(t)[0], [S.BP]),
        "bp_dia": (lambda t: S.parse_bp(t)[1], [S.BP]),
        "duration_days": (S.parse_duration, [rx for rx, _ in S.DURATION_RULES]),
        "age_years": (lambda t: S.parse_age(t)[0], [S.AGE_MONTHS, S.AGE_WEEKS, *S.AGE_YEARS, S.INFANT_W]),
        "vomit_count": (lambda t: S._count(S.COUNT_V, t.lower()), S.COUNT_V + [S.GENERIC_COUNT]),
        "stool_count": (lambda t: S._count(S.COUNT_S, t.lower()), S.COUNT_S + [S.GENERIC_COUNT]),
        "urine_absent_hours": (None, S.URINE_ABSENT),
        "pregnancy_weeks": (None, [S.PREG_M, S.PREG_W, S.PREG_LEAD]),
    }


def _turn_texts(user_texts: list[str]) -> list[str]:
    from .pathways.slots import DEVA_DIGITS
    return [clean(t).translate(DEVA_DIGITS) for t in user_texts]  # digit translation keeps every offset


def value_spans(slots, user_texts: list[str]) -> dict[str, dict]:
    """Where each numeric slot came from. A turn that reproduces the value on its own is preferred."""
    out: dict[str, dict] = {}
    turns = _turn_texts(user_texts)
    for attr, (parser, rxs) in _value_rules().items():
        v = getattr(slots, attr, None)
        if v is None:
            continue
        order = [i for i, t in enumerate(turns) if parser and parser(t) == v] + list(range(len(turns)))
        for i in dict.fromkeys(order):
            low = turns[i].lower()
            m = next((m for rx in rxs for m in [rx.search(low)] if m), None)
            if m:
                out[attr] = _span_dict("value", attr, i, clean(user_texts[i]), m.start(), m.end())
                break
    return out


def enforce_value_spans(slots, user_texts: list[str]) -> dict[str, dict]:
    """Drop every numeric value without a span in the user's words (no number is ever estimated)."""
    spans = value_spans(slots, user_texts)
    for attr in _value_rules():
        if getattr(slots, attr, None) is not None and attr not in spans:
            setattr(slots, attr, None)
    return spans


def sign_spans(signs: dict, answers, user_texts: list[str]) -> dict[str, dict]:
    """Span for each affirmed sign: the words that matched its pattern, else the chip the user tapped."""
    from .pathways.engine import _compiled_signs, question_index
    out: dict[str, dict] = {}
    turns = [clean(t) for t in user_texts]
    pats = _compiled_signs()
    for sid, val in signs.items():
        if val is not True:
            continue
        for i, s in enumerate(turns):
            m = next((m for p in pats.get(sid, []) for m in [p.search(s.lower())] if m), None)
            if m:
                out[sid] = _span_dict("sign", sid, i, s, m.start(), m.end())
                break
    by_id = {q["id"]: q for _, q in question_index().values()}
    for qid, chip_ids in (getattr(answers, "chips", None) or {}).items():
        q = by_id.get(qid)
        for c in (q or {}).get("chips", []):
            if c["id"] not in chip_ids:
                continue
            labels = [lab for lab in c["label"].values() if lab]
            for k, v in c.get("facts", {}).items():
                if v is not True or k in out:
                    continue
                for i, s in enumerate(turns):
                    j = next((s.lower().find(lab.lower()) for lab in labels if lab.lower() in s.lower()), -1)
                    if j >= 0:
                        lab = next(lab for lab in labels if lab.lower() in s.lower())
                        out[k] = _span_dict("chip", k, i, s, j, j + len(lab))
                        break
                else:  # chosen earlier and echoed back in assessment_state: the user's own earlier answer
                    out.setdefault(k, {"kind": "earlier_answer", "label": k, "text": c["label"].get("en", ""),
                                       "start": None, "end": None, "turn": None})
    return out
