"""Deterministic red-flag engine (English, Hindi Devanagari, Hinglish).

Safety is scored on emergency recall and under-triage is penalised heavily, so this engine is
deliberately sensitive. It is run on the raw input, the normalised input and every user turn of
the conversation history, and its result is unioned with any red flags from the LLM.
Any red flag => emergency path, no follow-ups, no caregiver matching.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .lang import clean, normalise

EMERGENCY_CARE_TYPE = "emergency_referral"
MOST_URGENT = "immediate"

W = r"(?:\S+\s+)"  # one word + trailing space, for "up to N words between" gaps

# --- simple flags: any pattern match (not negated, not excluded) fires the flag -----------------
SIMPLE: dict[str, list[str]] = {
    "chest_pain": [
        r"chest\s*(pain|pressure|tightness|heaviness|discomfort)", r"(pain|pressure|tightness|heaviness)\s+in\s+(the\s+|my\s+|his\s+|her\s+)?chest",
        r"heart\s*attack", r"(crushing|squeezing)\s+(pain\s+)?(in\s+)?(the\s+)?chest",
        rf"\b(seene|sine|seena|sina|chhati|chati|chest)\s+{W}{{0,3}}(dard|dardh|pain|dabav|dabaav|bhaari|bhari|bharipan|jakdan)",
        r"dil\s+(ka\s+daura|mein\s+dard|me\s+dard)",
        r"(सीने|छाती|सीना)[^।,.!?]{0,20}(दर्द|दबाव|भारीपन|भारी|जकड़न)", r"दिल का दौरा", r"दिल में दर्द",
    ],
    "severe_breathing_difficulty": [
        r"(can'?t|cannot|can not|unable to|not able to|struggling to|hard to|difficult to)\s+breath",
        r"(difficulty|trouble|problem|difficulties)\s+(in\s+|with\s+)?breathing", r"breathing\s+(difficulty|problem|trouble)",
        r"short(ness)?\s+of\s+breath", r"breathless", r"gasping", r"choking", r"not\s+breathing", r"stopped\s+breathing",
        r"breathing\s+(very\s+)?(fast|rapid|heavily|hard)", r"cannot breathe", r"dyspn", r"respiratory\s+distress",
        r"breathing\s+is\s+(very\s+)?(hard|difficult|laboured|labored)",
        rf"\b(saa?ns|sans|saas|swas|shwas|swaas)\s+{W}{{0,3}}(nahi\s+aa|nhi\s+aa|nahin\s+aa|ruk|phool|phul|ful\b|fool|dikk?at|takleef|taklif|problem|tang|band|nahi\s+le|nhi\s+le|atak|ukhad)",
        r"dam\s+gh[ou]t",
        r"(साँस|सांस|सास|श्वास)[^।,.!?]{0,25}(नहीं आ|फूल|रुक|दिक्कत|तकलीफ|परेशानी|नहीं ले|बंद|अटक|उखड़)", r"दम घुट",
    ],
    "blue_lips": [
        r"(lips?|face|nails?|fingers?|tongue)\s+(are\s+|is\s+)?(turning\s+|turned\s+|going\s+|gone\s+)?(blue|bluish|purple)",
        r"blue\s+(lips|face)",
        rf"\b(hont|honth|hoth|hoot|honthon|chehra|nakhun)\s+{W}{{0,2}}(neel|neele|neela|nila|nile|blue)",
        r"(होंठ|होठ|चेहरा|नाखून)[^।,.!?]{0,15}(नीले|नीला|नीली|नील)",
    ],
    "unconscious": [
        r"unconscious", r"unresponsive", r"(not|isn'?t|is\s+not|stopped)\s+(responding|responsive|waking|conscious)",
        r"passed\s+out", r"faint(ed|ing)", r"syncop", r"loc", r"loss\s+of\s+consciousness", r"collapsed", r"lost\s+consciousness", r"(won'?t|can'?t|cannot)\s+wake",
        r"\bbeh?oo?sh", r"\bbehos\b", r"\bhosh\s+(mein\s+|me\s+)?(nahi|nhi|nahin)", r"\bhosh\s+(kho|ud)",
        r"(jawab|response)\s+(nahi|nhi|nahin)\s+de", r"(uth|jaag)\s+(nahi|nhi)\s+rah",
        r"बेहोश", r"(?<!बे)होश\s*(में)?\s*नहीं", r"(?<!बे)होश खो", r"जवाब नहीं दे",
    ],
    "seizure": [
        r"seizure", r"convuls", r"\bfits?\b", r"epilep", r"jerking", r"\bdaura\b(?!\s+(par|pe))", r"\bdora\s+pad",
        r"mirgi", r"jhatk[ae]", r"दौरा", r"मिर्गी", r"झटके",
    ],
    "stroke_signs": [
        r"slurr", r"dysarthria|hemipar|hemipleg|facial\s+palsy",r"(face|mouth)\s+(is\s+)?(droop|drooping|tilted|twisted|crooked|deviated)", r"droop",
        r"(one|left|right)\s+side\s+(of\s+(the\s+|his\s+|her\s+)?(body|face)\s+)?(is\s+)?(weak|numb|paraly|not\s+moving)",
        r"weakness\s+(on|in)\s+one\s+side", r"(lt|rt|left|right)\.?\s+side\s+(\S+\s+)?weak", r"paraly", r"\bstroke\b", r"sudden\w*\s+(loss\s+of\s+)?(vision|speech)",
        r"can'?t\s+(speak|talk)\s+properly",
        rf"\b(awaaz|awaz|aawaz|aawaaz|zuban|zubaan|jubaan|juban|bolne|boli|bol)\s+{W}{{0,3}}(ladkh?ad|lad\s*khad|atak|saaf\s+nahi|nahi\s+nikal)",
        rf"\b(chehra|chehre|muh|munh|mooh|muhn)\s+{W}{{0,3}}(tedh|terh|tirch|latak|tedha)",
        rf"\b(ek\s+taraf|ek\s+side|aadha|aadhe|adha|adhe|left\s+side|right\s+side)\s+{W}{{0,2}}(kamz?j?or|sunn|lakwa|kaam\s+nahi|hil\s+nahi|chal\s+nahi)",
        r"lakwa|lakva|laqwa", r"\bstroke\b",
        r"(आवाज़|आवाज|ज़ुबान|जुबान|बोली|बोलने)[^।,.!?]{0,15}(लड़खड़|लडखड|अटक|साफ नहीं)",
        r"(चेहरा|चेहरे|मुँह|मुंह)[^।,.!?]{0,20}(टेढ़|टेढा|टेड़|लटक)", r"लकवा",
        r"(एक तरफ|आधे शरीर|आधा शरीर)[^।,.!?]{0,15}(कमज़ोर|कमजोर|सुन्न|काम नहीं)",
    ],
    "heavy_bleeding": [
        r"(heavy|heavily|lots?\s+of|severe|profuse|uncontrolled|non[- ]?stop|massive|a\s+lot\s+of)\s+(bleeding|blood)",
        r"bleeding\s+(heavily|a\s+lot|profusely|badly|won'?t\s+stop|not\s+stopping|non[- ]?stop|nonstop|continuously)",
        r"blood\s+(won'?t|will\s+not|is\s+not|isn'?t)\s+stop",
        r"vomit\w*\s+(of\s+)?blood", r"ha?ematemesis|melena|ha?emoptysis", r"blood\s+in\s+(the\s+)?vomit", r"cough\w*\s+(up\s+)?blood",
        rf"\b(bahut|bohot|bht|zyada|jyada|kaafi|lagatar|bahot)\s+{W}{{0,2}}(kh[oo]+n|khun|blood|bleeding)",
        rf"\b(kh[oo]+n|khun|blood|bleeding)\s+{W}{{0,3}}(ruk\s+nahi|ruk\s+nhi|band\s+nahi|band\s+nhi|rukta\s+nahi)",
        r"(kh[oo]+n|khun)\s+ki\s+ult", r"ult\w*\s+(mein|me)\s+(kh[oo]+n|khun)", r"khansi\s+(mein|me)\s+(kh[oo]+n|khun)",
        r"(बहुत|ज़्यादा|ज्यादा|लगातार|काफी)[^।,.!?]{0,10}(खून|ख़ून|रक्त)", r"(खून|ख़ून)[^।,.!?]{0,15}(रुक नहीं|बंद नहीं)",
        r"खून की उल्टी", r"उल्टी में खून", r"खांसी में खून",
    ],
    "severe_allergic_reaction": [
        r"(face|tongue|lips?)\s+(is\s+|are\s+|has\s+|have\s+)?(\S+\s+)?(swelling|swollen|swelled|puff)",
        r"swelling\s+(of|in|on)\s+(the\s+|his\s+|her\s+|my\s+)?(face|tongue|lips)", r"anaphyla",
        r"throat\s+(is\s+)?(closing|tight\w*)",
        rf"\b(chehra|chehre|jeebh|jibh|hont|honth|hoth)\s+{W}{{0,3}}(sooj|suj|phool\s+gay|sujan|soojan)",
        r"(चेहरा|चेहरे|जीभ|होंठ|होठ)[^।,.!?]{0,15}(सूज|सूजन)",
    ],
    "suicidal_intent": [
        r"suicid", r"kill\s+(my|him|her)sel", r"end\w*\s+(my|his|her)\s+life", r"(don'?t|do\s+not|doesn'?t)\s+want\s+to\s+live",
        r"want\s+to\s+die", r"self[- ]?harm", r"(cut|cutting|hurt|hurting|harm|harming)\s+(my|him|her)sel",
        r"no\s+reason\s+to\s+live", r"better\s+off\s+dead",
        r"(jeena|jina|jeene)\s+(ka\s+mann\s+)?(nahi|nhi|nahin)", r"marna\s+chah", r"mar\s+ja(a)?na\s+chah", r"mar\s+jaunga|mar\s+jaungi",
        r"khudkushi|khudkhushi|aatmhatya|atmahatya|aatmahatya", r"khud\s+ko\s+(khatam|maar|mar|nuksan|nuksaan|hurt|chot)",
        r"jaan\s+de\s+(du|dun|denge|dunga|dungi)",
        r"आत्महत्या|खुदकुशी|ख़ुदकुशी", r"जीना नहीं", r"जीने का मन नहीं", r"मरना चाह", r"खुद को\s*(खत्म|ख़त्म|मार|नुकसान)", r"जान दे",
    ],
    "poisoning_overdose": [
        r"poison", r"overdose", r"intoxicat", r"pesticide|insecticide|rat\s*(poison|kill)",
        r"(swallow|drank|drink|drunk|ate|took|taken|consumed)\w*\s+(\S+\s+){0,3}(bleach|acid|kerosene|phenyl|detergent|pesticide|poison|toilet\s+cleaner)",
        r"(too\s+many|a\s+lot\s+of|whole\s+(bottle|strip)\s+of|all\s+(the|his|her|my))\s+(\S+\s+)?(pills|tablets|medicines?)",
        r"(snake|scorpion)\s*(bite|bit|sting|stung)", r"bitten\s+by\s+a\s+(snake|scorpion)",
        r"zeh[ae]r|jah[ae]r|jeher|zahar", r"(keede|keeda|chuhe|chuha|machhar)\s+maar", r"kerosene|phenyl|tezaab|tezab",
        rf"\b(saari|sari|bahut|zyada|jyada|poori|puri)\s+{W}{{0,1}}(goliyan|goliya|goli|tablets?|dawai|dawa|dawaiyan)\s+{W}{{0,2}}(kha|le|pee|pi|nigal)",
        r"\b(saanp|sanp|saap|bichhu|bichu)\b",
        r"ज़हर|जहर|विष", r"(चूहे|कीड़े|कीडे)[^।,.!?]{0,6}मार", r"(सारी|बहुत|ज़्यादा|ज्यादा|पूरी)[^।,.!?]{0,6}(गोलियाँ|गोलियां|गोली|दवा|दवाई)",
        r"साँप|सांप|बिच्छू", r"तेज़ाब|तेजाब|केरोसिन|फिनाइल",
    ],
    "severe_burns": [
        r"(severe|severely|bad|badly|major|large|serious|deep|extensive)\w*\s+(\S+\s+){0,3}burn",
        r"burn\w*\s+(\S+\s+){0,5}(large|whole|entire|face|body|chest|severe|badly)", r"caught\s+fire", r"on\s+fire",
        r"electric\w*\s+(shock|burn)|electrocut", r"acid\s+(attack|burn)",
        r"\bjal\s+(gaye|gayi|gaya|gae|gyi|gya|gai)", r"jhulas", r"aag\s+(lag|mein|me)", r"(current|karant|bijli)\s+(lag|ka\s+jhatka)",
        r"जल\s*(गए|गई|गया|गये)", r"झुलस", r"आग\s*(लग|में)", r"करंट",
    ],
    "major_trauma": [
        r"(road|car|bike|scooter|truck|bus|motorcycle|two[- ]wheeler)\s+accident", r"accident",
        r"(fell|fallen|fall)\s+(\S+\s+){0,2}(from|off)\s+(\S+\s+){0,2}(roof|terrace|height|building|tree|ladder|balcony)",
        r"(broken|fractured)\s+(\S+\s+)?(bone|leg|arm|hip|neck|back)", r"bone\s+(is\s+)?(sticking|broken|out)", r"fracture",
        r"haddi\s+(toot|tut|tooti|tuti)", r"(chhat|chat|chhath|seedhi|ped)\s+se\s+gir",
        r"एक्सीडेंट|दुर्घटना", r"हड्डी\s*(टूट)", r"(छत|सीढ़ी|पेड़)\s*से\s*गिर",
    ],
    "altered_mental_state": [
        r"\bconfus", r"disorient", r"mental\s+(status\s+)?change", r"altered\s+(mental|sensorium|consciousness)",
        r"not\s+making\s+sense", r"talking\s+nonsense", r"delirious",
        r"(not|isn'?t|can'?t|cannot)\s+recogni[sz]", r"very\s+drowsy", r"responds\s+to\s+(pain|voice)\s+only",
        r"beh?ki\s+beh?ki|bahki\s+bahki|ulti\s+seedhi\s+baat|ajeeb\s+baat", r"pehchaan?\s+(nahi|nhi)", r"\bbhram",
        r"बहकी", r"भ्रम", r"पहचान नहीं", r"उल्टी सीधी बात",
    ],
}

# Clause-level exclusions per flag: if any of these is in the same clause, the flag is not fired.
EXCLUDE: dict[str, list[str]] = {
    "heavy_bleeding": [r"\b(thoda|thodi|little|slight|small|minor|halka|chhota)\b", r"(थोड़ा|थोड़ी|हल्का|छोटा)"],
    "seizure": [r"\bfits?\s+(well|fine|properly|in)\b", r"\bfit\s+(hai|hain|hoon|hu|h|he|ho|rehte|rehti)\b",
                r"dil\s+ka\s+daura", r"fit\s+(and|&)\s+fine"],
    "stroke_signs": [],
    "major_trauma": [r"\b(minor|small|chhota|chhoti|halka)\b\s+(\S+\s+)?accident"],
    "severe_breathing_difficulty": [],
}
CHRONIC = re.compile(r"(months?|years?|mahin|saal|महीन|साल)")
EXERTION = re.compile(r"(stairs|walking\s+fast|exercise|seedh?i|chadhne|daudne|सीढ़ी|चढ़ने)")

# --- combo flags: need a trigger AND a qualifier somewhere in the (whole) text --------------------
FEVER = r"(fever|temperature|bukh?aa?r|bukar|बुखार|ताप)"
COMBOS: dict[str, tuple[list[str], list[str]]] = {
    "fever_stiff_neck_confusion": (
        [FEVER],
        [r"stiff\w*\s+neck|neck\s+(is\s+)?(stiff|rigid)|neck\s+stiff", r"gardan\s+(\S+\s+)?(akad|akd|jakad|jakd|stiff)",
         r"गर्दन[^।,.!?]{0,10}(अकड़|अकड|जकड़)", r"\bconfus", r"beh?ki|bahki", r"बहकी|भ्रम", r"rash\s+that\s+does\s*n.?t\s+fade"],
    ),
    "infant_danger_signs": (
        [r"\b(baby|infant|newborn|new\s*born|navjaat|shishu)\b", r"\b([0-9]|1[0-2]|one|two|three|four|five|six)\s*[- ]?(month|months|mahine|mahina|week|weeks|hafte|din)\s*[- ]?(old|ka|ki|ke)\b",
         r"नवजात|शिशु", r"(एक|दो|तीन|चार|पाँच|पांच|छह|[0-9]+)\s*(महीने|हफ्ते|दिन)\s*(का|की|के)"],
        [r"(high|very\s+high|tez|tej|bahut)\s+(\S+\s+)?(fever|bukh?aa?r|temperature)", r"तेज़?\s*बुखार|बहुत बुखार",
         r"(not|isn'?t|stopped|refus\w*)\s+(feeding|drinking|taking\s+(milk|feeds))", r"(doodh|feed|milk)\s+(\S+\s+)?(nahi|nhi|nahin)",
         r"दूध[^।,.!?]{0,10}नहीं", r"letharg|limp|floppy|\bsust\b|सुस्त", r"not\s+moving|hil\s+nahi|हिल\s*नहीं",
         r"breathing\s+fast|tez\s+saans|तेज़? साँस", r"blue|neela|नीला", r"seizure|fit|daura|दौरा", r"(won'?t|not)\s+wak"],
    ),
    "pregnancy_emergency": (
        [r"pregnan", r"garbh|garbhvati|garbhwati|pet\s+se\s+hai|expecting", r"गर्भ|प्रेग्नेंट|गर्भवती"],
        [r"bleed|blood(?!\s*(test|report|sugar|pressure|sample|group|check|bp))|spotting",
         r"(kh[oo]+n|khun)(?!\s*(ki\s+)?(jaa?n?ch|test|report|sample))",
         r"(खून|ख़ून|रक्त)(?!\s*(की)?\s*(जाँच|जांच|टेस्ट|रिपोर्ट|सैंपल))", r"(severe|tez|tej|bahut|unbearable)\s+(\S+\s+)?(pain|dard)",
         r"(तेज़|तेज|बहुत)\s*दर्द", r"water\s+(broke|break)|paani\s+(gir|nikal|aa)", r"पानी\s*(गिर|निकल)",
         r"seizure|fit|daura|दौरा", r"(baby|bachcha|bachche)\s+(\S+\s+)?(not\s+moving|hil\s+nahi)", r"बच्चा\s*हिल\s*नहीं",
         r"severe\s+headache.*(blur|vision)", r"behosh|बेहोश|faint"],
    ),
    "severe_head_injury": (
        [r"head\s+(injury|trauma)|hit\s+(\S+\s+)?head|head\s+(\S+\s+){0,2}(hit|injur|bang|bump)|(fell|fall|accident)\s+(\S+\s+){0,6}head",
         r"\b(sar|sir|sarr)\s+(\S+\s+){0,2}(chot|chott|lag\s+gay|phat|fat\s+gay|takra)", r"सिर[^।,.!?]{0,12}(चोट|फट|टकरा)"],
        [r"vomit|\bult[ie]|उल्टी", r"confus|beh?ki|bhram|भ्रम|बहकी", r"unconscious|behosh|बेहोश|faint", r"bleed|blood|kh[oo]+n|khun|खून",
         r"seizure|fit|daura|दौरा", r"drows|neend|sleepy|नींद", r"severe|bad|serious|gambhir|गंभीर",
         r"(not|can'?t)\s+(walk|talk|speak)|bol\s+nahi"],
    ),
}

# --- negation ------------------------------------------------------------------------------------
CLAUSE_SPLIT = re.compile(r"[,.;!?।|\n]+|\s(?:but|however|although|lekin|magar|parantu|लेकिन|मगर|परंतु|किंतु)\s", re.I)
PRE_NEG = {"no", "not", "never", "without", "denies", "denied", "deny", "nor", "neither", "dont", "don't", "doesnt",
           "doesn't", "didnt", "didn't", "isnt", "isn't", "hasnt", "hasn't", "havent", "haven't", "negative", "bina",
           "बिना", "koi"}
PRE_BREAK = {"and", "but", "with", "aur", "also", "plus", "now", "then", "और", "अब", "phir", "fir", "since"}
POST_NEG = {"nahi", "nahin", "nhi", "nai", "not", "नहीं", "न", "ना", "mat", "मत"}
POST_FILLER = {"bilkul", "to", "toh", "koi", "hi", "bhi", "ho", "raha", "rahi", "rahe", "rha", "rhi", "hua", "hui", "hue",
               "hota", "hoti", "is", "was", "ki", "ka", "ke", "बिल्कुल", "तो", "कोई", "भी", "ही", "हो", "रहा", "रही", "रहे",
               "हुआ", "हुई", "की", "का", "के", "abhi", "अभी", "at", "all"}


@dataclass
class SafetyResult:
    red_flags: list[str] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)

    @property
    def is_emergency(self) -> bool:
        return bool(self.red_flags)


def _compile(pats: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.I) for p in pats]


_SIMPLE_C = {k: _compile(v) for k, v in SIMPLE.items()}
_EXCL_C = {k: _compile(v) for k, v in EXCLUDE.items()}
_COMBO_C = {k: (_compile(a), _compile(b)) for k, (a, b) in COMBOS.items()}
_TOKEN = re.compile(r"[\wऀ-ॿ']+")


def _tokens(s: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(s)]


def _negated(clause: str, start: int, end: int) -> bool:
    before = _tokens(clause[:start])[-5:]
    for i in range(len(before) - 1, -1, -1):
        w = before[i]
        if w in PRE_BREAK:
            break
        if w in PRE_NEG:
            # "koi" alone is not a negation unless a negation follows the match ("koi dikkat nahi")
            if w != "koi":
                return True
    after = _tokens(clause[end:])[:4]
    for w in after:
        if w in POST_FILLER or w in ("hai", "hain", "h", "he", "है", "हैं", "थी", "था"):
            continue
        return w in POST_NEG
    return False


def clauses(text: str) -> list[str]:
    return [c.strip() for c in CLAUSE_SPLIT.split(text) if c and c.strip()]


def _scan_text(text: str, found: dict[str, str]) -> None:
    for cl in clauses(text):
        for flag, pats in _SIMPLE_C.items():
            if flag in found:
                continue
            if any(x.search(cl) for x in _EXCL_C.get(flag, [])):
                continue
            if flag == "severe_breathing_difficulty" and CHRONIC.search(cl) and EXERTION.search(cl):
                continue
            for p in pats:
                m = p.search(cl)
                while m:
                    if not _negated(cl, m.start(), m.end()):
                        found[flag] = cl
                        break
                    m = p.search(cl, m.end())
                if flag in found:
                    break


def _affirmed(pats: list[re.Pattern], text: str) -> str | None:
    for cl in clauses(text):
        for p in pats:
            for m in p.finditer(cl):
                if not _negated(cl, m.start(), m.end()):
                    return cl
    return None


def _scan_combos(text: str, found: dict[str, str]) -> None:
    for flag, (trig, qual) in _COMBO_C.items():
        if flag in found:
            continue
        t = _affirmed(trig, text)
        if t is None:
            continue
        q = _affirmed(qual, text)
        if q is not None:
            found[flag] = f"{t} | {q}"


def check(user_texts: list[str], extra_flags: list[str] | None = None) -> SafetyResult:
    """Run all rules over each user text (raw + normalised) and over the joined conversation."""
    found: dict[str, str] = {}
    raws = [clean(t) for t in user_texts if t and t.strip()]
    for t in raws:
        _scan_text(t, found)
        _scan_text(normalise(t), found)
    joined = " . ".join(raws)
    _scan_combos(joined, found)
    _scan_combos(normalise(joined), found)
    for f in extra_flags or []:
        if f and f not in found:
            found[f] = "confirmed"
    order = list(SIMPLE) + list(COMBOS)
    flags = sorted(found, key=lambda f: order.index(f) if f in order else len(order))
    return SafetyResult(red_flags=flags, evidence=found)


# --- emergency messaging -------------------------------------------------------------------------
FLAG_LABELS = {
    "chest_pain": ("chest pain or pressure", "सीने में दर्द या दबाव", "seene mein dard ya dabav"),
    "severe_breathing_difficulty": ("difficulty breathing", "साँस लेने में तकलीफ", "saans lene mein takleef"),
    "blue_lips": ("blue lips or face", "होंठ या चेहरा नीला पड़ना", "hont ya chehra neela padna"),
    "unconscious": ("unconscious or not responding", "बेहोशी या जवाब न देना", "behoshi ya jawab na dena"),
    "seizure": ("a seizure / fit", "दौरा पड़ना", "daura padna"),
    "stroke_signs": ("signs of a stroke (face drooping, slurred speech or one-sided weakness)",
                     "लकवे के लक्षण (चेहरा टेढ़ा, बोली लड़खड़ाना या एक तरफ कमज़ोरी)",
                     "lakwe ke lakshan (chehra tedha, awaaz ladkhadana ya ek taraf kamzori)"),
    "heavy_bleeding": ("heavy bleeding", "बहुत ज़्यादा खून बहना", "bahut zyada khoon behna"),
    "severe_allergic_reaction": ("swelling of the face, lips or throat", "चेहरे, होंठ या गले में सूजन", "chehre, hont ya gale mein soojan"),
    "suicidal_intent": ("thoughts of suicide or self-harm", "खुद को नुकसान पहुँचाने के विचार", "khud ko nuksaan pahunchane ke vichaar"),
    "poisoning_overdose": ("possible poisoning or overdose", "ज़हर या दवा की ज़्यादा खुराक", "zeher ya dawa ki zyada khuraak"),
    "severe_burns": ("severe burns", "गंभीर रूप से जलना", "gambhir roop se jalna"),
    "major_trauma": ("a serious injury or accident", "गंभीर चोट या दुर्घटना", "gambhir chot ya accident"),
    "altered_mental_state": ("confusion or unusual behaviour", "भ्रम या असामान्य व्यवहार", "bhram ya ajeeb vyavhaar"),
    "fever_stiff_neck_confusion": ("high fever with stiff neck or confusion", "तेज़ बुखार के साथ गर्दन में अकड़न या भ्रम",
                                   "tez bukhar ke saath gardan akadna ya bhram"),
    "infant_danger_signs": ("danger signs in a young baby", "छोटे बच्चे में खतरे के लक्षण", "chhote bachche mein khatre ke lakshan"),
    "pregnancy_emergency": ("bleeding or severe pain in pregnancy", "गर्भावस्था में खून आना या तेज़ दर्द",
                            "pregnancy mein khoon aana ya tez dard"),
    "severe_head_injury": ("a serious head injury", "सिर में गंभीर चोट", "sar mein gambhir chot"),
}

STEPS = {
    "en": ("Call 112 (emergency) or 108 (ambulance) now. Stay with the person and keep them still and comfortable. "
           "Do not drive yourself if you feel unwell. Do not give food, drink or medicine unless the emergency operator tells you to."),
    "hi": ("अभी 112 (आपातकाल) या 108 (एम्बुलेंस) पर कॉल करें। मरीज़ के साथ रहें और उन्हें आराम से लिटाए रखें। "
           "अगर आपकी तबीयत ठीक नहीं है तो खुद गाड़ी न चलाएँ। जब तक आपातकालीन ऑपरेटर न कहे, खाना, पानी या दवा न दें।"),
    "hinglish": ("Abhi 112 (emergency) ya 108 (ambulance) par call karein. Mareez ke saath rahein aur unhe aaram se litaye rakhein. "
                 "Agar aapki tabiyat theek nahi hai to khud gaadi na chalayein. Jab tak emergency operator na kahe, khana, paani ya dawa na dein."),
}
SUICIDE_EXTRA = {
    "en": " You can also call the Tele-MANAS helpline 14416 (free, 24x7). You are not alone.",
    "hi": " आप टेली-मानस हेल्पलाइन 14416 (मुफ़्त, 24x7) पर भी कॉल कर सकते हैं। आप अकेले नहीं हैं।",
    "hinglish": " Aap Tele-MANAS helpline 14416 (free, 24x7) par bhi call kar sakte hain. Aap akele nahi hain.",
}


def flag_label(flag: str, lang: str) -> str:
    en, hi, hg = FLAG_LABELS.get(flag, (flag.replace("_", " "),) * 3)
    return {"hi": hi, "hinglish": hg}.get(lang, en)


def emergency_reasoning(flags: list[str], lang: str) -> str:
    labels = ", ".join(flag_label(f, lang) for f in flags[:3])
    head = {
        "en": f"Warning sign reported: {labels}. This needs emergency help now. ",
        "hi": f"खतरे का संकेत: {labels}। इसके लिए अभी आपातकालीन मदद चाहिए। ",
        "hinglish": f"Khatre ka sanket: {labels}. Iske liye abhi emergency madad chahiye. ",
    }.get(lang) or ""
    if not head:
        lang = "en"
        head = f"Warning sign reported: {labels}. This needs emergency help now. "
    extra = SUICIDE_EXTRA[lang] if "suicidal_intent" in flags else ""
    return head + STEPS[lang] + extra
