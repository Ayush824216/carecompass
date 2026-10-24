"""Health memory helpers. The memory itself lives ONLY on the user's device (see docs/PRIVACY.md); the server
never stores it. The client may echo a few remembered items in the optional `memory` request field:

    {"age_group": "elderly", "conditions": ["diabetes", "hypertension"], "pregnant": true}

They are never used silently: the pathway asks once "Last time you told us: ... Is this still true?". Only "Yes"
adds them as risk facts, so memory can raise urgency but never lower it.

`candidates()` lists what the user could save after a conversation; sensitive items (HIV/STI, mental health,
sexual health, pregnancy, substance use) are marked so the client never saves them without an explicit tick.
"""
from __future__ import annotations

import re
from typing import Optional

LANGS = ("en", "hi", "hinglish")
CONDITIONS = {
    "diabetes": ({"en": "sugar (diabetes)", "hi": "शुगर", "hinglish": "sugar"}, {"diabetes": True, "comorbid": True}),
    "hypertension": ({"en": "high BP", "hi": "हाई बीपी", "hinglish": "BP"}, {"hypertension": True, "comorbid": True}),
    "heart": ({"en": "a heart problem", "hi": "दिल की बीमारी", "hinglish": "dil ki bimari"}, {"heart": True, "comorbid": True}),
    "kidney": ({"en": "a kidney problem", "hi": "किडनी की बीमारी", "hinglish": "kidney ki bimari"}, {"kidney": True, "comorbid": True}),
    "asthma": ({"en": "asthma", "hi": "दमा", "hinglish": "asthma"}, {"asthma_copd": True}),
}
AGE = {
    "infant": ({"en": "age under 1 year", "hi": "उम्र 1 साल से कम", "hinglish": "umar 1 saal se kam"},
               {"age_known": True, "infant": True, "child": True, "under5": True, "minor": True}),
    "child": ({"en": "age under 18", "hi": "उम्र 18 से कम", "hinglish": "umar 18 se kam"},
              {"age_known": True, "child": True, "minor": True}),
    "adult": ({"en": "age 18–64", "hi": "उम्र 18–64", "hinglish": "umar 18–64"}, {"age_known": True, "adult": True}),
    "elderly": ({"en": "age 65+", "hi": "उम्र 65+", "hinglish": "umar 65+"}, {"age_known": True, "elderly": True}),
}
PREGNANT = ({"en": "pregnancy", "hi": "गर्भावस्था", "hinglish": "pregnancy"}, {"pregnant": True})
TEXT = {"en": "Last time you told us: {x}. Is this still true?",
        "hi": "पिछली बार आपने बताया था: {x}। क्या यह अभी भी सही है?",
        "hinglish": "Pichli baar aapne bataya tha: {x}. Kya yeh abhi bhi sahi hai?"}
YES = {"en": "Yes, still true", "hi": "हाँ, अभी भी", "hinglish": "Haan, abhi bhi"}
NO = {"en": "No, not now", "hi": "नहीं, अब नहीं", "hinglish": "Nahi, ab nahi"}
QID = "memory.confirm"


def _items(memory: Optional[dict]) -> list[tuple[dict, dict]]:
    if not isinstance(memory, dict):
        return []
    out = []
    ag = memory.get("age_group")
    if ag in AGE:
        out.append(AGE[ag])
    for c in memory.get("conditions") or []:
        if c in CONDITIONS:
            out.append(CONDITIONS[c])
    if memory.get("pregnant") is True:
        out.append(PREGNANT)
    return out


def question(memory: Optional[dict]) -> Optional[dict]:
    """The one confirmation question for the remembered items, or None when nothing usable is remembered."""
    items = _items(memory)
    if not items:
        return None
    facts: dict = {}
    for _, f in items:
        facts.update(f)
    text = {l: TEXT[l].format(x=", ".join(lab[l] for lab, _ in items)) for l in LANGS}
    return {"id": QID, "kind": "memory", "text": text, "no_none_chip": False, "none_label": NO,
            "chips": [{"id": "yes", "label": YES, "facts": facts}]}


_HEAD = {l: re.compile("^" + re.escape(TEXT[l].split("{x}")[0].strip().lower())) for l in LANGS}


def is_memory_question(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(rx.search(t) for rx in _HEAD.values())


# ---------------------------------------------------------------- what could be saved after this conversation
SENSITIVE_TEXT = {
    "sexual_health": re.compile(r"\b(sti|std|sexual(ly)?|gupt\s*rog|yaun|private\s+part|genital|gonorr|syphil|herpes)\w*|गुप्त\s*रोग|यौन", re.I),
    "hiv_sti": re.compile(r"\bhiv\b|\baids\b|एचआईवी", re.I),
}
LABEL = {
    "age": {"en": "Age group", "hi": "उम्र", "hinglish": "Umar"},
    "pregnancy": {"en": "Pregnancy", "hi": "गर्भावस्था", "hinglish": "Pregnancy"},
    "mental_health": {"en": "Mood / mental health", "hi": "मन / मानसिक स्वास्थ्य", "hinglish": "Mann / mental health"},
    "substance_use": {"en": "Alcohol or drug use", "hi": "शराब या नशा", "hinglish": "Sharab ya nasha"},
    "sexual_health": {"en": "Sexual health", "hi": "यौन स्वास्थ्य", "hinglish": "Sexual health"},
    "hiv_sti": {"en": "HIV / STI", "hi": "एचआईवी / यौन संक्रमण", "hinglish": "HIV / STI"},
}


def candidates(user_texts: list[str], pout, age_group: Optional[str], lang: str) -> list[dict]:
    """Items the user may save on their device. sensitive=True -> never saved unless the user ticks 'Save this'."""
    lang = lang if lang in LANGS else "en"
    f = pout.facts if pout is not None else {}
    slots = pout.slots if pout is not None else None
    comorb = set(getattr(slots, "comorbidities", []) or [])
    out: list[dict] = []
    if age_group in AGE:
        out.append({"id": "age_group", "kind": "age", "value": age_group, "sensitive": False,
                    "label": AGE[age_group][0][lang][:1].upper() + AGE[age_group][0][lang][1:]})
    present = {"diabetes": f.get("diabetes") or "diabetes" in comorb, "hypertension": f.get("hypertension"),
               "heart": f.get("heart") or "heart" in comorb, "kidney": "kidney" in comorb or f.get("kidney"),
               "asthma": f.get("asthma_copd")}
    for cid, on in present.items():
        if on:
            out.append({"id": cid, "kind": "condition", "value": True, "sensitive": False,
                        "label": CONDITIONS[cid][0][lang]})
    text = " ".join(user_texts)
    sens = {
        "pregnancy": bool(f.get("pregnant")),
        "mental_health": bool(pout is not None and pout.primary is not None and pout.primary.pathway == "mood"),
        "substance_use": bool(f.get("substance_use")),
        "hiv_sti": "hiv" in comorb or bool(SENSITIVE_TEXT["hiv_sti"].search(text)),
        "sexual_health": bool(SENSITIVE_TEXT["sexual_health"].search(text)),
    }
    for sid, on in sens.items():
        if on:
            out.append({"id": sid, "kind": "sensitive", "value": True, "sensitive": True, "label": LABEL[sid][lang]})
    return out


SENSITIVE_CATEGORIES = {"mood"}  # an assessment summary in these categories is itself sensitive
