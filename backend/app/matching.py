"""Caregiver ranking: hard eligibility filters, then a weighted 0-1 score with a human-readable reason."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Optional

from . import data_adapter
from .config import get_settings
from .data_adapter import IST, parse_slot

# symptom / need -> caregiver skills that help
SKILL_NEEDS: dict[str, list[str]] = {
    "fever": ["fever_assessment", "vitals_check"], "high fever": ["fever_assessment", "vitals_check"],
    "cough": ["fever_assessment", "vitals_check"], "cold": ["general_medicine"], "sore throat": ["general_medicine"],
    "vomiting": ["dehydration_care", "vitals_check"], "diarrhoea": ["dehydration_care", "vitals_check"],
    "dizziness": ["vitals_check", "fall_assessment"], "weakness": ["vitals_check"],
    "injury": ["first_aid", "fall_assessment", "wound_dressing"], "wound": ["wound_dressing", "wound_care", "first_aid"],
    "checkup": ["sample_collection", "vitals_check", "report_review"], "blood pressure": ["vitals_check"],
    "high sugar": ["vitals_check", "endocrinology", "diabetic_foot_care"],
    "joint pain": ["orthopedics"], "back pain": ["orthopedics"], "rash": ["dermatology"], "itching": ["dermatology"],
    "vision problem": ["ophthalmology"], "hearing problem": ["ent"], "pregnancy": ["gynecology"],
    "lump": ["oncology", "gynecology"], "development": ["pediatrics"], "low mood": ["psychiatry"],
    "sleep problem": ["psychiatry"], "headache": ["neurology", "general_medicine"], "palpitations": ["cardiology"],
}
KEYWORD_SKILLS: list[tuple[str, str]] = [
    ("inject", "injection"), ("इंजेक्शन", "injection"), ("drip", "iv_drip"), ("ड्रिप", "iv_drip"), (" iv ", "iv_drip"),
    ("catheter", "catheter_care"), ("कैथेटर", "catheter_care"), ("surgery", "post_op_care"), ("operation", "post_op_care"),
    ("ऑपरेशन", "post_op_care"), ("bedsore", "bedsore_care"), ("bistar", "bedsore_care"), ("बिस्तर", "bedsore_care"),
    ("feeding tube", "feeding_tube_care"), ("फीडिंग", "feeding_tube_care"), ("newborn", "newborn_care"),
    ("delivery", "newborn_care"), ("डिलीवरी", "newborn_care"), ("dressing", "wound_care"), ("ड्रेसिंग", "wound_care"),
    ("thyroid", "endocrinology"), ("थायरॉइड", "endocrinology"), ("report", "report_review"), ("रिपोर्ट", "report_review"),
    ("sugar", "diabetic_foot_care"), ("शुगर", "diabetic_foot_care"), ("heart", "cardiology"), ("dhadkan", "cardiology"),
]
AGE_SKILLS = {"elderly": ["elderly_care"], "child": ["pediatrics_basic", "pediatrics"],
              "infant": ["pediatrics_basic", "pediatrics", "newborn_care"]}
SPECIALTIES = {"cardiology", "orthopedics", "dermatology", "pediatrics", "gynecology", "ent", "ophthalmology",
               "endocrinology", "psychiatry", "neurology", "oncology"}
LANG_CODE = {"en": "en", "hi": "hi", "hinglish": "hi"}
LANG_NAME = {"en": ("English-speaking", "अंग्रेज़ी बोलते हैं", "English bolte hain"),
             "hi": ("Hindi-speaking", "हिंदी बोलते हैं", "Hindi bolte hain")}
SKILL_LABEL = {
    "elderly_care": ("elderly care", "बुज़ुर्गों की देखभाल", "buzurgon ki dekhbhal"),
    "fever_assessment": ("fever checks", "बुखार की जाँच", "bukhar ki jaanch"),
    "wound_dressing": ("wound dressing", "घाव की पट्टी", "ghaav ki patti"),
    "wound_care": ("wound care", "घाव की देखभाल", "ghaav ki dekhbhal"),
    "injection": ("injections", "इंजेक्शन", "injection"), "iv_drip": ("IV drips", "ड्रिप", "drip"),
    "catheter_care": ("catheter care", "कैथेटर देखभाल", "catheter care"),
    "post_op_care": ("post-surgery care", "ऑपरेशन के बाद देखभाल", "operation ke baad dekhbhal"),
    "pediatrics_basic": ("children", "बच्चों का इलाज", "bachchon ka ilaaj"),
    "newborn_care": ("newborn care", "नवजात देखभाल", "navjaat dekhbhal"),
    "dehydration_care": ("dehydration care", "पानी की कमी की देखभाल", "paani ki kami ki dekhbhal"),
    "bedsore_care": ("bedsore care", "घाव (बेडसोर) की देखभाल", "bedsore care"),
    "feeding_tube_care": ("feeding tube care", "फीडिंग ट्यूब देखभाल", "feeding tube care"),
    "diabetic_foot_care": ("diabetic foot care", "शुगर के घाव की देखभाल", "sugar ke ghaav ki dekhbhal"),
    "first_aid": ("first aid", "प्राथमिक उपचार", "first aid"), "fall_assessment": ("fall checks", "गिरने की जाँच", "girne ki jaanch"),
    "sample_collection": ("sample collection", "सैंपल लेना", "sample lena"), "vitals_check": ("BP/sugar checks", "बीपी/शुगर जाँच", "BP/sugar jaanch"),
    "report_review": ("explaining reports", "रिपोर्ट समझाना", "report samjhana"),
}
SPEC_LABEL = {"cardiology": ("heart specialist", "हृदय विशेषज्ञ", "dil ke specialist"),
              "orthopedics": ("bone & joint specialist", "हड्डी विशेषज्ञ", "haddi ke specialist"),
              "dermatology": ("skin specialist", "त्वचा विशेषज्ञ", "skin specialist"),
              "pediatrics": ("child specialist", "बाल विशेषज्ञ", "bachchon ke specialist"),
              "gynecology": ("women's health specialist", "महिला रोग विशेषज्ञ", "mahila specialist"),
              "ent": ("ear-nose-throat specialist", "नाक-कान-गला विशेषज्ञ", "naak-kaan-gala specialist"),
              "ophthalmology": ("eye specialist", "आँखों के विशेषज्ञ", "aankh ke specialist"),
              "endocrinology": ("sugar & thyroid specialist", "शुगर-थायरॉइड विशेषज्ञ", "sugar-thyroid specialist"),
              "psychiatry": ("mental health specialist", "मानसिक स्वास्थ्य विशेषज्ञ", "mental health specialist"),
              "neurology": ("nerve & brain specialist", "नस-दिमाग विशेषज्ञ", "nas-dimaag specialist"),
              "oncology": ("lump & cancer-screening specialist", "गांठ जाँच विशेषज्ञ", "gaanth jaanch specialist")}
IDX = {"en": 0, "hi": 1, "hinglish": 2}


@lru_cache
def match_cfg() -> dict:
    return json.loads((get_settings().config_dir / "matching.json").read_text(encoding="utf-8"))


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def needed_skills(symptoms: list[str], age_group: Optional[str], text: str) -> list[str]:
    need: list[str] = []
    for s in symptoms:
        need += SKILL_NEEDS.get(s, [])
    t = f" {text.lower()} "
    need += [sk for kw, sk in KEYWORD_SKILLS if kw in t]
    need += AGE_SKILLS.get(age_group or "", [])
    return list(dict.fromkeys(need))


@dataclass
class Scored:
    cg: dict
    score: float
    dist_km: Optional[float]
    slot: Optional[datetime]
    skills_hit: list[str]
    lang_ok: bool


def _earliest_slot(cg: dict, now: datetime, urgency: str) -> Optional[datetime]:
    slots = sorted(d for d in (parse_slot(s) for s in cg.get("availability_slots", [])) if d and d >= now)
    if not slots:
        return None
    if urgency == "same_day":
        today = [d for d in slots if d.astimezone(IST).date() == now.astimezone(IST).date()]
        return today[0] if today else None
    return slots[0]


def rank(care_type: str, urgency: str, lang: str, location: Optional[dict], symptoms: list[str],
         age_group: Optional[str] = None, text: str = "", now: Optional[datetime] = None,
         caregivers: Optional[list[dict]] = None, top_k: Optional[int] = None) -> list[Scored]:
    cfg = match_cfg()
    roles = cfg["roles"].get(care_type, [])
    if not roles:
        return []
    now = now or datetime.now(IST)
    cgs = caregivers if caregivers is not None else data_adapter.load_caregivers()
    home = care_type in cfg["home_visit_types"]
    w = dict(cfg["weights_home"] if home else cfg["weights_remote"])
    if care_type == "specialist_referral":
        w["distance"] = cfg.get("specialist_distance_weight", 0.0)
    tot = sum(w.values()) or 1.0
    w = {k: v / tot for k, v in w.items()}
    need = needed_skills(symptoms, age_group, text)
    need_spec = [s for s in need if s in SPECIALTIES]
    user_lang = LANG_CODE.get(lang, "en")
    cutoff = cfg["distance_cutoff_km"]

    def score_pool(pool_roles: list[str], strict: bool) -> list[Scored]:
        out = []
        for cg in cgs:
            if cg.get("role") not in pool_roles:
                continue
            skills = set(cg.get("skills", []))
            if care_type == "specialist_referral" and need_spec and strict and not (skills & set(need_spec)):
                continue
            d = None
            if location and cg.get("lat") is not None:
                d = haversine_km(location["lat"], location["lng"], float(cg["lat"]), float(cg["lng"]))
            if home and strict and d is not None and d > cutoff:
                continue
            slot = _earliest_slot(cg, now, urgency)
            if slot is None and strict and urgency == "same_day":
                continue
            hit = [s for s in need if s in skills]
            s_skill = (len(hit) / len(need)) if need else 1.0
            if need_spec:
                s_skill = max(s_skill, 1.0 if skills & set(need_spec) else 0.0)
            s_dist = max(0.0, 1 - d / cutoff) if d is not None else 0.5
            if slot is None:
                s_av = 0.0
            else:
                hrs = (slot - now).total_seconds() / 3600
                s_av = max(0.0, 1 - hrs / cfg["horizon_hours"])
            lang_ok = user_lang in cg.get("languages", [])
            s_lang = 1.0 if lang_ok else 0.0
            s_rate = min(1.0, max(0.0, (float(cg.get("rating", 0)) - 3.0) / 2.0))
            total = (w["skill"] * s_skill + w["distance"] * s_dist + w["availability"] * s_av
                     + w["language"] * s_lang + w["rating"] * s_rate)
            out.append(Scored(cg, round(min(1.0, max(0.0, total)), 3), d, slot, hit, lang_ok))
        return out

    res = score_pool(roles, strict=True)
    if not res:
        res = score_pool(roles + cfg["fallback_roles"].get(care_type, []), strict=False)
    res.sort(key=lambda s: (-s.score, s.dist_km if s.dist_km is not None else 1e9, s.cg["caregiver_id"]))
    return res[: (top_k or cfg["top_k"])]


def _fmt_time(slot: datetime, now: datetime, lang: str) -> str:
    s, n = slot.astimezone(IST), now.astimezone(IST)
    h = s.hour % 12 or 12
    ampm = "am" if s.hour < 12 else "pm"
    days = (s.date() - n.date()).days
    if lang == "hi":
        part = "सुबह" if s.hour < 12 else ("दोपहर" if s.hour < 16 else ("शाम" if s.hour < 20 else "रात"))
        day = "आज" if days == 0 else ("कल" if days == 1 else s.strftime("%d/%m"))
        return f"{day} {part} {h} बजे"
    if lang == "hinglish":
        day = "aaj" if days == 0 else ("kal" if days == 1 else s.strftime("%d/%m"))
        return f"{day} {h} {ampm}"
    day = "today" if days == 0 else ("tomorrow" if days == 1 else s.strftime("%a %d %b"))
    return f"{day} at {h} {ampm}"


def reason(sc: Scored, care_type: str, lang: str, now: Optional[datetime] = None) -> str:
    """Deterministic reason from the actual score components, in the user's language."""
    now = now or datetime.now(IST)
    i = IDX.get(lang, 0)
    parts = []
    if sc.lang_ok:
        parts.append(LANG_NAME[LANG_CODE.get(lang, "en")][i])
    if care_type == "gp_teleconsult":
        parts.append(("video/phone consult", "वीडियो/फ़ोन पर सलाह", "video/phone par salaah")[i])
    elif sc.dist_km is not None:
        km = f"{sc.dist_km:.0f}" if sc.dist_km >= 1 else "<1"
        parts.append((f"{km} km away", f"{km} किमी दूर", f"{km} km door")[i])
    if sc.slot:
        t = _fmt_time(sc.slot, now, lang)
        parts.append((f"free {t}", f"{t} खाली", f"{t} free")[i])
    spec = [s for s in sc.cg.get("skills", []) if s in SPEC_LABEL][:1]
    hit = [h for h in sc.skills_hit if h in SKILL_LABEL][:1]
    if care_type == "specialist_referral" and spec:
        parts.append(SPEC_LABEL[spec[0]][i])
    elif hit:
        lab = SKILL_LABEL[hit[0]][i]
        parts.append((f"experienced in {lab}", f"{lab} में अनुभव", f"{lab} mein experience")[i])
    rating = sc.cg.get("rating")
    parts.append((f"rated {rating}", f"रेटिंग {rating}", f"rating {rating}")[i])
    out = ", ".join(parts)
    return out[0].upper() + out[1:] if out else out
