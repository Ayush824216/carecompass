"""'Your assessment' card and the echoed assessment state (docs/SYMPTOM_CATEGORIES.md, objectives 1-9).

Everything here is explanation built from the pathway outcome; nothing here changes care type or urgency.
Possible causes are educational ("a doctor may consider"), never a diagnosis, and can be switched off with
SHOW_POSSIBLE_CAUSES. Precautions are non-medicine only: the public symptom_precaution.csv is filtered for
anything that names or implies a medicine, and every card ends with "do not take any medicine without asking
a doctor". The card lives only in the optional debug block; the official response fields are unchanged.
"""
from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from typing import Optional

from .config import get_settings
from .pathways import engine
from .pathways import route as proute
from .pathways.engine import PathwayOutcome

IDX = {"en": 0, "hi": 1, "hinglish": 2}
STRENGTH_RANK = {"strong": 2, "moderate": 1, "weak": 0}

# anything that names or implies a medicine, remedy product or treatment is never shown as a precaution
MEDICINE_RX = re.compile(
    r"medic|drug|tablet|pill|capsule|syrup|dose|injection|inhaler|cream|oint|oinment|antibiot|antiboit|asprin|aspirin|"
    r"acetaminophen|paracetamol|ibuprofen|\botc\b|reliver|reliever|calamine|vaccin|iodine|probiotic|cranberry|thistle|"
    r"witch hazel|alovera|aloe|neem|papaya|lemon balm|epsom|detol|dettol|vitamin|acupuncture|therapy|treatment|juice|"
    r"heating pad|massage|ayurved|homeo|herb|kadha|supplement", re.I)

# the CSV precautions that survive the filter and are shown, with translations (anything else is dropped)
CSV_SAFE = {
    "drink plenty of water": ("Drink plenty of water.", "खूब पानी पिएँ।", "Khoob paani piyein."),
    "keep hydrated": ("Keep drinking fluids.", "पानी और तरल लेते रहें।", "Paani aur liquid lete rahein."),
    "try taking small sips of water": ("Take small sips of water.", "घूँट-घूँट पानी पिएँ।", "Ghoont-ghoont paani piyein."),
    "rest": ("Rest.", "आराम करें।", "Aaram karein."),
    "get proper sleep": ("Get enough sleep.", "पूरी नींद लें।", "Poori neend lein."),
    "keep mosquitos out": ("Keep mosquitoes out (net, screens).", "मच्छरों को दूर रखें (मच्छरदानी, जाली)।", "Machharon ko door rakhein (machhardaani, jaali)."),
    "keep mosquitos away": ("Keep mosquitoes out (net, screens).", "मच्छरों को दूर रखें (मच्छरदानी, जाली)।", "Machharon ko door rakhein (machhardaani, jaali)."),
    "cover mouth": ("Cover the mouth when coughing.", "खांसते समय मुँह ढकें।", "Khaanste samay muh dhakein."),
    "wash hands with warm soapy water": ("Wash hands with soap and water.", "साबुन और पानी से हाथ धोएँ।", "Sabun aur paani se haath dhoyein."),
    "avoid fatty spicy food": ("Avoid oily and spicy food.", "तला और मसालेदार खाना न खाएँ।", "Tala aur masaledar khana na khayein."),
    "avoid oily food": ("Avoid oily food.", "तला खाना न खाएँ।", "Tala khana na khayein."),
    "avoid lying down after eating": ("Do not lie down right after eating.", "खाने के तुरंत बाद न लेटें।", "Khaane ke turant baad na letein."),
    "take deep breaths": ("Sit up and take slow, deep breaths.", "सीधे बैठकर धीरे-धीरे गहरी साँस लें।", "Seedhe baithkar dheere-dheere gehri saans lein."),
    "get away from trigger": ("Move away from smoke, dust or whatever set it off.", "धुएँ, धूल या जिससे तकलीफ हुई उससे दूर हटें।", "Dhuein, dhool ya jisse takleef hui usse door hatein."),
    "switch to loose cloothing": ("Loosen tight clothes.", "टाइट कपड़े ढीले करें।", "Tight kapde dheele karein."),
    "keep calm": ("Stay calm and keep someone with you.", "शांत रहें और किसी को साथ रखें।", "Shaant rahein aur kisi ko saath rakhein."),
    "lie down": ("Lie down when dizzy.", "चक्कर आए तो लेट जाएँ।", "Chakkar aaye to let jaayein."),
    "avoid sudden change in body": ("Change position slowly.", "धीरे-धीरे करवट या स्थिति बदलें।", "Dheere-dheere position badlein."),
    "avoid abrupt head movment": ("Avoid sudden head movements.", "सिर को अचानक न घुमाएँ।", "Sir ko achanak na ghumayein."),
    "reduce stress": ("Reduce stress where you can.", "जहाँ हो सके तनाव कम करें।", "Jahan ho sake tanaav kam karein."),
    "ease back into eating": ("Go back to normal food slowly.", "धीरे-धीरे सामान्य खाना शुरू करें।", "Dheere-dheere normal khana shuru karein."),
    "avoid cold food": ("Avoid cold food and drinks.", "ठंडी चीज़ें न लें।", "Thandi cheezein na lein."),
}

DERIVED = ("long_fever", "long_cough", "low_platelets", "high_temp", "short_illness", "older")

TEXT = {
    "title": ("Your assessment", "आपका आकलन", "Aapka assessment"),
    "symptoms": ("Symptoms checked", "जाँचे गए लक्षण", "Jaanche gaye lakshan"),
    "why": ("Why this urgency", "यह जल्दी क्यों", "Yeh urgency kyun"),
    "causes": ("Possible causes a doctor may consider (not a diagnosis)", "डॉक्टर जिन संभावित कारणों पर विचार कर सकते हैं (निदान नहीं)",
               "Sambhavit kaaran jin par doctor vichaar kar sakte hain (diagnosis nahi)"),
    "tests": ("Tests a doctor may advise", "डॉक्टर ये जाँच बता सकते हैं", "Doctor ye jaanch bata sakte hain"),
    "tests_lead": ("Your doctor may ask for:", "आपके डॉक्टर ये जाँच कह सकते हैं:", "Aapke doctor ye jaanch keh sakte hain:"),
    "precautions": ("Until you see the caregiver", "देखभालकर्ता के आने तक", "Caregiver ke aane tak"),
    "call112": ("Call 112 immediately if", "तुरंत 112 पर कॉल करें अगर", "Turant 112 par call karein agar"),
    "next": ("Next step", "अगला कदम", "Agla kadam"),
    "temperature": ("Temperature", "तापमान", "Temperature"),
    "not_measured": ("not measured", "नहीं नापा", "naapa nahi"),
    "contradiction": ("You said both that there is and is not: {x}. We used the more serious answer.",
                      "आपने होने और न होने, दोनों बातें कहीं: {x}। हमने ज़्यादा गंभीर जवाब माना।",
                      "Aapne hone aur na hone, dono baatein kahin: {x}. Humne zyada gambhir jawab maana."),
    "hospitals": ("Because of the warning signs, the nearest hospitals are shown too.",
                  "चेतावनी के संकेतों की वजह से पास के अस्पताल भी दिखाए गए हैं।",
                  "Chetawani ke sanketon ki wajah se paas ke hospital bhi dikhaye gaye hain."),
}


@lru_cache
def load_cfg() -> dict:
    return json.loads((get_settings().config_dir / "assessment.json").read_text(encoding="utf-8"))


def _t(d: dict, lang: str) -> str:
    return d.get(lang) or d.get("en") or ""


def is_medicine(text: str) -> bool:
    return bool(MEDICINE_RX.search(text or ""))


@lru_cache
def csv_precautions() -> dict[str, list[str]]:
    """Disease -> non-medicine precautions from the public symptom_precaution.csv (if present locally)."""
    p = get_settings().public_dir / "symptom_severity" / "symptom_precaution.csv"
    out: dict[str, list[str]] = {}
    if not p.exists():
        return out
    with open(p, encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or row[0] == "Disease":
                continue
            keep = [x.strip().lower() for x in row[1:] if x.strip() and not is_medicine(x)]
            out[row[0].strip()] = [x for x in keep if x in CSV_SAFE]
    return out


def category_for(pathway: str, facts: dict) -> str:
    cats = load_cfg()["categories"]
    if pathway in cats:
        return pathway
    alias = load_cfg().get("aliases", {}).get(pathway, [])
    if pathway == "stomach" and alias:
        return "vomiting" if facts.get("vomiting") or facts.get("diarrhoea") or facts.get("vomit_count") or facts.get("stool_count") else "abdominal"
    return alias[0] if alias else pathway


def _derived(facts: dict) -> dict:
    d = dict(facts)
    dur, temp = facts.get("duration_days"), facts.get("temp_f")
    d["long_fever"] = bool(facts.get("fever") and dur is not None and dur > 7)
    d["long_cough"] = bool(dur is not None and dur >= 14 and (facts.get("cough") or facts.get("dry_cough") or facts.get("wet_cough")))
    d["low_platelets"] = facts.get("platelets") is not None and facts["platelets"] < 100000
    d["high_temp"] = bool((temp is not None and temp >= 102) or facts.get("fever_reported_high"))
    d["short_illness"] = dur is not None and dur <= 3
    d["older"] = facts.get("age_years") is not None and facts["age_years"] >= 50
    return d


def _label(name: str, lang: str) -> str:
    dl = load_cfg().get("derived_labels", {})
    if name in dl:
        return _t(dl[name], lang)
    return engine.sign_label(name, lang)


def possible_causes(cat: str, facts: dict, lang: str, n_max: int = 3) -> list[dict]:
    """Top 2-3 causes by how many of their supporting findings are present. Never fewer than 2, never one verdict."""
    spec = load_cfg()["categories"].get(cat)
    if not spec:
        return []
    fx = _derived(facts)
    fn = engine._funcs(fx, set(), set())
    scored = []
    for i, c in enumerate(spec["causes"]):
        if c.get("only_if") and not engine.expr.evaluate(c["only_if"], fx, fn):
            continue
        sup = c["supports"]
        matched = [s for s in sup if fx.get(s) is True]
        score = len(matched) / len(sup) if sup else 0.0
        strength = "strong" if len(matched) >= 2 and score >= 0.4 else "moderate" if matched else "weak"
        scored.append((STRENGTH_RANK[strength], len(matched), score, -i, c, strength, matched))
    scored.sort(key=lambda x: x[:4], reverse=True)
    top = [x for x in scored if x[0] > 0][:n_max]
    for x in scored:  # always at least two options, never a single verdict
        if len(top) >= 2:
            break
        if x not in top:
            top.append(x)
    return [{"id": c["id"], "label": _t(c["label"], lang), "strength": strength,
             "matched": [_label(s, lang) for s in matched],
             "missing": [_label(s, lang) for s in c["supports"] if s not in matched][:3],
             "tests": c.get("tests", []), "csv": c.get("csv", [])}
            for *_, c, strength, matched in top]


def symptoms_checked(out: PathwayOutcome, lang: str, limit: int = 12) -> list[dict]:
    """✓ present / ✗ absent / ? not asked, from the primary pathway's questions and the signs found."""
    prim = out.primary
    _, pathways, signs = engine.load()
    order: list[str] = []
    danger: set[str] = set()
    for q in pathways[prim.pathway].cfg["questions"]:
        for c in q["chips"]:
            for k, v in c["facts"].items():
                if v is True and k in signs and k not in order:
                    order.append(k)
                    if q.get("kind") == "danger":
                        danger.add(k)
    order += [k for k, v in out.facts.items() if v is True and k in signs and k not in order]
    rows = []
    for k in order:
        st = "present" if out.facts.get(k) is True else "absent" if k in out.neg else "not_asked"
        if st == "not_asked" and k not in danger:
            continue
        span = out.spans.get(k)
        if st == "present" and span is None:  # hallucination control: shown as present only with the user's words
            continue
        rows.append({"id": k, "label": engine.sign_label(k, lang), "status": st, "evidence": span})
    rows.sort(key=lambda r: {"present": 0, "absent": 1, "not_asked": 2}[r["status"]])
    rows = rows[:limit]
    if out.facts.get("fever"):
        i = IDX.get(lang, 0)
        band = out.facts.get("temp_band")
        span = out.spans.get("temp_f")
        if out.slots.temp_f is not None:
            val = proute.temperature_said(out.slots.temp_f, span)
        elif band:
            val = f"{band.replace('-', '–')}°F"
        else:
            val = None
        rows.insert(0, {"id": "temperature", "label": TEXT["temperature"][i], "evidence": span,
                        "status": "measured" if val else "not_measured", "value": val or TEXT["not_measured"][i]})
    return rows


def build_card(out: PathwayOutcome, care_type: str, urgency: str, reasoning: str, lang: str) -> Optional[dict]:
    """The non-emergency 'Your assessment' card (debug block only)."""
    prim = out.primary
    if prim is None:
        return None
    lang = lang if lang in IDX else "en"
    i = IDX[lang]
    cfg = load_cfg()
    cat = category_for(prim.pathway, out.facts)
    spec = cfg["categories"].get(cat, {})
    common, pathways, _ = engine.load()
    fx = _derived(out.facts)
    fn = engine._funcs(fx, out.neg, out.known)

    causes = possible_causes(cat, out.facts, lang)
    test_ids: list[str] = []
    for c in causes:
        if c["strength"] != "weak":
            test_ids += [t for t in c["tests"] if t not in test_ids]
    test_ids += [t for t in spec.get("default_tests", []) if t not in test_ids]
    tests = [{"id": t, "label": _t(cfg["tests"][t]["label"], lang), "home_sample": cfg["tests"][t].get("home_sample", False)}
             for t in test_ids[:5] if t in cfg["tests"]]

    precautions = [_t(p, lang) for p in spec.get("precautions", [])]
    for c in causes:
        for d in c["csv"]:
            for ph in csv_precautions().get(d, []):
                line = CSV_SAFE[ph][i]
                have = " ".join(precautions).lower()
                repeat = any(w in have for w in re.findall(r"\w{5,}", line.lower()))
                if not repeat and len(precautions) < len(spec.get("precautions", [])) + 2:
                    precautions.append(line)
    precautions = [p for p in precautions if not is_medicine(p)]
    precautions.append(_t(cfg["common"]["no_medicine"], lang))

    notes = [_t(n["text"], lang) for n in spec.get("notes", []) if engine.expr.evaluate(n["when"], fx, fn)]
    call = [_t(x, lang) for x in spec.get("call_112_if", [])] + [_t(x, lang) for x in cfg["common"]["call_112_common"]]
    show_causes = get_settings().show_possible_causes
    contra = [engine.sign_label(s, lang) for s in sorted(out.contradictions)]
    return {
        "title": TEXT["title"][i],
        "category": cat,
        "pathway": prim.pathway,
        "pathway_label": _t(pathways[prim.pathway].label, lang),
        "secondary": [r.pathway for r in out.results if r is not prim and r.stage != "S0"],
        "stage": prim.stage,
        "stage_label": _t(common["stages"][prim.stage], lang),
        "sections": {
            "symptoms": {"title": TEXT["symptoms"][i], "items": symptoms_checked(out, lang)},
            "why": {"title": TEXT["why"][i], "signs": proute.danger_labels(out, lang), "text": reasoning,
                    "contradictions": [TEXT["contradiction"][i].format(x=x) for x in contra]},
            "causes": {"title": TEXT["causes"][i], "shown": show_causes, "items": causes if show_causes else [],
                       "note": _t(cfg["common"]["only_doctor"], lang), "notes": notes},
            "tests": {"title": TEXT["tests"][i], "lead": TEXT["tests_lead"][i], "items": tests,
                      "home_sample_note": _t(cfg["common"]["home_sample"], lang) if any(t["home_sample"] for t in tests) else None},
            "precautions": {"title": TEXT["precautions"][i], "items": precautions},
            "call_112": {"title": TEXT["call112"][i], "items": call},
            "next": {"title": TEXT["next"][i], "care_type": care_type, "urgency": urgency,
                     "show_hospitals": prim.stage == "S2",
                     "hospitals_note": TEXT["hospitals"][i] if prim.stage == "S2" else None},
        },
    }


def state(out: PathwayOutcome) -> dict:
    """Temporary assessment state for the client to echo back. Nothing is stored server-side."""
    prim = out.primary
    f = out.facts
    return {
        "v": 1,
        "category": category_for(prim.pathway, f) if prim else None,
        "secondary": [r.pathway for r in out.results if prim and r is not prim],
        "stage": prim.stage if prim else None,
        "answered": out.answers.chips,
        "confirm_asked": out.answers.confirm_asked,
        "reported": {k: f.get(k) for k in ("temp_band", "fever_reported_high", "duration_days", "platelets", "bp_sys", "bp_dia")
                     if f.get(k) not in (None, False)},
        "measured_temperature": f.get("temp_measured", False),
        "missing": [k for k in ("duration_days", "temp_f", "age_years") if k not in out.known and f.get(k) is None],
        "contradictions": sorted(out.contradictions),
    }
