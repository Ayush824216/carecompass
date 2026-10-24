"""Deterministic, plain-language reasoning built from the user's own reported facts. No diagnosis."""
from __future__ import annotations

from .intake import Slots

SYM = {  # canonical -> (en, hi, hinglish)
    "high fever": ("high fever", "तेज़ बुखार", "tez bukhar"), "fever": ("fever", "बुखार", "bukhar"),
    "cough": ("cough", "खांसी", "khansi"), "cold": ("cold", "जुकाम", "zukaam"),
    "sore throat": ("sore throat", "गले में खराश", "gale mein kharash"),
    "breathlessness": ("breathlessness", "साँस फूलना", "saans phoolna"), "chest pain": ("chest pain", "सीने में दर्द", "seene mein dard"),
    "headache": ("headache", "सिर दर्द", "sar dard"), "abdominal pain": ("stomach pain", "पेट दर्द", "pet dard"),
    "vomiting": ("vomiting", "उल्टी", "ulti"), "diarrhoea": ("loose motions", "दस्त", "dast"),
    "dizziness": ("dizziness", "चक्कर", "chakkar"), "weakness": ("weakness", "कमज़ोरी", "kamzori"),
    "rash": ("skin rash or patches", "त्वचा पर दाने या दाग", "skin par daane ya daag"), "itching": ("itching", "खुजली", "khujli"),
    "acidity": ("acidity or gas", "एसिडिटी या गैस", "acidity ya gas"), "swelling": ("swelling", "सूजन", "sujan"),
    "wound": ("a wound", "घाव", "ghaav"), "injury": ("an injury", "चोट", "chot"), "back pain": ("back pain", "कमर दर्द", "kamar dard"),
    "joint pain": ("joint or knee pain", "जोड़ों या घुटनों में दर्द", "jodon ya ghutno mein dard"),
    "vision problem": ("vision trouble", "देखने में दिक्कत", "dekhne mein dikkat"),
    "hearing problem": ("hearing trouble", "सुनने में दिक्कत", "sunne mein dikkat"),
    "high sugar": ("sugar readings", "शुगर", "sugar"), "blood pressure": ("blood pressure", "बीपी", "BP"),
    "low mood": ("low mood or worry", "उदासी या घबराहट", "udaasi ya ghabrahat"),
    "sleep problem": ("poor sleep", "नींद की कमी", "neend ki kami"), "palpitations": ("fast heartbeat", "तेज़ धड़कन", "tez dhadkan"),
    "lump": ("a lump", "गांठ", "gaanth"), "pain": ("pain", "दर्द", "dard"),
    "nursing need": ("nursing care at home", "घर पर नर्सिंग देखभाल", "ghar par nursing dekhbhal"),
    "checkup": ("a check-up or test", "जाँच", "jaanch"), "pregnancy": ("pregnancy care", "गर्भावस्था की देखभाल", "pregnancy ki dekhbhal"),
    "development": ("a child development concern", "बच्चे के विकास की चिंता", "bachche ke vikas ki chinta"),
}
DUR = {"hours": ("since today", "आज से", "aaj se"), "acute": ("for a few days", "कुछ दिनों से", "kuch dino se"),
       "week": ("for about a week", "लगभग एक हफ्ते से", "lagbhag ek hafte se"),
       "chronic": ("for a long time (months)", "कई महीनों से", "kai mahino se")}
WHO = {"elderly": ("an elderly person", "बुज़ुर्ग", "buzurg"), "child": ("a child", "बच्चा", "bachcha"),
       "infant": ("a baby", "शिशु", "baby")}
CARE = {
    "paramedic_home_visit": ("A paramedic home visit", "पैरामेडिक का घर आना", "Paramedic ka ghar aana"),
    "nurse_home_visit": ("A nurse home visit", "नर्स का घर आना", "Nurse ka ghar aana"),
    "gp_teleconsult": ("A phone/video consult with a general doctor", "सामान्य डॉक्टर से फ़ोन/वीडियो पर सलाह",
                       "General doctor se phone/video par salaah"),
    "specialist_referral": ("An appointment with a specialist doctor", "विशेषज्ञ डॉक्टर से मिलना", "Specialist doctor se milna"),
    "emergency_referral": ("Emergency help", "आपातकालीन मदद", "Emergency madad"),
}
URG = {"routine": ("in the next few days", "अगले कुछ दिनों में", "agle kuch dino mein"),
       "same_day": ("today", "आज ही", "aaj hi"), "immediate": ("right now", "अभी तुरंत", "abhi turant")}
WHY = {
    "paramedic_home_visit": ("so the patient can be checked at home", "ताकि घर पर ही जाँच हो सके", "taaki ghar par hi jaanch ho sake"),
    "nurse_home_visit": ("for regular care at home", "घर पर नियमित देखभाल के लिए", "ghar par niyamit dekhbhal ke liye"),
    "gp_teleconsult": ("as this sounds mild and can be discussed remotely", "क्योंकि यह हल्का लगता है और फ़ोन पर बात हो सकती है",
                       "kyunki yeh halka lagta hai aur phone par baat ho sakti hai"),
    "specialist_referral": ("as this needs a specialist's opinion", "क्योंकि इसके लिए विशेषज्ञ की राय चाहिए",
                            "kyunki iske liye specialist ki raay chahiye"),
    "emergency_referral": ("", "", ""),
}
IDX = {"en": 0, "hi": 1, "hinglish": 2}


def _join(items: list[str], lang: str) -> str:
    if len(items) <= 1:
        return "".join(items)
    conj = {"en": " and ", "hi": " और ", "hinglish": " aur "}[lang]
    return ", ".join(items[:-1]) + conj + items[-1]


def reasoning(slots: Slots, care_type: str, urgency: str, lang: str) -> str:
    i = IDX.get(lang, 0)
    lang = lang if lang in IDX else "en"
    syms = [SYM[s][i] for s in slots.symptoms if s in SYM][:3]
    parts = []
    if syms:
        what = _join(syms, lang)
        dur = f" {slots.duration_text}" if slots.duration_text else (f" {DUR[slots.duration][i]}" if slots.duration in DUR else "")
        who = WHO.get(slots.age_group)
        if lang == "en":
            s = f"{what[0].upper() + what[1:]}{dur}" + (f" in {who[0]}" if who else "")
        elif lang == "hi":
            s = (f"{who[1]} को " if who else "") + f"{dur.strip()} {what}".strip()
        else:
            s = (f"{who[2]} ko " if who else "") + f"{dur.strip()} {what}".strip()
        parts.append(s[0].upper() + s[1:] if lang != "hi" else s)
    notes = []
    if slots.breathing == "ok":
        notes.append(("no breathing difficulty reported", "साँस की कोई तकलीफ नहीं बताई गई", "saans ki takleef nahi batayi")[i])
    if slots.can_travel is False:
        notes.append(("unable to travel easily", "बाहर जाना मुश्किल", "bahar jaana mushkil")[i])
    if slots.severity == "mild":
        notes.append(("described as mild", "हल्की बताई गई", "halki batayi")[i])
    head = ", ".join(parts + notes)
    care = CARE[care_type][i]
    urg = URG[urgency][i]
    why = WHY[care_type][i]
    if lang == "en":
        tail = f"{care} {urg} is suggested{', ' + why if why else ''}."
    elif lang == "hi":
        tail = f"सुझाव: {care}, {urg}{', ' + why if why else ''}।"
    else:
        tail = f"Sujhav: {care}, {urg}{', ' + why if why else ''}."
    end = "." if lang != "hi" else "।"
    return f"{head}{end} {tail}" if head else tail
