"""Language detection (en / hi / hinglish) and symptom-term normalisation to canonical English."""
from __future__ import annotations

import re
import unicodedata

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_WORD = re.compile(r"[a-z']+")

# Latin-script tokens that only make sense in romanised Hindi. Ambiguous English words
# ("do", "to", "me", "the", "main") are deliberately left out.
HINGLISH_TOKENS = {
    "hai", "hain", "h", "ko", "se", "mein", "mai", "nahi", "nhi", "nahin", "kya", "aur", "bhi", "raha", "rahi",
    "rahe", "rha", "rhi", "ho", "gaya", "gayi", "gaye", "gya", "gyi", "ke", "ki", "ka", "dard", "bukhar", "bukhaar",
    "bukar", "khansi", "khaansi", "khasi", "saans", "sans", "chakkar", "ulti", "dast", "mujhe", "mera", "meri",
    "mere", "unko", "usko", "inko", "hum", "humein", "kal", "din", "dino", "hafte", "mahine", "saal", "abhi",
    "bahut", "bohot", "bht", "thoda", "thodi", "zyada", "jyada", "tez", "tej", "halka", "halki", "kamzori",
    "kamjori", "pet", "sar", "sir", "seene", "sine", "chhati", "gala", "gale", "pair", "haath", "ghutne", "kamar",
    "beta", "bete", "beti", "bachcha", "bachche", "bacche", "dadi", "dada", "nani", "nana", "papa", "mummy",
    "pitaji", "mataji", "ji", "wale", "wala", "wali", "lag", "laga", "lagi", "pa", "rahein", "karein", "karna",
    "chahiye", "kaise", "kyun", "jab", "phir", "lekin", "par", "sath", "saath", "behosh", "khoon", "khun",
    "jukam", "zukaam", "zukam", "sardi", "neend", "dawai", "dawa", "haan", "nahin", "ab", "tak", "wo", "woh",
    "unhe", "unhein", "hua", "hui", "hue", "tha", "thi", "baje", "subah", "shaam", "raat",
    "kaunsi", "konsi", "kaun", "lun", "loon", "batao", "bataiye", "batayein", "kaisa", "kaisi", "kaise", "aaj", "tum",
    "aap", "mausam", "dawai", "bimari", "bimaari", "haal", "aajkal", "sunao", "chahiye",
}
STRONG_EXTRA = {"kaunsi", "konsi", "kaise", "kaisa", "kaisi", "batao", "bimari", "mausam", "aajkal", "sunao"}
# a single generic token (e.g. "ho", "se") is weak evidence; symptom words are strong
STRONG_HINGLISH = {"bukhar", "bukhaar", "khansi", "khaansi", "saans", "chakkar", "ulti", "dast", "behosh",
                   "mujhe", "nahi", "nhi", "hai", "hain", "khoon", "dard", "kamzori", "seene", "zukaam", "jukam",
                   "raha", "rahi", "rahe", "gaya", "gayi", "gaye", "mein", "ko"}


def detect_language(text: str) -> str:
    """'hi' for Devanagari, 'hinglish' for romanised Hindi, otherwise 'en'."""
    if not text:
        return "en"
    if DEVANAGARI.search(text):
        return "hi"
    words = _WORD.findall(text.lower())
    if not words:
        return "en"
    hits = [w for w in words if w in HINGLISH_TOKENS]
    if any(w in STRONG_HINGLISH or w in STRONG_EXTRA for w in hits) or len(hits) >= 2:
        return "hinglish"
    return "en"


def resolve_language(requested: str | None, text: str) -> str:
    if requested and requested != "auto":
        return requested
    return detect_language(text)


# (pattern, canonical English). Applied in order, so put longer phrases first.
_LATIN_RULES: list[tuple[str, str]] = [
    (r"dil ka daura", "heart attack"),
    (r"(tez|tej|bahut|bohot) (bukh?aa?r|bukar)", "high fever"),
    (r"(halka|halki|thoda|thodi) (bukh?aa?r|bukar)", "mild fever"),
    (r"bukh?aa?r|bukar|bhukar|fevar", "fever"),
    (r"kh?aa?n?si|khasi|khaasi", "cough"),
    (r"(saa?ns?|swas|shwas) (bahut )?(phool|ful|fool|phul)\w*", "breathlessness"),
    (r"(saa?ns?|swas|shwas) (nahi|nhi|nahin) (aa|aa rahi|aa rhi|le pa)\w*", "cannot breathe"),
    (r"(saa?ns?|swas|shwas) (lene )?(ki |mein |me |mai )?(dikk?at|takleef|taklif|problem|pareshani|tang)", "breathing difficulty"),
    (r"dam gh[ou]t\w*", "choking"),
    (r"chakk?ar", "dizziness"),
    (r"ul?tee?|ulti|ulty", "vomiting"),
    (r"loose motions?|patle dast|dast|dust lag", "diarrhoea"),
    (r"behoo?sh|behos", "unconscious"),
    (r"(seene|sine|seena|sina|chhati|chati|chest) ?(mein|me|mai|m)? ?(tez )?(dard|dardh)", "chest pain"),
    (r"daura|dora pad", "seizure"),
    (r"mirgi|mirgee", "seizure"),
    (r"kh[oo]+n|khun", "blood"),
    (r"(sar|sir) ?(mein|me)? ?(dard|dardh)|sardard|sirdard", "headache"),
    (r"pet ?(mein|me)? ?(dard|dardh)", "abdominal pain"),
    (r"kamz?j?ori|kamjori|kamzori", "weakness"),
    (r"zukaa?m|jukaa?m|zukam|nazla", "cold"),
    (r"gale ?(mein|me)? ?(dard|kharash|kharas)", "sore throat"),
    (r"khujli", "itching"),
    (r"soo?jan|suj[ae]n|sooj\w*", "swelling"),
    (r"ghaa?v|zakh?m", "wound"),
    (r"chott?", "injury"),
    (r"thakaa?n|thakawat", "fatigue"),
    (r"paseen?a|pasina", "sweating"),
    (r"dard|dardh", "pain"),
    (r"jalan", "burning"),
    (r"papa|pitaji|daddy|pita ji", "father"),
    (r"mumm?y|mumma|mataji|mata ji|maa", "mother"),
    (r"dadi|nani|daadi|naani", "grandmother"),
    (r"dada ?ji|nana ?ji|dada|nana", "grandfather"),
    (r"navjaat|shishu", "infant"),
    (r"bachch?[ae]|bacch[ae]|bachchi|beta|bete|beti", "child"),
    (r"(nahi|nhi|nahin)", "not"),
    (r"din se|dino se|dinon se", "days"),
    (r"hafte|hafta", "week"),
    (r"mahine|mahino|mahinon", "months"),
    (r"saal", "years"),
]
_DEVA_RULES: list[tuple[str, str]] = [
    ("दिल का दौरा", "heart attack"),
    ("तेज़ बुखार", "high fever"), ("तेज बुखार", "high fever"), ("हल्का बुखार", "mild fever"),
    ("बुखार", "fever"), ("खांसी", "cough"), ("खाँसी", "cough"),
    ("साँस फूल", "breathlessness"), ("सांस फूल", "breathlessness"),
    ("साँस नहीं आ", "cannot breathe"), ("सांस नहीं आ", "cannot breathe"),
    ("साँस लेने में दिक्कत", "breathing difficulty"), ("सांस लेने में दिक्कत", "breathing difficulty"),
    ("साँस की दिक्कत", "breathing difficulty"), ("सांस की दिक्कत", "breathing difficulty"),
    ("साँस लेने में तकलीफ", "breathing difficulty"), ("सांस लेने में तकलीफ", "breathing difficulty"),
    ("दम घुट", "choking"),
    ("चक्कर", "dizziness"), ("उल्टी", "vomiting"), ("दस्त", "diarrhoea"), ("बेहोश", "unconscious"),
    ("सीने में दर्द", "chest pain"), ("छाती में दर्द", "chest pain"), ("सीने में तेज़ दर्द", "chest pain"),
    ("दौरा", "seizure"), ("मिर्गी", "seizure"), ("खून", "blood"), ("ख़ून", "blood"),
    ("सिर दर्द", "headache"), ("सिरदर्द", "headache"), ("सिर में दर्द", "headache"),
    ("पेट में दर्द", "abdominal pain"), ("पेट दर्द", "abdominal pain"),
    ("कमज़ोरी", "weakness"), ("कमजोरी", "weakness"), ("जुकाम", "cold"), ("ज़ुकाम", "cold"),
    ("गले में खराश", "sore throat"), ("खुजली", "itching"), ("सूजन", "swelling"), ("घाव", "wound"),
    ("चोट", "injury"), ("थकान", "fatigue"), ("पसीना", "sweating"), ("दर्द", "pain"), ("जलन", "burning"),
    ("पापा", "father"), ("पिताजी", "father"), ("मम्मी", "mother"), ("माँ", "mother"),
    ("दादी", "grandmother"), ("नानी", "grandmother"), ("दादाजी", "grandfather"), ("दादा", "grandfather"),
    ("नानाजी", "grandfather"), ("नाना", "grandfather"), ("नवजात", "infant"), ("शिशु", "infant"),
    ("बच्चे", "child"), ("बच्चा", "child"), ("बेटे", "child"), ("बेटा", "child"), ("बेटी", "child"),
    ("नहीं", "not"), ("दिन से", "days"), ("हफ्ते", "week"), ("हफ़्ते", "week"), ("महीने", "months"),
    ("महीनों", "months"), ("साल", "years"),
]
_LATIN_COMPILED = [(re.compile(rf"\b(?:{p})\b"), c) for p, c in _LATIN_RULES]


def clean(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "")
    t = t.replace("‍", "").replace("‌", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalise(text: str) -> str:
    """Lower-case and map Hindi/Hinglish symptom words to canonical English terms."""
    t = clean(text).lower()
    for old, new in _DEVA_RULES:
        t = t.replace(old, f" {new} ")
    for rx, new in _LATIN_COMPILED:
        t = rx.sub(new, t)
    return re.sub(r"\s+", " ", t).strip()


_SKIP_CANON = {"not", "days", "week", "months", "years", "pain"}


def term_matches(text: str) -> list[dict]:
    """Which user words were mapped to which canonical term, e.g. {"source": "bukhar", "canonical": "fever"}."""
    t = clean(text).lower()
    out: list[dict] = []
    seen: set[str] = set()
    for old, new in _DEVA_RULES:
        if new not in _SKIP_CANON and old in t and new not in seen:
            out.append({"source": old, "canonical": new})
            seen.add(new)
            t = t.replace(old, " ")
    for rx, new in _LATIN_COMPILED:
        if new in _SKIP_CANON or new in seen:
            continue
        m = rx.search(t)
        if m and m.group(0) != new:
            out.append({"source": m.group(0), "canonical": new})
            seen.add(new)
            t = t[:m.start()] + " " + t[m.end():]
    return out
