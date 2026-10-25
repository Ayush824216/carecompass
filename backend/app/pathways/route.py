"""Combine pathway results with the ML ensemble (spec section 7) and build user-facing text.

- Final urgency = most urgent of (pathway, ML). Missing slots never lower urgency.
- Care type = the pathway's when its stage was decided by explicit rules, otherwise the ML ensemble's.
- S3 from any pathway = emergency path (no questions, no matching).
- User-facing text names danger signs in plain words. Concern patterns (dengue_like ...) stay internal (debug only),
  and diseases the user named are never confirmed.
"""
from __future__ import annotations

import re
from importlib import import_module
from typing import Optional

from .. import explain, safety
from ..triage import Decision
from . import engine, expr
from .engine import PathwayOutcome

URG = {"routine": 0, "same_day": 1, "immediate": 2}
IDX = {"en": 0, "hi": 1, "hinglish": 2}
S0_RAISE_CONF = 0.75
# the model alone may make an emergency only when it is very sure; otherwise (no red flag, no S3 rule) it means
# "do not wait": same day. Emergencies come from the safety rules and the pathway S3 rules (S3 recall stays 100%).
MODEL_EMERGENCY_CONF = 0.75
NOT_MEASURED = ("temperature not measured", "तापमान नहीं नापा गया", "temperature naapa nahi gaya")


def merge(dec: Optional[Decision], out: PathwayOutcome) -> Optional[Decision]:
    prim = out.primary
    if prim is None:
        return dec
    if dec is None:
        dec = Decision(prim.care_type, prim.urgency, "pathway")
    path_urg = out.urgency or prim.urgency
    urgency = max([dec.urgency, path_urg], key=lambda u: URG[u])
    # approved S0 rule: when an explicit S0 rule says "mild" (and no pathway says more), the model may raise
    # urgency only when it is highly confident. Every other case: the more urgent of pathway and model.
    if prim.explicit and prim.stage == "S0" and path_urg == "routine" and URG[dec.urgency] > URG[path_urg] \
            and dec.urgency != "immediate" and dec.probs:
        if dec.probs.get("urgency", {}).get(dec.urgency, 0.0) < S0_RAISE_CONF:
            urgency = path_urg
    care = prim.care_type if prim.explicit else dec.care_type
    merged = Decision(care, urgency, f"pathway:{prim.pathway}+{dec.source}" if prim.explicit else dec.source,
                      dec.confidence, dec.probs, dec.red_flags, dec.llm_reasoning)
    if prim.stage != "S3" and not dec.red_flags and (merged.care_type == "emergency_referral" or merged.urgency == "immediate"):
        # a pathway decided below S3 and no red flag: the model cannot turn it into an emergency
        merged.urgency = "same_day"
        if merged.care_type == "emergency_referral":
            merged.care_type = prim.care_type if prim.care_type != "emergency_referral" else second_care(dec)
        merged.source += "+capped"
        return merged
    if merged.care_type == "emergency_referral" or merged.urgency == "immediate":
        merged.care_type, merged.urgency = "emergency_referral", "immediate"
    return merged


def second_care(dec: Decision) -> str:
    """The model's most likely non-emergency care type (GP teleconsult when unknown)."""
    probs = (dec.probs or {}).get("care_type") or {}
    rest = {k: v for k, v in probs.items() if k != "emergency_referral"}
    return max(rest, key=rest.get) if rest else "gp_teleconsult"


def cap_model_emergency(dec: Optional[Decision], out: Optional[PathwayOutcome]) -> Optional[Decision]:
    """No pathway, no red flag: a model-only emergency below MODEL_EMERGENCY_CONF becomes same day."""
    if dec is None or dec.red_flags or (out is not None and out.primary is not None):
        return dec
    if dec.care_type != "emergency_referral" and dec.urgency != "immediate":
        return dec
    p = (dec.probs or {})
    conf = max(p.get("care_type", {}).get("emergency_referral", 0.0), p.get("urgency", {}).get("immediate", 0.0))
    if not p or conf >= MODEL_EMERGENCY_CONF:
        return dec
    return Decision(second_care(dec) if dec.care_type == "emergency_referral" else dec.care_type, "same_day",
                    f"{dec.source}+capped", dec.confidence, dec.probs, dec.red_flags, dec.llm_reasoning)


def temperature_said(temp_f: float, span: Optional[dict]) -> str:
    """A temperature in the user's own number: "102°F", or "39 C (= 102.2°F)" when it was given in Celsius."""
    said = (span or {}).get("text")
    if not said:
        return f"{temp_f:g}°F"
    m = re.search(r"\d+(?:\.\d+)?", said)
    if m and abs(float(m.group(0)) - temp_f) >= 0.05:
        return f"{said} (= {temp_f:g}°F)"
    return said if re.search(r"°|f|fahrenheit|deg", said, re.I) else f"{said}°F"


def _num(n: float) -> str:
    return f"{int(n):,}" if float(n).is_integer() else f"{n:g}"


def slot_phrases(out: PathwayOutcome, refs: list[str], lang: str) -> list[str]:
    f, i = out.facts, IDX.get(lang, 0)
    ph: list[str] = []
    for r in refs:
        v = f.get(r)
        if v is None:
            continue
        if r == "temp_f" and out.slots.temp_f is not None:
            said = temperature_said(v, out.spans.get("temp_f"))
            ph.append((f"temperature {said}", f"तापमान {said}", f"temperature {said}")[i])
        elif r == "temp_f" and f.get("temp_band"):  # the thermometer band the user picked, never a made-up number
            b = f["temp_band"].replace("-", "–")
            b = b if b[0] in "<" or b.endswith("+") else f"{b}"
            ph.append((f"thermometer {b}°F", f"थर्मामीटर {b}°F", f"thermometer {b}°F")[i])
        elif r == "duration_days":
            if v < 1:
                ph.append(("since today", "आज से", "aaj se")[i])
            elif v >= 14 and v % 7 == 0:
                w = int(v // 7)
                ph.append((f"for {w} weeks", f"{w} हफ्ते से", f"{w} hafte se")[i])
            else:
                d = int(round(v))
                ph.append((f"for {d} days", f"{d} दिन से", f"{d} din se")[i])
        elif r == "platelets":
            ph.append((f"platelets {_num(v)}", f"प्लेटलेट्स {_num(v)}", f"platelets {_num(v)}")[i])
        elif r == "bp_sys" and f.get("bp_dia"):
            ph.append((f"BP {v}/{f['bp_dia']}", f"बीपी {v}/{f['bp_dia']}", f"BP {v}/{f['bp_dia']}")[i])
        elif r == "vomit_count":
            ph.append((f"vomited {v} times", f"{v} बार उल्टी", f"{v} baar ulti")[i])
        elif r == "stool_count":
            ph.append((f"{v} loose motions a day", f"दिन में {v} बार दस्त", f"din mein {v} baar dast")[i])
        elif r == "urine_absent_hours":
            ph.append((f"no urine for {v:g} hours", f"{v:g} घंटे से पेशाब नहीं", f"{v:g} ghante se peshab nahi")[i])
        elif r == "age_years":
            ph.append((f"age {v:g}", f"उम्र {v:g}", f"umar {v:g}")[i])
    return ph


# the user speaks about themselves ("mujhe", "I have"): "aap" wording, never "mareez" / "patient"
SELF = re.compile(r"\b(mujhe|mujhko|meri|mera|mere|main|mai|maine|mujhse|i|i'm|im|i've|ive|my|me|myself)\b|मुझे|मेरी|मेरा|मेरे|मैं", re.I)
OTHER = re.compile(r"\b(papa|pitaji|mummy|mumma|maa|mother|father|dad|mom|beta|beti|bachch?[aeiy]|baby|son|daughter|dadi|dada|"
                   r"nani|nana|bhai|bhaiya|behen|bahan|didi|wife|husband|patni|pati|biwi|sasur|saas|uncle|aunty|chacha|chachi|"
                   r"grand(mother|father|ma|pa)|unhe|unko|inhe|inko|woh|wo|he|she|his|her|him)\b|पापा|मम्मी|माँ|बेटा|बेटी|बच्च|दादी|दादा|"
                   r"नानी|नाना|भाई|बहन|पत्नी|पति|उन्हें|उनको", re.I)


def speaks_about_self(user_texts: list[str]) -> bool:
    text = " ".join(user_texts)
    return bool(SELF.search(text)) and not OTHER.search(text)


# a long-term condition named in a reason: only the one(s) the user said, never a generic list
CONDITION_NAMES = {
    "diabetes": ("sugar (diabetes)", "शुगर (डायबिटीज़)", "sugar"), "heart": ("heart disease", "दिल की बीमारी", "dil ki bimari"),
    "heart_disease": ("heart disease", "दिल की बीमारी", "dil ki bimari"), "kidney": ("kidney disease", "किडनी की बीमारी", "kidney ki bimari"),
    "kidney_failure": ("kidney failure / dialysis", "किडनी फेल / डायलिसिस", "kidney failure / dialysis"),
    "liver": ("liver disease", "लीवर की बीमारी", "liver ki bimari"), "cancer": ("cancer", "कैंसर", "cancer"),
    "steroids": ("long-term steroid use", "लंबे समय से स्टेरॉयड", "lambe samay se steroid"), "hiv": ("HIV", "HIV", "HIV"),
    "transplant": ("a transplant", "ट्रांसप्लांट", "transplant"),
}
CONDITION_MODS = ("comorbid_raise", "serious_chronic_raise")


def _conditions_said(out: PathwayOutcome) -> list[str]:
    ids = list(dict.fromkeys(list(out.slots.comorbidities) + list(out.facts.get("lex_conditions") or [])))
    if out.facts.get("diabetes") and "diabetes" not in ids:
        ids.append("diabetes")
    return [i for i in ids if i in CONDITION_NAMES]


def modifier_label(m: dict, out: PathwayOutcome, lang: str) -> str:
    if m["id"] in CONDITION_MODS:
        i = ("en", "hi", "hinglish").index(lang) if lang in ("en", "hi", "hinglish") else 0
        said = [CONDITION_NAMES[c][i] for c in _conditions_said(out)]
        if said:
            return ", ".join(said)
    return m["label"].get(lang) or m["label"]["en"]


ENTRY_TEXT = {"mood": "Mann / mood", "women": "Mahila swasthya / Periods", "fever": "Bukhar / Fever", "breathing": "Saans ki dikkat"}


def other_concerns(out: PathwayOutcome, lang: str) -> list[dict]:
    """Other complaints in the same conversation (handled after the most urgent one): pathway, signs said, a start text."""
    prim = out.primary
    if prim is None:
        return []
    _, pathways, _ = engine.load()
    seen, res = {prim.pathway}, []
    for r in out.results:
        if r.pathway in seen or r.pathway == "general":
            continue
        seen.add(r.pathway)
        p = pathways[r.pathway]
        trig = [n for n in expr.names_in(p.cfg["trigger"]) if out.facts.get(n) is True and n in engine._compiled_signs()
                and not n.endswith("_entry")]
        labels = [engine.sign_label(n, lang) for n in dict.fromkeys(trig)]
        if not labels:
            continue
        res.append({"pathway": r.pathway, "label": p.label.get(lang) or p.label["en"], "signs": labels,
                    "start": ENTRY_TEXT.get(r.pathway) or (p.label.get("hinglish") or p.label["en"])})
    return res


def acknowledge_others(others: list[dict], lang: str, feminine: bool) -> str:
    if not others:
        return ""
    said = [s for o in others for s in o["signs"]]
    joined = (" aur " if lang == "hinglish" else " और " if lang == "hi" else " and ").join(
        [", ".join(said[:-1]), said[-1]] if len(said) > 1 else said)
    if lang == "hi":
        return f"आपने {joined} भी बताया — क्या आप इस पर भी बात करना चाहेंगी?" if feminine else f"आपने {joined} भी बताया — क्या आप इस पर भी बात करना चाहेंगे?"
    if lang == "hinglish":
        return f"Aapne {joined} bhi bataya — kya aap is par bhi baat karna chahengi?" if feminine else f"Aapne {joined} bhi bataya — kya aap is par bhi baat karna chahenge?"
    return f"You also mentioned {joined}. Would you like to talk about that too?"


def danger_labels(out: PathwayOutcome, lang: str) -> list[str]:
    """Plain-language reasons for the primary result: triggered signs, readings and risk modifiers."""
    prim = out.primary
    if prim is None:
        return []
    common, _, _ = engine.load()
    labels = [engine.sign_label(s, lang) for s in prim.signs]
    labels += slot_phrases(out, prim.slot_refs, lang)
    for mid in prim.modifiers:
        m = next((x for x in common["modifiers"] if x["id"] == mid), None)
        if m:
            labels.append(modifier_label(m, out, lang))
    seen, outl = set(), []
    for lab in labels:
        if lab and lab not in seen:
            seen.add(lab)
            outl.append(lab)
    return outl


def emergency_reasoning(out: PathwayOutcome, lang: str, safety_flags: list[str]) -> str:
    labels = [safety.flag_label(f, lang) for f in safety_flags] + danger_labels(out, lang)
    labels = list(dict.fromkeys(labels))[:4] or [("danger signs", "खतरे के संकेत", "khatre ke sanket")[IDX.get(lang, 0)]]
    lang = lang if lang in IDX else "en"
    head = {"en": "Warning sign reported: {x}. This needs emergency help now. ",
            "hi": "खतरे का संकेत: {x}। इसके लिए अभी आपातकालीन मदद चाहिए। ",
            "hinglish": "Khatre ka sanket: {x}. Iske liye abhi emergency madad chahiye. "}[lang].format(x=", ".join(labels))
    extra = safety.SUICIDE_EXTRA[lang] if "suicidal_intent" in safety_flags else ""
    return head + safety.STEPS[lang] + extra


def reasoning(out: PathwayOutcome, care_type: str, urgency: str, lang: str) -> str:
    prim = out.primary
    lang = lang if lang in IDX else "en"
    i = IDX[lang]
    _, pathways, _ = engine.load()
    complaint = pathways[prim.pathway].label.get(lang, pathways[prim.pathway].label["en"])
    common, _, _ = engine.load()
    signs = [engine.sign_label(s, lang) for s in prim.signs]
    signs = [s for s in dict.fromkeys(signs) if s.lower() != complaint.lower()]
    readings = slot_phrases(out, prim.slot_refs, lang)
    if out.facts.get("fever") and not out.facts.get("temp_measured"):
        readings.append(NOT_MEASURED[i])
    mods = [modifier_label(m, out, lang) for m in common["modifiers"] if m["id"] in prim.modifiers]
    mods = [x for x in mods if not any(o != x and o.startswith(x) for o in mods)]  # "65+ umar" inside "65+ umar (ghar par ...)"
    items = readings + signs[:4] + mods  # "Bukhar: 4 din se, aankhon ke peeche dard, badan dard."
    head = f"{complaint}: {', '.join(items)}" if items else complaint
    care = explain.CARE[care_type][i]
    urg = explain.URG[urgency][i]
    tail = {"en": f"{care} {urg} is suggested.", "hi": f"सुझाव: {care}, {urg}।", "hinglish": f"Sujhav: {care}, {urg}."}[lang]
    notes = []
    mod = import_module(f".{prim.pathway}", __package__)
    for n in prim.notes:
        if n in getattr(mod, "NOTES", {}):
            notes.append(mod.NOTES[n].get(lang) or mod.NOTES[n]["en"])
    end = "।" if lang == "hi" else "."
    return " ".join([f"{head}{end}", tail] + notes)


# neutral red-flag ids for decisions made from readings alone (rule ids stay internal)
SLOT_FLAGS = {"platelets": "low_platelets", "temp_f": "very_high_temperature", "bp_sys": "very_high_bp",
              "bp_dia": "very_high_bp", "urine_absent_hours": "no_urine", "vomit_count": "repeated_vomiting",
              "stool_count": "many_loose_motions", "duration_days": "long_duration", "age_years": "age_risk",
              "pregnancy_weeks": "pregnancy"}
SLOT_FLAG_LABELS = {
    "low_platelets": ("low platelet count", "प्लेटलेट्स कम", "platelets kam"),
    "very_high_temperature": ("very high temperature", "बहुत तेज़ बुखार", "bahut tez bukhar"),
    "very_high_bp": ("very high BP", "बहुत ज़्यादा बीपी", "BP bahut zyada"),
    "no_urine": ("no urine for many hours", "कई घंटों से पेशाब नहीं", "kai ghanton se peshab nahi"),
    "repeated_vomiting": ("repeated vomiting", "बार-बार उल्टी", "baar baar ulti"),
    "many_loose_motions": ("many loose motions", "बहुत दस्त", "bahut dast"),
    "long_duration": ("going on for long", "काफ़ी दिनों से", "kaafi dinon se"),
    "age_risk": ("age-related risk", "उम्र के कारण जोखिम", "umar ki wajah se jokhim"),
    "pregnancy": ("pregnancy", "गर्भावस्था", "pregnancy"),
    "pathway_danger_sign": ("a danger sign", "खतरे का संकेत", "khatre ka sanket"),
}


def flag_labels(flags: list[str], lang: str) -> dict[str, str]:
    """Plain-language labels for pathway red-flag ids (signs, modifiers, reading-based ids), for the UI."""
    common, _, signs = engine.load()
    mods = {m["id"]: m["label"] for m in common["modifiers"]}
    i = IDX.get(lang, 0)
    out = {}
    for f in flags:
        if f in SLOT_FLAG_LABELS:
            out[f] = SLOT_FLAG_LABELS[f][i]
        elif f in mods:
            out[f] = mods[f].get(lang) or mods[f]["en"]
        elif f in signs:
            out[f] = engine.sign_label(f, lang)
    return out


def trace(out: PathwayOutcome, lang: str) -> dict:
    """Debug block only. Concern patterns are internal routing labels, not diagnoses."""
    prim = out.primary
    common, _, _ = engine.load()
    return {
        "triggered": [r.as_dict() for r in out.results],
        "primary": prim.as_dict() if prim else None,
        "stage_label": common["stages"][prim.stage].get(lang, common["stages"][prim.stage]["en"]) if prim else None,
        "moved_by": danger_labels(out, lang) if prim else [],
        "concern_patterns_internal": sorted({p for r in out.results for p in r.patterns}),
        "named_by_user_internal": out.slots.named_diseases,
        "context_internal": out.slots.context_diseases,
        "slots": {k: out.facts.get(k) for k in ("temp_f", "duration_days", "age_years", "platelets", "bp_sys", "bp_dia",
                                                "vomit_count", "stool_count", "urine_absent_hours", "pregnancy_weeks")},
        "risk": {k: out.facts.get(k) for k in ("infant", "child", "elderly", "pregnant", "comorbid", "bedridden")},
        "answered_questions": out.answers.asked,
        "flag_labels": flag_labels([x for r in out.results for x in r.signs + r.modifiers] + list(SLOT_FLAG_LABELS), lang),
    }
