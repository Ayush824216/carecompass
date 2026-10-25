"""Broad medical lexicon: is there any health word in the user's text, even misspelled?

config/medical_lexicon.json (symptom and disease names from the public datasets, CMS ICD-10-CM 3-character categories,
Hindi / Hinglish body parts and abnormal descriptors; built by scripts/build_lexicon.py) and config/disease_aliases.json
(Hindi / Hinglish names of common conditions with a tag). Used only to recognise a health request and to set risk
modifiers: a disease name is never confirmed, denied or repeated back.

Matching: exact words and phrases, then fuzzy matching for Latin-script typos (Damerau / OSA edit distance:
"aakh" -> "aankh", "cnacer" -> "cancer"). Common words never match fuzzily ("kaam" is not "kaan").
A body part with an abnormal descriptor in the same clause ("aankh peeli") is health evidence; either alone is not.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from .config import get_settings
from .lang import clean

LATIN = re.compile(r"[a-z]+(?:'[a-z]+)?")
DEVA = re.compile(r"[ऀ-ॿ]")
# everyday words that must never be read as a typo of a medical word
STOP = set("""a an the and or but for with that this these those have has had from they them what when where your you yours
about would could should there their will which kids kid aid help please need want find look looking like just very much more
most some any all also only even still really maybe okay good bad nice fine well done make made take taken give given call
came come going went gone said says know think time times year years month months week weeks day days today tomorrow night
morning evening home house room work job office school food water milk wala wali wale hai hain hoon hun meri mera mere mujhe
mujhko humko hamko kya kyaa nahi nahin nhi kaam naam jaan gaya gayi gaye kal aaj abhi bahut bohot bahot thoda thodi kuch sab
koi kab kaise kaisa kaisi kyun kyon kahan yahan wahan main mai mein hum tum aap unka unki unke uska uski uske iska iski iske
woh yeh bhi toh tha thi the raha rahi rahe karo karna kiya kari karte karti baat paas pani paani khana ghar log beta beti papa
mummy mamma bhai behen bahan didi dada dadi nana nani bachcha bacha bache bachche din raat subah shaam sham hafte mahine saal
lekin magar agar jab tab phir fir bas sirf ekdum zyada jyada acha accha achha theek thik sahi galat liye diya liya chahiye
sakta sakti sakte dena lena aana jana hona hota hoti hote wapas waise aise kaun kisi kisko usko isko inko unko yaar bro sir
madam bata batao bataiye batana dekho dekhna suno chalo pata maalum lagta lagti lage laga lagi""".split())


@dataclass(frozen=True)
class Hit:
    kind: str        # disease | symptom | body | descriptor
    canonical: str   # condition id, body part, descriptor, or the lexicon term
    tag: str         # emergency_condition | serious_chronic | common | ""
    sensitive: bool
    text: str        # the user's own words
    start: int
    end: int
    fuzzy: bool


@lru_cache
def _load() -> tuple[dict, dict]:
    d = get_settings().config_dir
    lex = json.loads((d / "medical_lexicon.json").read_text(encoding="utf-8"))
    ali = json.loads((d / "disease_aliases.json").read_text(encoding="utf-8"))
    return lex, ali


@lru_cache
def _index():
    """word -> entry; phrase regex -> entry lookup; fuzzy vocabulary bucketed by length."""
    lex, ali = _load()
    words: dict[str, tuple] = {}
    phrases: dict[str, tuple] = {}

    def put(term: str, entry: tuple) -> None:
        t = clean(term).lower().strip()
        if not t or t in STOP:
            return
        (phrases if (" " in t or "-" in t or DEVA.search(t)) else words).setdefault(t, entry)

    for c in ali["conditions"]:  # aliases first: their tag wins over a plain lexicon entry
        for a in c["aliases"]:
            put(a, ("disease", c["id"], c["tag"], bool(c.get("sensitive"))))
    for part, vs in lex["body_parts"].items():
        for v in vs:
            put(v, ("body", part, "", False))
    for desc, vs in lex["descriptors"].items():
        for v in vs:
            put(v, ("descriptor", desc, "", False))
    for t in lex["diseases"] + [c["name"].lower() for c in lex["icd10"]]:
        put(t, ("disease", t, "common", False))
    for t in lex["symptoms"]:
        put(t, ("symptom", t, "", False))
    for t in lex["terms"]:
        put(t, ("disease", t, "common", False))
    # one alternation for all phrases, longest first; Devanagari phrases match as plain substrings
    lat = sorted((p for p in phrases if not DEVA.search(p)), key=len, reverse=True)
    dev = sorted((p for p in phrases if DEVA.search(p)), key=len, reverse=True)
    rx_lat = re.compile(r"\b(?:" + "|".join(re.escape(p) for p in lat) + r")\b") if lat else None
    rx_dev = re.compile("|".join(re.escape(p) for p in dev)) if dev else None
    buckets: dict[int, list[str]] = {}
    for w in sorted(words):
        if LATIN.fullmatch(w) and len(w) >= 4:
            buckets.setdefault(len(w), []).append(w)
    return words, phrases, rx_lat, rx_dev, buckets


def osa(a: str, b: str, cap: int = 3) -> int:
    """Optimal string alignment distance (Levenshtein + adjacent transposition), stops early above `cap`."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev2, prev = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > cap:
            return cap + 1
        prev2, prev = prev, cur
    return prev[-1]


def _max_dist(token: str, kind: str) -> int:
    n = len(token)
    if kind in ("body", "descriptor"):
        return 0 if n < 4 else 1 if n < 6 else 2
    return 0 if n < 5 else 1 if n < 7 else 2


@lru_cache(maxsize=4096)
def fuzzy(token: str) -> str | None:
    """Closest lexicon word for a misspelled Latin-script token, or None."""
    words, _, _, _, buckets = _index()
    if len(token) < 4 or token in STOP or token in words:
        return None
    best, best_d = None, 9
    for n in range(len(token) - 2, len(token) + 3):
        for w in buckets.get(n, ()):
            md = min(_max_dist(token, words[w][0]), _max_dist(w, words[w][0]))
            if md == 0 or abs(n - len(token)) > md:
                continue
            if w[0] != token[0]:
                md = 1  # a different first letter: one edit at most
            d = osa(token, w, md)
            if d <= md and d < best_d:
                best, best_d = w, d
    return best


def hits(text: str) -> list[Hit]:
    """Every lexicon hit in one text (offsets in the cleaned text)."""
    words, phrases, rx_lat, rx_dev, _ = _index()
    s = clean(text)
    low = s.lower()
    out: list[Hit] = []
    taken: list[tuple[int, int]] = []
    for rx in (rx_lat, rx_dev):
        if rx is None:
            continue
        for m in rx.finditer(low):
            e = phrases[m.group(0)]
            out.append(Hit(e[0], e[1], e[2], e[3], s[m.start():m.end()], m.start(), m.end(), False))
            taken.append((m.start(), m.end()))
    for m in LATIN.finditer(low):
        if any(a <= m.start() < b for a, b in taken):
            continue
        tok = m.group(0)
        e = words.get(tok)
        fz = False
        if e is None:
            w = fuzzy(tok)
            if w is None:
                continue
            e, fz = words[w], True
        out.append(Hit(e[0], e[1], e[2], e[3], s[m.start():m.end()], m.start(), m.end(), fz))
    for m in re.finditer(r"[ऀ-ॿ]+", low):  # single Devanagari words (exact)
        if any(a <= m.start() < b for a, b in taken):
            continue
        e = words.get(m.group(0))
        if e:
            out.append(Hit(e[0], e[1], e[2], e[3], s[m.start():m.end()], m.start(), m.end(), False))
    return sorted(out, key=lambda h: h.start)


def canonical_text(text: str) -> str:
    """The text with misspelled words replaced by their lexicon spelling ("aakh pili" -> "aankh pili")."""
    s = clean(text).lower()

    def sub(m: re.Match) -> str:
        w = fuzzy(m.group(0))
        return w or m.group(0)
    return LATIN.sub(sub, s)


def _clauses(text: str) -> list[tuple[int, str]]:
    from .safety import CLAUSE_SPLIT
    out, pos = [], 0
    for part in CLAUSE_SPLIT.split(clean(text)):
        if part is None:
            continue
        j = clean(text).find(part, pos)
        if part.strip():
            out.append((max(j, 0), part))
        pos = max(pos, j + len(part)) if j >= 0 else pos
    return out


def evidence_hits(text: str) -> list[Hit]:
    """Hits that count as health evidence: any disease / symptom word, or a body part + a descriptor in one clause."""
    hs = hits(text)
    ev = [h for h in hs if h.kind in ("disease", "symptom")]
    for start, cl in _clauses(text):
        end = start + len(cl)
        inside = [h for h in hs if start <= h.start < end]
        if any(h.kind == "body" for h in inside) and any(h.kind == "descriptor" for h in inside):
            ev += [h for h in inside if h.kind in ("body", "descriptor")]
    return sorted(set(ev), key=lambda h: h.start)


ACUTE = re.compile(r"\b(abhi|just\s+now|right\s+now|aaj|achanak|suddenly|sudden|maar\s+gaya|maar\s+gayi|pad\s+gaya|pad\s+gayi|"
                   r"padh\s+gaya|pada\s+hai|padi\s+hai|aaya\s+hai|aayi\s+hai|aa\s+gaya|aa\s+gayi|ho\s+gaya|ho\s+gayi|hua\s+hai|"
                   r"hui\s+hai|ho\s+raha|ho\s+rahi|is\s+having|having\s+an?|happening|started|शुरू)\b|अभी|अचानक|पड़\s*गया|आया\s+है|हो\s+गया|हो\s+रहा",
                   re.I)


def facts(clauses: list[str]) -> dict:
    """Pathway facts from the patient's current clauses (negated mentions do not count)."""
    from .safety import _negated, not_current
    f = {"lex_disease": False, "body_complaint": False, "serious_chronic": False, "emergency_condition_now": False,
         "sensitive_condition": False}
    conditions: list[str] = []
    for cl in clauses:
        if not_current(cl, cl):
            continue
        low = clean(cl).lower()
        ev = evidence_hits(cl)
        for h in ev:
            if _negated(low, h.start, h.end):
                continue
            if h.kind == "disease":
                f["lex_disease"] = True
                conditions.append(h.canonical)
                if h.tag == "serious_chronic":
                    f["serious_chronic"] = True
                if h.tag == "emergency_condition" and ACUTE.search(cl):
                    f["emergency_condition_now"] = True
                if h.sensitive:
                    f["sensitive_condition"] = True
            elif h.kind in ("body", "descriptor"):
                f["body_complaint"] = True
    f["lex_conditions"] = sorted(set(conditions))
    return f
