"""Caregiver ranking.

1. Hard filter by eligible role (config/care_type_to_roles.json) and, for specialist referrals, by the specialty
   inferred from the symptoms (rash -> dermatology, knee pain -> orthopedics, child -> pediatrics, ...).
2. Widen the search radius in steps (5 -> 10 -> 20 km -> all NCR) until enough candidates are found.
   Teleconsults ignore distance.
3. Weighted 0-1 score: skill, distance, availability (urgency-aware), language, rating, experience.
4. Never return an empty list for a non-emergency case: if nobody is free in the needed window, the best
   caregivers are still returned with their earliest slot shown in the reason.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from typing import Optional

from . import data_adapter
from .config import get_settings
from .data_adapter import IST, parse_slot

# symptom / need -> caregiver skills that help
SKILL_NEEDS: dict[str, list[str]] = {
    "fever": ["fever_assessment", "vitals_check"], "high fever": ["fever_assessment", "vitals_check"],
    "cough": ["fever_assessment", "vitals_check", "chronic_cough"], "cold": ["general_medicine"],
    "sore throat": ["general_medicine", "ear_nose_throat"],
    "vomiting": ["dehydration_care", "vitals_check"], "diarrhoea": ["dehydration_care", "vitals_check"],
    "dizziness": ["vitals_check", "fall_assessment"], "weakness": ["vitals_check"],
    "injury": ["first_aid", "fall_assessment", "wound_dressing"], "wound": ["wound_dressing", "wound_care", "first_aid"],
    "checkup": ["sample_collection", "vitals_check", "report_review"], "blood pressure": ["vitals_check", "bp_management"],
    "high sugar": ["vitals_check", "diabetic_foot_care", "diabetes_care"],
    "joint pain": ["joint_pain"], "back pain": ["back_pain"], "rash": ["skin_conditions", "rash_assessment"],
    "itching": ["skin_conditions"], "vision problem": ["eye_checkup", "vision_care"], "hearing problem": ["hearing_assessment"],
    "pregnancy": ["pregnancy_care"], "lump": ["lump_assessment"], "development": ["growth_development", "child_health"],
    "low mood": ["mental_health"], "sleep problem": ["sleep_problems"], "headache": ["headache_clinic", "general_medicine"],
    "palpitations": ["heart_checkup"], "breathlessness": ["breathing_conditions"],
}
KEYWORD_SKILLS: list[tuple[str, str]] = [
    ("inject", "injection"), ("इंजेक्शन", "injection"), ("insulin", "injection"), ("drip", "iv_drip"), ("ड्रिप", "iv_drip"),
    (" iv ", "iv_drip"), ("catheter", "catheter_care"), ("कैथेटर", "catheter_care"), ("surgery", "post_op_care"),
    ("operation", "post_op_care"), ("ऑपरेशन", "post_op_care"), ("bedsore", "bedsore_care"), ("bed sore", "bedsore_care"),
    ("bistar", "bedsore_care"), ("बिस्तर", "bedsore_care"), ("feeding tube", "feeding_tube_care"), ("फीडिंग", "feeding_tube_care"),
    ("newborn", "newborn_care"), ("delivery", "newborn_care"), ("डिलीवरी", "newborn_care"), ("dressing", "wound_care"),
    ("ड्रेसिंग", "wound_care"), ("diabet", "diabetic_foot_care"), ("sugar", "diabetic_foot_care"), ("शुगर", "diabetic_foot_care"),
    ("report", "report_review"), ("रिपोर्ट", "report_review"),
]
AGE_SKILLS = {"elderly": ["elderly_care"], "child": ["pediatrics_basic", "child_health"],
              "infant": ["pediatrics_basic", "newborn_care", "child_health"]}

# specialty inference: symptom slots and raw keywords (EN / Hinglish / Devanagari)
SYMPTOM_SPECIALTY = {
    "rash": "dermatology", "itching": "dermatology", "joint pain": "orthopedics", "back pain": "orthopedics",
    "palpitations": "cardiology", "blood pressure": "cardiology", "hearing problem": "ent", "sore throat": "ent",
    "pregnancy": "gynecology", "headache": "neurology", "breathlessness": "pulmonology", "vision problem": "ophthalmology",
    "high sugar": "endocrinology", "low mood": "psychiatry", "sleep problem": "psychiatry", "lump": "oncology",
    "development": "pediatrics",
}
KEYWORD_SPECIALTY: list[tuple[str, str]] = [
    (r"skin|rash|acne|pimple|eczema|daane|dane|daag|khujli|chakatte|दाने|दाग|खुजली|त्वचा|मुहांसे", "dermatology"),
    (r"knee|joint|ghutn|jod|back pain|kamar|spine|fracture|haddi|घुटन|जोड़|कमर|हड्डी|heel|edi|एड़ी", "orthopedics"),
    (r"heart|dil\b|dhadkan|chest|bp\b|blood pressure|धड़कन|दिल|बीपी", "cardiology"),
    (r"\bear\b|kaan|nose|naak|throat|gala|gale|hearing|sunai|कान|नाक|गला|गले|सुनाई|tonsil", "ent"),
    (r"pregnan|period|mahwari|breast|garbh|गर्भ|पीरियड|स्तन|vaginal|white discharge|safe?d\s+paa?ni|likoria|menopaus|"
     r"delivery|postpartum|prasav|yoni|सफ़?े?द\s*पानी|माहवारी|डिलीवरी|प्रसव", "gynecology"),
    (r"migraine|headache|sar dard|sir dard|tremor|kaanp|numb|tingl|sunn|seizure history|सिर दर्द|सुन्न|कांप", "neurology"),
    (r"asthma|breath|saans|wheez|chronic cough|cough for|khansi .*(hafte|mahine)|दमा|साँस|सांस", "pulmonology"),
    (r"\beye|vision|aankh|dhundh|आँख|धुंधल", "ophthalmology"),
    (r"thyroid|sugar|diabet|शुगर|थायरॉइड", "endocrinology"),
    (r"depress|anxiety|tension|ghabrah|udaas|sleep|neend|उदास|घबराह|नींद|stress", "psychiatry"),
    (r"lump|gaanth|गांठ|swelling in (the )?(neck|armpit)", "oncology"),
]
SPECIALTIES = {"cardiology", "orthopedics", "dermatology", "pediatrics", "gynecology", "ent", "ophthalmology",
               "endocrinology", "psychiatry", "neurology", "oncology", "pulmonology"}
RADIUS_STEPS = [5.0, 10.0, 20.0, None]  # None = all NCR
MIN_CANDIDATES = 3

LANG_CODE = {"en": "en", "hi": "hi", "hinglish": "hi"}
IDX = {"en": 0, "hi": 1, "hinglish": 2}
LANG_NAME = {"en": ("English-speaking", "अंग्रेज़ी बोलते हैं", "English bolte hain"),
             "hi": ("Hindi-speaking", "हिंदी बोलते हैं", "Hindi bolte hain")}
SPEC_LABEL = {
    "cardiology": ("Heart specialist", "हृदय विशेषज्ञ", "Dil ke specialist"),
    "orthopedics": ("Bone & joint specialist", "हड्डी विशेषज्ञ", "Haddi ke specialist"),
    "dermatology": ("Skin specialist", "त्वचा विशेषज्ञ", "Skin specialist"),
    "pediatrics": ("Child specialist", "बाल रोग विशेषज्ञ", "Bachchon ke specialist"),
    "gynecology": ("Women's health specialist", "महिला रोग विशेषज्ञ", "Mahila rog specialist"),
    "ent": ("Ear-nose-throat specialist", "नाक-कान-गला विशेषज्ञ", "Naak-kaan-gala specialist"),
    "ophthalmology": ("Eye specialist", "आँखों के विशेषज्ञ", "Aankh ke specialist"),
    "endocrinology": ("Sugar & thyroid specialist", "शुगर-थायरॉइड विशेषज्ञ", "Sugar-thyroid specialist"),
    "psychiatry": ("Mental health specialist", "मानसिक स्वास्थ्य विशेषज्ञ", "Mental health specialist"),
    "neurology": ("Nerve & brain specialist", "नस-दिमाग विशेषज्ञ", "Nas-dimaag specialist"),
    "oncology": ("Lump & cancer-screening specialist", "गांठ जाँच विशेषज्ञ", "Gaanth jaanch specialist"),
    "pulmonology": ("Lung & breathing specialist", "फेफड़ों के विशेषज्ञ", "Phephdon ke specialist"),
}
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
    "bedsore_care": ("bedsore care", "बेडसोर की देखभाल", "bedsore care"),
    "feeding_tube_care": ("feeding tube care", "फीडिंग ट्यूब देखभाल", "feeding tube care"),
    "diabetic_foot_care": ("diabetic wound care", "शुगर के घाव की देखभाल", "sugar ke ghaav ki dekhbhal"),
    "first_aid": ("first aid", "प्राथमिक उपचार", "first aid"), "fall_assessment": ("fall checks", "गिरने की जाँच", "girne ki jaanch"),
    "sample_collection": ("sample collection", "सैंपल लेना", "sample lena"), "vitals_check": ("BP/sugar checks", "बीपी/शुगर जाँच", "BP/sugar jaanch"),
    "report_review": ("explaining reports", "रिपोर्ट समझाना", "report samjhana"),
}


@lru_cache
def match_cfg() -> dict:
    return json.loads((get_settings().config_dir / "matching.json").read_text(encoding="utf-8"))


@lru_cache
def role_map() -> dict:
    return json.loads((get_settings().config_dir / "care_type_to_roles.json").read_text(encoding="utf-8"))


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


def infer_specialties(symptoms: list[str], age_group: Optional[str], text: str, prefer: Optional[str] = None) -> list[str]:
    """Specialties that fit the request, most specific first. Children also accept pediatrics.
    `prefer`: the specialty of the pathway that decided (women's health -> gynaecology) goes first."""
    found: list[str] = [prefer] if prefer else []
    t = text.lower()
    from . import lexicon  # a named condition's treating specialist first ("cancer ka ilaaj" -> oncology)
    for h in lexicon.hits(text):
        spec = lexicon.specialty(h.canonical) if h.kind == "disease" else None
        if spec and spec not in found:
            found.append(spec)
    for rx, spec in KEYWORD_SPECIALTY:
        if re.search(rx, t) and spec not in found:
            found.append(spec)
    for s in symptoms:
        spec = SYMPTOM_SPECIALTY.get(s)
        if spec and spec not in found:
            found.append(spec)
    # pregnancy / after delivery: the gynaecologist first (a mood concern keeps mental-health support first)
    if "gynecology" in found and not prefer and re.search(r"pregnan|garbh|गर्भ|postpartum|delivery|prasav|डिलीवरी|प्रसव", t) and "psychiatry" not in found:
        found.remove("gynecology")
        found.insert(0, "gynecology")
    if age_group in ("child", "infant") and "pediatrics" not in found:
        found.append("pediatrics")
    return found


@dataclass
class Scored:
    cg: dict
    score: float
    dist_km: Optional[float]
    slot: Optional[datetime]
    skills_hit: list[str]
    lang_ok: bool
    in_window: bool = True  # free within the urgency window (today for same_day)


@dataclass
class MatchInfo:
    eligible_roles: list[str] = field(default_factory=list)
    pool: int = 0
    specialties: list[str] = field(default_factory=list)
    after_specialty: int = 0
    radius_km: Optional[float] = None
    after_distance: int = 0
    free_in_window: int = 0
    returned: int = 0
    used_fallback_roles: bool = False


def _earliest_slots(cg: dict, now: datetime) -> list[datetime]:
    return sorted(d for d in (parse_slot(s) for s in cg.get("availability_slots", [])) if d and d >= now)


def _pick_slot(cg: dict, now: datetime, urgency: str) -> tuple[Optional[datetime], bool]:
    """Best slot for the urgency, and whether it is inside the wanted window."""
    slots = _earliest_slots(cg, now)
    if not slots:
        return None, False
    if urgency == "same_day":
        today = [d for d in slots if d.astimezone(IST).date() == now.astimezone(IST).date()]
        return (today[0], True) if today else (slots[0], False)
    horizon = match_cfg().get("horizon_hours", 72)
    return slots[0], (slots[0] - now).total_seconds() / 3600 <= horizon


def _availability_score(slot: Optional[datetime], in_window: bool, now: datetime, urgency: str) -> float:
    if slot is None:
        return 0.0
    hrs = max(0.0, (slot - now).total_seconds() / 3600)
    if urgency == "same_day":
        return max(0.4, 1 - hrs / 12) if in_window else max(0.0, 0.25 * (1 - hrs / 72))
    return max(0.05, 1 - hrs / match_cfg().get("horizon_hours", 72))


def rank_with_info(care_type: str, urgency: str, lang: str, location: Optional[dict], symptoms: list[str],
                   age_group: Optional[str] = None, text: str = "", now: Optional[datetime] = None,
                   caregivers: Optional[list[dict]] = None, top_k: Optional[int] = None,
                   prefer_specialty: Optional[str] = None) -> tuple[list[Scored], MatchInfo]:
    info = MatchInfo()
    spec_cfg = role_map().get(care_type) or {"roles": match_cfg()["roles"].get(care_type, []), "fallback_roles": []}
    roles = spec_cfg["roles"]
    info.eligible_roles = roles
    if not roles:
        return [], info  # emergency: never match
    cfg = match_cfg()
    now = now or datetime.now(IST)
    cgs = caregivers if caregivers is not None else data_adapter.load_caregivers()
    mode = spec_cfg.get("mode")
    remote = mode == "teleconsult"
    w = dict(cfg["weights_remote"] if remote else cfg["weights_home"])
    if care_type == "specialist_referral":
        w.update(cfg.get("weights_specialist", {}))
    w.setdefault("experience", 0.0)
    tot = sum(w.values()) or 1.0
    w = {k: v / tot for k, v in w.items()}
    need = needed_skills(symptoms, age_group, text)
    user_lang = LANG_CODE.get(lang, "en")

    pool = [c for c in cgs if c.get("role") in roles]
    if len(pool) < MIN_CANDIDATES and spec_cfg.get("fallback_roles"):
        pool += [c for c in cgs if c.get("role") in spec_cfg["fallback_roles"]]
        info.used_fallback_roles = True
    info.pool = len(pool)

    specs: list[str] = []
    if care_type == "specialist_referral":
        specs = infer_specialties(symptoms, age_group, text, prefer_specialty)
        info.specialties = specs
        if specs:
            def spec_of(c):
                return c.get("specialty") or next((s for s in c.get("skills", []) if s in SPECIALTIES), None)
            narrowed = [c for c in pool if spec_of(c) in specs]
            if narrowed:
                pool = narrowed
    info.after_specialty = len(pool)

    def dist(c):
        if not location or c.get("lat") is None:
            return None
        return haversine_km(location["lat"], location["lng"], float(c["lat"]), float(c["lng"]))

    dists = {c["caregiver_id"]: dist(c) for c in pool}
    candidates = pool
    if not remote and location:
        # smallest radius giving a full list (top_k); else the 20 km ring if it has >= 3; else all NCR
        target = top_k or cfg["top_k"]
        rings = {r: [c for c in pool if r is None or (dists[c["caregiver_id"]] is not None and dists[c["caregiver_id"]] <= r)]
                 for r in RADIUS_STEPS}
        chosen = next((r for r in RADIUS_STEPS[:-1] if len(rings[r]) >= target), None)
        if chosen is None:
            chosen = next((r for r in reversed(RADIUS_STEPS[:-1]) if len(rings[r]) >= MIN_CANDIDATES), None)
        candidates, info.radius_km = rings[chosen], chosen
    info.after_distance = len(candidates)
    scale_km = info.radius_km or cfg.get("distance_cutoff_km", 20)

    out: list[Scored] = []
    for cg in candidates:
        skills = set(cg.get("skills", []))
        d = dists[cg["caregiver_id"]]
        slot, in_window = _pick_slot(cg, now, urgency)
        hit = [s for s in need if s in skills]
        s_skill = (len(hit) / len(need)) if need else 1.0
        if specs:
            s_skill = max(s_skill, 1.0 if (cg.get("specialty") in specs or skills & set(specs)) else 0.0)
            if specs and cg.get("specialty") == specs[0]:
                s_skill = 1.0
        s_dist = max(0.0, 1 - d / max(scale_km * 1.5, 1.0)) if d is not None else 0.5
        s_av = _availability_score(slot, in_window, now, urgency)
        lang_ok = user_lang in cg.get("languages", [])
        s_rate = min(1.0, max(0.0, (float(cg.get("rating", 0)) - 3.0) / 2.0))
        s_exp = min(1.0, float(cg.get("years_experience") or 0) / 20.0)
        total = (w["skill"] * s_skill + w["distance"] * s_dist + w["availability"] * s_av
                 + w["language"] * (1.0 if lang_ok else 0.0) + w["rating"] * s_rate + w["experience"] * s_exp)
        out.append(Scored(cg, round(min(1.0, max(0.0, total)), 3), d, slot, hit, lang_ok, in_window))
    info.free_in_window = sum(s.in_window for s in out)
    out.sort(key=lambda s: (-s.score, s.dist_km if s.dist_km is not None else 1e9, s.cg["caregiver_id"]))
    out = out[: (top_k or cfg["top_k"])]
    info.returned = len(out)
    return out, info


def rank(*args, **kwargs) -> list[Scored]:
    return rank_with_info(*args, **kwargs)[0]


def _fmt_time(slot: datetime, now: datetime, lang: str) -> str:
    s, n = slot.astimezone(IST), now.astimezone(IST)
    h12 = s.hour % 12 or 12
    hm = f"{h12}:{s.minute:02d}"
    ampm = "AM" if s.hour < 12 else "PM"
    days = (s.date() - n.date()).days
    if lang == "hi":
        part = "सुबह" if s.hour < 12 else ("दोपहर" if s.hour < 16 else ("शाम" if s.hour < 20 else "रात"))
        day = "आज" if days == 0 else ("कल" if days == 1 else s.strftime("%d/%m"))
        return f"{day} {part} {hm} बजे"
    if lang == "hinglish":
        day = "aaj" if days == 0 else ("kal" if days == 1 else s.strftime("%d/%m"))
        return f"{day} {hm} {ampm}"
    day = "today" if days == 0 else ("tomorrow" if days == 1 else s.strftime("%a %d %b"))
    return f"{day} {hm} {ampm}"


def reason(sc: Scored, care_type: str, lang: str, now: Optional[datetime] = None) -> str:
    """Deterministic reason built from the actual score components, in the user's language."""
    now = now or datetime.now(IST)
    i = IDX.get(lang, 0)
    lang = lang if lang in IDX else "en"
    parts: list[str] = []
    spec = sc.cg.get("specialty") or next((s for s in sc.cg.get("skills", []) if s in SPEC_LABEL), None)
    if care_type == "specialist_referral" and spec in SPEC_LABEL:
        parts.append(SPEC_LABEL[spec][i])
    if sc.lang_ok:
        parts.append(LANG_NAME[LANG_CODE.get(lang, "en")][i])
    if care_type == "gp_teleconsult":
        parts.append(("video call", "वीडियो कॉल", "video call")[i])
    elif sc.dist_km is not None:
        km = f"{sc.dist_km:.1f}" if sc.dist_km < 10 else f"{sc.dist_km:.0f}"
        parts.append((f"{km} km away", f"{km} किमी दूर", f"{km} km door")[i])
    if sc.slot:
        tm = _fmt_time(sc.slot, now, lang)
        if sc.in_window:
            parts.append((f"free {tm}", f"{tm} खाली", f"{tm} free")[i])
        else:
            parts.append((f"earliest {tm}", f"सबसे पहले {tm}", f"sabse pehle {tm}")[i])
    hit = [h for h in sc.skills_hit if h in SKILL_LABEL][:1]
    if hit and care_type != "specialist_referral":
        lab = SKILL_LABEL[hit[0]][i]
        parts.append((f"experienced in {lab}", f"{lab} में अनुभव", f"{lab} mein experience")[i])
    rating = sc.cg.get("rating")
    if rating is not None:
        parts.append(f"{rating}★")
    yrs = sc.cg.get("years_experience")
    if yrs:
        parts.append((f"{yrs} yrs experience", f"{yrs} साल का अनुभव", f"{yrs} saal ka anubhav")[i])
    out = " · ".join(parts)
    return out[0].upper() + out[1:] if out else out
