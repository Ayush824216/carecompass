"""Combine pathway results with the ML ensemble (spec section 7) and build user-facing text.

- Final urgency = most urgent of (pathway, ML). Missing slots never lower urgency.
- Care type = the pathway's when its stage was decided by explicit rules, otherwise the ML ensemble's.
- S3 from any pathway = emergency path (no questions, no matching).
- User-facing text names danger signs in plain words. Concern patterns (dengue_like ...) stay internal (debug only),
  and diseases the user named are never confirmed.
"""
from __future__ import annotations

from importlib import import_module
from typing import Optional

from .. import explain, safety
from ..triage import Decision
from . import engine
from .engine import PathwayOutcome

URG = {"routine": 0, "same_day": 1, "immediate": 2}
IDX = {"en": 0, "hi": 1, "hinglish": 2}
S0_RAISE_CONF = 0.75
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
    if merged.care_type == "emergency_referral" or merged.urgency == "immediate":
        merged.care_type, merged.urgency = "emergency_referral", "immediate"
    return merged


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
            ph.append((f"temperature {v:g}°F", f"तापमान {v:g}°F", f"temperature {v:g}°F")[i])
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
            labels.append(m["label"].get(lang) or m["label"]["en"])
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
    mods = [m["label"].get(lang) or m["label"]["en"] for m in common["modifiers"] if m["id"] in prim.modifiers]
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
