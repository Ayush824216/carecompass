"""Reproducible synthetic dev data for CareCompass.

Writes dev_data/taxonomy.json, dev_data/vignettes.csv and dev_data/caregivers.json.
Everything here is SELF-GENERATED and SYNTHETIC (templates + seeded randomisation,
no LLM calls, no real patients).

    python scripts/make_dev_data.py [--n 400] [--seed 42] [--base-date 2026-10-24]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CARE_TYPES = {
    "paramedic_home_visit": {
        "en": "A trained paramedic visits your home to check vital signs, dress minor wounds and assess common illness.",
        "hi": "प्रशिक्षित पैरामेडिक घर आकर जाँच करेंगे, छोटी चोट की पट्टी करेंगे और सामान्य बीमारी देखेंगे।",
    },
    "nurse_home_visit": {
        "en": "A nurse visits your home for ongoing care: injections, drips, wound or catheter care, bedridden patients.",
        "hi": "नर्स घर आकर लगातार देखभाल करेंगी: इंजेक्शन, ड्रिप, घाव या कैथेटर की देखभाल, बिस्तर पर रहने वाले मरीज़।",
    },
    "gp_teleconsult": {
        "en": "A general doctor talks to you on a phone or video call for mild, common problems.",
        "hi": "सामान्य डॉक्टर फ़ोन या वीडियो कॉल पर हल्की, आम समस्याओं के लिए बात करेंगे।",
    },
    "specialist_referral": {
        "en": "An appointment with a specialist doctor for long-standing or specific problems.",
        "hi": "लंबे समय से चल रही या खास समस्या के लिए विशेषज्ञ डॉक्टर से मिलना।",
    },
    "emergency_referral": {
        "en": "Needs emergency help now. Call 112 or ambulance 108.",
        "hi": "अभी आपातकालीन मदद चाहिए। 112 या एम्बुलेंस 108 पर कॉल करें।",
    },
}
URGENCY = {
    "routine": {"en": "Can wait a few days.", "hi": "कुछ दिन रुक सकते हैं।"},
    "same_day": {"en": "Should be seen today.", "hi": "आज ही दिखाना चाहिए।"},
    "immediate": {"en": "Needs help right now.", "hi": "अभी तुरंत मदद चाहिए।"},
}
RED_FLAGS = [
    ("chest_pain", "Chest pain or pressure", "सीने में दर्द या दबाव"),
    ("severe_breathing_difficulty", "Severe difficulty breathing", "साँस लेने में गंभीर तकलीफ"),
    ("blue_lips", "Blue lips or face", "होंठ या चेहरा नीला पड़ना"),
    ("unconscious", "Unconscious or not responding", "बेहोश या जवाब नहीं दे रहे"),
    ("seizure", "Seizure / fit", "दौरा पड़ना"),
    ("stroke_signs", "Face drooping, slurred speech or one-sided weakness", "चेहरा टेढ़ा, बोली लड़खड़ाना या एक तरफ कमज़ोरी"),
    ("heavy_bleeding", "Heavy bleeding", "बहुत ज़्यादा खून बहना"),
    ("severe_allergic_reaction", "Swelling of face or throat / severe allergy", "चेहरे या गले में सूजन / गंभीर एलर्जी"),
    ("suicidal_intent", "Thoughts of suicide or self-harm", "आत्महत्या या खुद को नुकसान पहुँचाने के विचार"),
    ("poisoning_overdose", "Poisoning or overdose", "ज़हर या दवा की ज़्यादा खुराक"),
    ("severe_head_injury", "Serious head injury", "सिर में गंभीर चोट"),
    ("fever_stiff_neck_confusion", "High fever with stiff neck or confusion", "तेज़ बुखार के साथ गर्दन में अकड़न या भ्रम"),
    ("infant_danger_signs", "Infant with very high fever or not feeding", "शिशु को बहुत तेज़ बुखार या दूध न पीना"),
    ("pregnancy_emergency", "Pregnancy with bleeding or severe pain", "गर्भावस्था में खून आना या तेज़ दर्द"),
    ("severe_burns", "Severe burns", "गंभीर रूप से जलना"),
]

# --- who / duration fillers ------------------------------------------------
EN_WHO = {
    "elder": [("My father", "has"), ("My mother", "has"), ("My grandmother", "has"),
              ("My grandfather", "has"), ("My 75 year old father", "has"), ("My old mother", "has")],
    "adult": [("I", "have"), ("My wife", "has"), ("My husband", "has"), ("My brother", "has"), ("My sister", "has")],
    "child": [("My son", "has"), ("My daughter", "has"), ("My 6 year old", "has"), ("My child", "has")],
}
HG_W = {
    "elder": ["Papa ko", "Mummy ko", "Dadi ko", "Dada ji ko", "Nani ko", "Nana ji ko"],
    "adult": ["Mujhe", "Meri wife ko", "Mere husband ko", "Bhai ko", "Didi ko"],
    "child": ["Bete ko", "Beti ko", "Mere 6 saal ke bete ko", "Bachche ko"],
}
HG_N = {
    "elder": ["Papa", "Mummy", "Dadi", "Dada ji", "Nani", "Nana ji"],
    "adult": ["Meri wife", "Mere husband", "Bhai", "Didi", "Mera dost"],
    "child": ["Beta", "Beti", "Mera 6 saal ka beta", "Bachcha"],
}
HI_W = {
    "elder": ["पापा को", "मम्मी को", "दादी को", "दादाजी को", "नानी को"],
    "adult": ["मुझे", "मेरी पत्नी को", "मेरे पति को", "भाई को", "दीदी को"],
    "child": ["बेटे को", "बेटी को", "मेरे छह साल के बेटे को", "बच्चे को"],
}
HI_N = {
    "elder": ["पापा", "मम्मी", "दादी", "दादाजी", "नानी"],
    "adult": ["मेरी पत्नी", "मेरे पति", "भाई", "दीदी"],
    "child": ["बेटा", "बेटी", "मेरा छह साल का बेटा", "बच्चा"],
}
DUR = {
    "acute": {"en": ["since yesterday", "for 2 days", "for 3 days", "since this morning"],
              "hg": ["kal se", "do din se", "2 din se", "teen din se", "subah se"],
              "hi": ["कल से", "दो दिन से", "तीन दिन से", "सुबह से"]},
    "week": {"en": ["for a week", "for 5 days", "for 10 days"],
             "hg": ["ek hafte se", "5 din se", "10 din se", "hafte bhar se"],
             "hi": ["एक हफ्ते से", "पाँच दिन से", "दस दिन से"]},
    "chronic": {"en": ["for 3 months", "for 6 months", "for a year", "for many months"],
                "hg": ["3 mahine se", "6 mahine se", "ek saal se", "kai mahino se"],
                "hi": ["तीन महीने से", "छह महीने से", "एक साल से", "कई महीनों से"]},
    "hours": {"en": ["since this morning", "for a few hours", "today"],
              "hg": ["subah se", "kuch ghante se", "aaj se"],
              "hi": ["सुबह से", "कुछ घंटों से", "आज से"]},
    "now": {"en": ["just now", "for the last 10 minutes", "suddenly"],
            "hg": ["abhi abhi", "10 minute se", "achanak"],
            "hi": ["अभी अभी", "दस मिनट से", "अचानक"]},
}


def S(ct, urg, who, dur, en, hg, hi):
    return dict(care_type=ct, urgency=urg, who=who, dur=dur, en=en, hg=hg, hi=hi)


GP, PM, NU, SP, EM = ("gp_teleconsult", "paramedic_home_visit", "nurse_home_visit",
                      "specialist_referral", "emergency_referral")
SCENARIOS = [
    # ---------------- GP teleconsult ----------------
    S(GP, "routine", "any", "acute",
      ["{S} {has} a runny nose and sneezing {D}", "{S} {has} had a cold {D}, nothing else"],
      ["{W} {D} zukaam aur cheenk aa rahi hai", "{W} {D} sardi zukaam hai bas"],
      ["{W} {D} जुकाम और छींक आ रही है"]),
    S(GP, "same_day", "adult", "acute",
      ["{S} {has} had mild fever {D}, eating and drinking normally"],
      ["{W} {D} halka bukhar hai, khana peena theek hai"],
      ["{W} {D} हल्का बुखार है, खाना पीना ठीक है"]),
    S(GP, "same_day", "adult", "acute",
      ["{S} {has} fever and cough {D}, no breathing difficulty", "Fever and cough {D}, breathing is fine"],
      ["{W} {D} bukhar aur khansi hai, saans ki dikkat nahi hai", "{W} {D} bukhar khansi hai par saans theek hai"],
      ["{W} {D} बुखार और खांसी है, साँस की दिक्कत नहीं है"]),
    S(GP, "routine", "adult", "week",
      ["{S} {has} acidity and burning after meals {D}"],
      ["{W} {D} khane ke baad acidity aur jalan ho rahi hai"],
      ["{W} {D} खाने के बाद एसिडिटी और जलन हो रही है"]),
    S(GP, "routine", "any", "acute",
      ["{S} {has} a mild headache {D}"],
      ["{W} {D} halka sar dard hai"],
      ["{W} {D} हल्का सिर दर्द है"]),
    S(GP, "same_day", "any", "acute",
      ["{S} {has} a sore throat and mild cough {D}"],
      ["{W} {D} gale mein kharash aur thodi khansi hai"],
      ["{W} {D} गले में खराश और थोड़ी खांसी है"]),
    S(GP, "same_day", "adult", "acute",
      ["{S} {has} had loose motions {D} but is drinking fluids"],
      ["{W} {D} dast ho rahe hain par paani pee rahe hain"],
      ["{W} {D} दस्त हो रहे हैं पर पानी पी रहे हैं"]),
    S(GP, "routine", "any", "acute",
      ["{S} {has} an itchy rash on the arm {D}"],
      ["{W} {D} haath par khujli wale daane hain"],
      ["{W} {D} हाथ पर खुजली वाले दाने हैं"]),
    S(GP, "routine", "none", None,
      ["I want to discuss my blood test report with a doctor", "Need a doctor to explain my test results"],
      ["Mujhe apni blood report doctor ko dikhani hai", "report aayi hai, doctor se baat karni hai"],
      ["मुझे अपनी खून की जाँच रिपोर्ट डॉक्टर को दिखानी है"]),
    S(GP, "same_day", "child", "acute",
      ["{S} {has} a mild fever {D} and is playing normally"],
      ["{W} {D} halka bukhar hai, khel raha hai theek se"],
      ["{W} {D} हल्का बुखार है, ठीक से खेल रहा है"]),
    S(GP, "routine", "adult", "week",
      ["{S} {has} been feeling weak and tired {D}", "Not feeling well {D}, just tired"],
      ["{W} {D} kamzori aur thakaan lag rahi hai", "{W} {D} tabiyat theek nahi lag rahi"],
      ["{W} {D} कमज़ोरी और थकान लग रही है", "{W} {D} तबीयत ठीक नहीं लग रही"]),
    S(GP, "routine", "adult", "acute",
      ["{S} {has} gas and bloating {D}, no chest pain"],
      ["{W} {D} gas aur pet phoolna hai, seene mein dard nahi hai"],
      ["{W} {D} गैस और पेट फूलना है, सीने में दर्द नहीं है"]),
    S(GP, "routine", "adult", "acute",
      ["{S} {has} mild back pain {D} after lifting a bag"],
      ["{W} {D} bag uthane ke baad kamar mein halka dard hai"],
      ["{W} {D} बैग उठाने के बाद कमर में हल्का दर्द है"]),
    # ---------------- Paramedic home visit ----------------
    S(PM, "same_day", "elder", "acute",
      ["{S} {has} had fever and cough {D}", "{S} {has} fever with cough {D} and feels weak"],
      ["{W} {D} bukhar hai aur khansi bhi", "{W} {D} bukhar aur khansi hai, kamzori bhi hai"],
      ["{W} {D} बुखार है और खांसी भी"]),
    S(PM, "same_day", "elder", "acute",
      ["{S} slipped in the bathroom {D}, has knee pain and a bruise but is talking normally"],
      ["{N} {D} bathroom mein fisal gaye, ghutne mein chot aur dard hai par baat theek se kar rahe hain"],
      ["{N} {D} बाथरूम में फिसल गए, घुटने में चोट और दर्द है पर ठीक से बात कर रहे हैं"]),
    S(PM, "routine", "elder", None,
      ["{S} cannot travel, need a BP and sugar check at home"],
      ["{N} bahar nahi ja sakte, ghar par BP aur sugar check karwana hai"],
      ["{N} बाहर नहीं जा सकते, घर पर बीपी और शुगर जाँच करवानी है"]),
    S(PM, "same_day", "any", "acute",
      ["{S} got a small cut on the hand {D}, needs cleaning and dressing"],
      ["{W} {D} haath par chhota sa cut lag gaya, dressing karwani hai"],
      ["{W} {D} हाथ पर छोटा सा कट लग गया, पट्टी करवानी है"]),
    S(PM, "routine", "elder", None,
      ["Need a blood sample collected at home, {S} cannot go to the lab"],
      ["{N} ka ghar par blood sample lena hai, lab nahi ja sakte"],
      ["{N} का घर पर खून का सैंपल लेना है, लैब नहीं जा सकते"]),
    S(PM, "same_day", "elder", "acute",
      ["{S} {has} fever and vomited twice {D}, feeling weak"],
      ["{W} {D} bukhar hai aur do baar ulti hui, kamzori hai"],
      ["{W} {D} बुखार है और दो बार उल्टी हुई, कमज़ोरी है"]),
    S(PM, "same_day", "elder", "acute",
      ["{S} {has} had loose motions {D} and feels dizzy when standing"],
      ["{W} {D} dast ho rahe hain aur khade hone par chakkar aata hai"],
      ["{W} {D} दस्त हो रहे हैं और खड़े होने पर चक्कर आता है"]),
    S(PM, "same_day", "any", "acute",
      ["{S} twisted an ankle {D}, it is swollen and walking is hard"],
      ["{W} {D} pair mein moch aa gayi, sujan hai aur chalne mein dikkat hai"],
      ["{W} {D} पैर में मोच आ गई, सूजन है और चलने में दिक्कत है"]),
    # ---------------- Nurse home visit ----------------
    S(NU, "routine", "any", None,
      ["{S} had surgery last week and needs wound dressing at home"],
      ["{N} ka pichle hafte operation hua tha, ghar par dressing karwani hai"],
      ["{N} का पिछले हफ्ते ऑपरेशन हुआ था, घर पर ड्रेसिंग करवानी है"]),
    S(NU, "routine", "any", None,
      ["{S} needs the injections the doctor advised, given at home every day"],
      ["{W} doctor ne injection bataye hain, roz ghar par lagwane hain"],
      ["{W} डॉक्टर ने इंजेक्शन बताए हैं, रोज़ घर पर लगवाने हैं"]),
    S(NU, "routine", "elder", None,
      ["{S} {has} a urine catheter that needs to be changed"],
      ["{N} ka catheter badalna hai, ghar par nurse chahiye"],
      ["{N} का कैथेटर बदलना है, घर पर नर्स चाहिए"]),
    S(NU, "same_day", "elder", None,
      ["{S} is bedridden and has a bedsore that is getting worse"],
      ["{N} bistar par hain aur peeth par ghaav badh raha hai"],
      ["{N} बिस्तर पर हैं और पीठ पर घाव बढ़ रहा है"]),
    S(NU, "same_day", "elder", None,
      ["The doctor advised an IV drip at home for {S}"],
      ["Doctor ne {N} ko ghar par drip lagwane ko kaha hai"],
      ["डॉक्टर ने {N} को घर पर ड्रिप लगवाने को कहा है"]),
    S(NU, "routine", "none", None,
      ["Need help with newborn baby care and the mother's stitches after delivery"],
      ["Delivery ke baad bachche ki dekhbhal aur taankon ki dressing ke liye nurse chahiye"],
      ["डिलीवरी के बाद बच्चे की देखभाल और टांकों की ड्रेसिंग के लिए नर्स चाहिए"]),
    S(NU, "routine", "elder", None,
      ["{S} {has} a feeding tube and needs daily nursing care at home"],
      ["{N} ko feeding tube lagi hai, roz ghar par nurse ki dekhbhal chahiye"],
      ["{N} को फीडिंग ट्यूब लगी है, रोज़ घर पर नर्स की देखभाल चाहिए"]),
    S(NU, "same_day", "elder", "week",
      ["{S} {has} diabetes and a foot wound {D} that needs regular dressing"],
      ["{W} sugar hai aur {D} pair mein ghaav hai, roz dressing chahiye"],
      ["{W} शुगर है और {D} पैर में घाव है, रोज़ ड्रेसिंग चाहिए"]),
    # ---------------- Specialist referral ----------------
    S(SP, "routine", "elder", "chronic",
      ["{S} {has} had knee pain {D}, worse on the stairs"],
      ["{W} {D} ghutno mein dard hai, seedhi chadhne mein zyada"],
      ["{W} {D} घुटनों में दर्द है, सीढ़ी चढ़ने में ज़्यादा"]),
    S(SP, "routine", "any", "chronic",
      ["{S} {has} had white patches on the skin {D} that keep spreading"],
      ["{W} {D} skin par safed daag hain jo badh rahe hain"],
      ["{W} {D} त्वचा पर सफेद दाग हैं जो बढ़ रहे हैं"]),
    S(SP, "routine", "elder", "chronic",
      ["{S} {has} had blurry vision {D}, difficulty reading"],
      ["{W} {D} dhundhla dikh raha hai, padhne mein dikkat hai"],
      ["{W} {D} धुंधला दिख रहा है, पढ़ने में दिक्कत है"]),
    S(SP, "routine", "elder", "chronic",
      ["{S} {has} had trouble hearing {D}"],
      ["{W} {D} kam sunai de raha hai"],
      ["{W} {D} कम सुनाई दे रहा है"]),
    S(SP, "same_day", "adult", "week",
      ["{S} {has} had sugar readings above 300 {D} even with regular medicines"],
      ["{W} {D} sugar 300 se upar aa rahi hai, dawai le rahe hain phir bhi"],
      ["{W} {D} शुगर 300 से ऊपर आ रही है, दवा लेने पर भी"]),
    S(SP, "routine", "none", None,
      ["My wife is 5 months pregnant and needs a routine checkup"],
      ["Meri wife 5 mahine pregnant hai, regular checkup karwana hai"],
      ["मेरी पत्नी पाँच महीने की गर्भवती है, नियमित जाँच करवानी है"]),
    S(SP, "routine", "none", None,
      ["My 3 year old is not speaking any words yet"],
      ["Mera 3 saal ka beta abhi tak bolta nahi hai"],
      ["मेरा तीन साल का बेटा अभी तक बोलता नहीं है"]),
    S(SP, "routine", "adult", "chronic",
      ["{S} {has} been feeling very low and not sleeping well {D}"],
      ["{W} {D} mann bahut udaas rehta hai aur neend nahi aati"],
      ["{W} {D} मन बहुत उदास रहता है और नींद नहीं आती"]),
    S(SP, "same_day", "adult", "week",
      ["{S} {has} had episodes of fast heartbeat {D}, no chest pain"],
      ["{W} {D} dil ki dhadkan tez ho jaati hai, seene mein dard nahi hai"],
      ["{W} {D} दिल की धड़कन तेज़ हो जाती है, सीने में दर्द नहीं है"]),
    S(SP, "routine", "adult", "chronic",
      ["{S} {has} had repeated severe one-sided headaches {D}"],
      ["{W} {D} baar baar aadhe sar mein tez dard hota hai"],
      ["{W} {D} बार बार आधे सिर में तेज़ दर्द होता है"]),
    S(SP, "same_day", "none", "week",
      ["My wife noticed a painless lump in the breast {D}", "I noticed a painless breast lump {D}"],
      ["Meri wife ko {D} breast mein ek gaanth mehsoos ho rahi hai", "Didi ko {D} breast mein gaanth hai"],
      ["मेरी पत्नी को {D} स्तन में एक गांठ महसूस हो रही है"]),
    S(SP, "routine", "none", None,
      ["The doctor said my thyroid is high and I should see a specialist"],
      ["Doctor ne bola thyroid badha hua hai, specialist ko dikhana hai"],
      ["डॉक्टर ने कहा थायरॉइड बढ़ा हुआ है, विशेषज्ञ को दिखाना है"]),
    # ---------------- Emergency ----------------
    S(EM, "immediate", "elder", "now",
      ["{S} {has} severe chest pain and is sweating {D}", "{S} {has} heavy pressure in the chest {D}"],
      ["{W} {D} seene mein tez dard ho raha hai aur paseena aa raha hai", "{W} {D} chest mein bahut dard hai"],
      ["{W} {D} सीने में तेज़ दर्द हो रहा है और पसीना आ रहा है"]),
    S(EM, "immediate", "any", None,
      ["{S} cannot breathe properly and the lips are turning blue"],
      ["{N} ko saans nahi aa rahi, hont neele pad rahe hain"],
      ["{N} को साँस नहीं आ रही, होंठ नीले पड़ रहे हैं"]),
    S(EM, "immediate", "elder", None,
      ["{S} fainted and is not responding", "{S} is unconscious and not waking up"],
      ["{N} behosh ho gaye hain, jawab nahi de rahe", "{N} hosh mein nahi hain"],
      ["{N} बेहोश हो गए हैं, जवाब नहीं दे रहे"]),
    S(EM, "immediate", "any", "now",
      ["{S} is having a fit {D}, the whole body is shaking"],
      ["{W} {D} daura pad raha hai, haath pair kaanp rahe hain"],
      ["{W} {D} दौरा पड़ रहा है, हाथ पैर काँप रहे हैं"]),
    S(EM, "immediate", "elder", None,
      ["{S} suddenly has slurred speech and one side of the face is drooping"],
      ["{N} ki awaaz achanak ladkhada rahi hai aur chehra ek taraf tedha ho gaya"],
      ["{N} की आवाज़ अचानक लड़खड़ा रही है और चेहरा एक तरफ टेढ़ा हो गया है"]),
    S(EM, "immediate", "any", None,
      ["{S} had a road accident and is bleeding heavily"],
      ["{N} ka accident ho gaya, bahut khoon beh raha hai"],
      ["{N} का एक्सीडेंट हो गया, बहुत खून बह रहा है"]),
    S(EM, "immediate", "any", None,
      ["After eating peanuts, the face and throat are swelling and it is hard to breathe"],
      ["{N} ka khana khane ke baad chehra aur gala sooj gaya, saans lene mein dikkat hai"],
      ["{N} का खाना खाने के बाद चेहरा और गला सूज गया, साँस लेने में दिक्कत है"]),
    S(EM, "immediate", "child", None,
      ["{S} accidentally swallowed rat poison"],
      ["{N} ne galti se chuhe maarne ki dawai pee li"],
      ["{N} ने गलती से चूहे मारने की दवा पी ली"]),
    S(EM, "immediate", "none", None,
      ["I don't want to live anymore, I am thinking of ending my life"],
      ["Mujhe ab jeena nahi hai, khud ko khatam karne ka mann kar raha hai"],
      ["मुझे अब जीना नहीं है, खुद को खत्म करने का मन कर रहा है"]),
    S(EM, "immediate", "none", None,
      ["My 2 month old baby has a high fever and is not feeding"],
      ["Mere 2 mahine ke bachche ko tez bukhar hai aur doodh nahi pee raha"],
      ["मेरे दो महीने के बच्चे को तेज़ बुखार है और दूध नहीं पी रहा"]),
    S(EM, "immediate", "none", None,
      ["My wife is 7 months pregnant and is bleeding with severe pain"],
      ["Meri wife 7 mahine pregnant hai aur bleeding ho rahi hai, tez dard hai"],
      ["मेरी पत्नी सात महीने की गर्भवती है और खून आ रहा है, तेज़ दर्द है"]),
    S(EM, "immediate", "elder", None,
      ["{S} fell and hit the head, now vomiting and confused"],
      ["{N} gir gaye aur sar par chot lagi, ab ulti ho rahi hai aur confuse hain"],
      ["{N} गिर गए और सिर पर चोट लगी, अब उल्टी हो रही है और भ्रमित हैं"]),
    S(EM, "immediate", "any", "acute",
      ["{S} {has} had a high fever {D} with a stiff neck and confusion"],
      ["{W} {D} tez bukhar hai, gardan akad gayi hai aur behki behki baatein kar rahe hain"],
      ["{W} {D} तेज़ बुखार है, गर्दन अकड़ गई है और बहकी बहकी बातें कर रहे हैं"]),
    S(EM, "immediate", "any", None,
      ["{S} got badly burned by boiling oil over a large part of the body"],
      ["{N} garam tel se bahut buri tarah jal gaye hain"],
      ["{N} गरम तेल से बहुत बुरी तरह जल गए हैं"]),
    S(EM, "immediate", "elder", "now",
      ["{S} is extremely breathless {D} and cannot even speak"],
      ["{W} {D} saans bahut phool rahi hai, bol bhi nahi pa rahe"],
      ["{W} {D} साँस बहुत फूल रही है, बोल भी नहीं पा रहे"]),
]

# v2: wider coverage (more complaint types, vocabulary and phrasing styles)
SCENARIOS += [
    # ---------------- GP teleconsult ----------------
    S(GP, "same_day", "child", "acute",
      ["{S} {has} ear pain {D} and a slight temperature", "{S} keeps pulling at the ear and crying {D}"],
      ["{W} {D} kaan mein dard hai aur halka bukhar", "{W} {D} kaan dard ho raha hai"],
      ["{W} {D} कान में दर्द है और हल्का बुखार है"]),
    S(GP, "same_day", "any", "acute",
      ["{S} {has} burning while passing urine {D}", "There is a burning feeling when urinating {D}"],
      ["{W} {D} peshab mein jalan ho rahi hai", "{W} {D} urine karte waqt jalan hoti hai"],
      ["{W} {D} पेशाब में जलन हो रही है"]),
    S(GP, "same_day", "adult", "acute",
      ["{S} {has} body ache and fever {D}, otherwise fine", "Temperature of 100 with body pain {D}"],
      ["{W} {D} badan dard aur bukhar hai, baaki sab theek", "{W} {D} 100 bukhar aur badan toot raha hai"],
      ["{W} {D} बदन दर्द और बुखार है, बाकी सब ठीक है"]),
    S(GP, "same_day", "any", "hours",
      ["{S} {has} a red, watery eye {D}", "Something went into the eye {D}, it is red and itchy"],
      ["{W} {D} aankh laal hai aur paani aa raha hai", "{W} {D} aankh mein kuch chala gaya, jalan ho rahi hai"],
      ["{W} {D} आँख लाल है और पानी आ रहा है"]),
    S(GP, "routine", "adult", "acute",
      ["{S} {has} painful mouth ulcers {D}", "{S} {has} small sores inside the mouth {D}"],
      ["{W} {D} muh mein chhale hain", "{W} {D} munh mein chhaale ho gaye hain, khane mein dard"],
      ["{W} {D} मुँह में छाले हैं"]),
    S(GP, "routine", "none", None,
      ["Can a doctor check whether my child's vaccinations are up to date?", "I want to ask a doctor about a healthy diet for my father",
       "I need a doctor to review my regular medicines list", "Is there a doctor I can talk to on the phone?"],
      ["Bachche ke tike ke baare mein doctor se poochna hai", "Papa ki diet ke liye doctor se salaah chahiye", "doctor se phone par baat karni hai"],
      ["बच्चे के टीकों के बारे में डॉक्टर से पूछना है", "डॉक्टर से फ़ोन पर बात करनी है"]),
    S(GP, "routine", "adult", "week",
      ["{S} {has} constipation {D} but is eating normally"],
      ["{W} {D} kabz hai, pet saaf nahi hota"],
      ["{W} {D} कब्ज़ है, पेट साफ नहीं होता"]),
    S(GP, "routine", "any", "hours",
      ["{S} got a mosquito or insect bite {D}, small itchy bump only", "A bee stung the hand {D}, only small swelling at that spot"],
      ["{W} {D} keede ne kaat liya, bas thodi khujli aur chhoti sujan", "madhumakkhi ne kaata {D}, bas wahi thoda sooja hai"],
      ["{W} {D} कीड़े ने काटा, बस थोड़ी खुजली है"]),
    S(GP, "same_day", "adult", "week",
      ["{S} {has} had a dry cough {D}, no fever and breathing is fine"],
      ["{W} {D} sookhi khansi hai, bukhar nahi, saans theek hai"],
      ["{W} {D} सूखी खांसी है, बुखार नहीं है, साँस ठीक है"]),
    S(GP, "routine", "adult", "acute",
      ["{S} {has} a headache with pain behind the eyes {D}, no fever"],
      ["{W} {D} sar dard aur aankhon ke peeche dard hai, bukhar nahi"],
      ["{W} {D} सिर दर्द और आँखों के पीछे दर्द है, बुखार नहीं है"]),
    # ---------------- Paramedic home visit ----------------
    S(PM, "same_day", "elder", None,
      ["{S}'s BP reading is very high today, 180 over 110, with a heavy head", "BP machine shows 175/105 for {S}, feeling uneasy"],
      ["{N} ka BP aaj bahut high aa raha hai, sar bhaari hai", "{N} ka BP 180/110 aa raha hai"],
      ["{N} का बीपी आज बहुत ज़्यादा आ रहा है, सिर भारी है"]),
    S(PM, "same_day", "elder", "acute",
      ["{S} {has} not passed stool {D} and the stomach is bloated"],
      ["{N} ko {D} latrine nahi hui, pet phoola hua hai"],
      ["{N} को {D} शौच नहीं हुआ, पेट फूला हुआ है"]),
    S(PM, "same_day", "elder", "acute",
      ["{S} feels dizzy when getting up from bed {D}", "{S} {has} been light-headed on standing {D}"],
      ["{W} {D} bistar se uthne par chakkar aata hai"],
      ["{W} {D} बिस्तर से उठने पर चक्कर आता है"]),
    S(PM, "same_day", "elder", "acute",
      ["{S} {has} high temperature {D} and is too weak to get out of bed", "{S} {has} been running a temperature of 102 {D}, very weak"],
      ["{W} {D} tez bukhar hai aur bahut kamzori, bistar se uth nahi pa rahe"],
      ["{W} {D} तेज़ बुखार है और बहुत कमज़ोरी है, बिस्तर से उठ नहीं पा रहे"]),
    S(PM, "routine", "elder", None,
      ["{S} is bedridden, need someone to check BP and sugar at home every week", "Need regular home checks of vitals for {S}"],
      ["{N} bistar par hain, har hafte ghar par BP sugar check karwana hai"],
      ["{N} बिस्तर पर हैं, हर हफ्ते घर पर बीपी शुगर जाँच करवानी है"]),
    S(PM, "same_day", "elder", "hours",
      ["{S} fell {D}, the wrist is swollen and painful, talking normally", "{S} slipped {D}, ankle hurts, fully alert"],
      ["{N} {D} gir gaye, kalai sooj gayi hai aur dard hai, baat theek kar rahe hain"],
      ["{N} {D} गिर गए, कलाई सूज गई है और दर्द है, होश में हैं"]),
    S(PM, "same_day", "elder", "acute",
      ["{S} {has} been coughing a lot {D} with a temperature of 101"],
      ["{W} {D} bahut khansi aur 101 bukhar hai"],
      ["{W} {D} बहुत खांसी और 101 बुखार है"]),
    # ---------------- Nurse home visit ----------------
    S(NU, "routine", "elder", None,
      ["{S} needs daily insulin injections at home and cannot do it alone"],
      ["{N} ko roz insulin ka injection lagwana hai, khud nahi laga pate"],
      ["{N} को रोज़ इंसुलिन का इंजेक्शन लगवाना है, खुद नहीं लगा पाते"]),
    S(NU, "same_day", "elder", "hours",
      ["{S}'s urine catheter seems blocked {D}, nothing is draining", "The catheter bag has stayed empty {D}"],
      ["{N} ka catheter {D} band lag raha hai, urine nahi aa rahi"],
      ["{N} का कैथेटर {D} बंद लग रहा है, पेशाब नहीं आ रहा"]),
    S(NU, "routine", "none", None,
      ["My wife had a c-section last week, the stitches need dressing at home",
       "After the knee replacement surgery, mother needs dressing and exercises at home"],
      ["Wife ka c-section hua hai, taankon ki dressing ghar par chahiye", "Mummy ke ghutne ka operation hua hai, ghar par dressing aur exercise chahiye"],
      ["पत्नी का सी-सेक्शन हुआ है, टांकों की ड्रेसिंग घर पर चाहिए", "माँ के घुटने का ऑपरेशन हुआ है, घर पर ड्रेसिंग चाहिए"]),
    S(NU, "routine", "elder", None,
      ["{S} came home after a stroke last month and needs daily nursing care",
       "{S} is bedridden and needs help with bathing, turning and hygiene"],
      ["{N} ko pichle mahine lakwa hua tha, ab ghar par roz nursing care chahiye", "{N} bistar par hain, nahlane aur karwat dilane ke liye nurse chahiye"],
      ["{N} को पिछले महीने लकवा हुआ था, अब घर पर रोज़ देखभाल चाहिए", "{N} बिस्तर पर हैं, नहलाने और करवट दिलाने के लिए नर्स चाहिए"]),
    # ---------------- Specialist referral ----------------
    S(SP, "routine", "elder", "chronic",
      ["{S}'s hands have been trembling {D} and walking has become slow"],
      ["{N} ke haath {D} kaanpte hain aur chaal dheemi ho gayi hai"],
      ["{N} के हाथ {D} काँपते हैं और चाल धीमी हो गई है"]),
    S(SP, "routine", "adult", "chronic",
      ["{S} {has} had acne on the face {D} that does not go away"],
      ["{W} {D} chehre par pimples hain jo jaate nahi"],
      ["{W} {D} चेहरे पर मुहांसे हैं जो जाते नहीं"]),
    S(SP, "same_day", "none", "chronic",
      ["My sister has had very heavy periods {D}", "My wife's periods have been very heavy and long {D}"],
      ["Didi ko {D} periods mein bahut zyada bleeding hoti hai"],
      ["दीदी को {D} पीरियड्स में बहुत ज़्यादा खून आता है"]),
    S(SP, "routine", "adult", "chronic",
      ["{S} {has} been passing urine very often and feeling very thirsty {D}"],
      ["{W} {D} baar baar peshab aata hai aur pyaas bahut lagti hai"],
      ["{W} {D} बार बार पेशाब आता है और प्यास बहुत लगती है"]),
    S(SP, "routine", "child", "chronic",
      ["{S} cannot concentrate at school and is very irritable {D}"],
      ["{W} {D} school mein dhyaan nahi lagta, chidchida rehta hai"],
      ["{W} {D} स्कूल में ध्यान नहीं लगता, चिड़चिड़ा रहता है"]),
    S(SP, "same_day", "adult", "week",
      ["{S} {has} a painless lump in the neck {D}", "There is a swelling in the armpit {D}, not painful"],
      ["{W} {D} gardan mein gaanth hai, dard nahi"],
      ["{W} {D} गर्दन में गांठ है, दर्द नहीं है"]),
    S(SP, "same_day", "elder", "chronic",
      ["{S}'s legs have been swelling {D} and gets breathless on walking"],
      ["{N} ke pairon mein {D} sujan hai aur chalne par saans phoolti hai"],
      ["{N} के पैरों में {D} सूजन है और चलने पर साँस फूलती है"]),
    S(SP, "routine", "adult", "chronic",
      ["{S} {has} had lower back pain {D} going down one leg"],
      ["{W} {D} kamar dard hai jo pair tak jaata hai"],
      ["{W} {D} कमर दर्द है जो पैर तक जाता है"]),
    S(SP, "same_day", "any", "acute",
      ["{S} {has} a toothache with swelling of the gum {D}"],
      ["{W} {D} daant mein dard aur masoode mein sujan hai"],
      ["{W} {D} दाँत में दर्द और मसूड़े में सूजन है"]),
    S(SP, "routine", "any", "week",
      ["{S} {has} had an itchy skin rash {D} that is not going away", "{S} {has} red patches on the skin {D}, not improving"],
      ["{W} {D} skin pe rash hai jo theek nahi ho raha", "{W} {D} skin par laal daane hain, jaa nahi rahe"],
      ["{W} {D} त्वचा पर दाने हैं जो ठीक नहीं हो रहे"]),
    S(SP, "routine", "adult", "week",
      ["{S} {has} been very anxious and tense {D}, cannot sleep"],
      ["{W} {D} bahut tension aur ghabrahat rehti hai, neend nahi aati"],
      ["{W} {D} बहुत तनाव और घबराहट रहती है, नींद नहीं आती"]),
    # ---------------- Emergency ----------------
    S(EM, "immediate", "adult", None,
      ["{S} swallowed a whole strip of sleeping pills", "{S} took far too many tablets on purpose"],
      ["{N} ne bahut saari neend ki goliyan kha li hain"],
      ["{N} ने बहुत सारी नींद की गोलियाँ खा ली हैं"]),
    S(EM, "immediate", "child", None,
      ["{S} drank kerosene by mistake", "{S} drank toilet cleaner"],
      ["{N} ne galti se kerosene pee liya"],
      ["{N} ने गलती से केरोसिन पी लिया"]),
    S(EM, "immediate", "any", "now",
      ["{S} is wheezing badly and the inhaler is not helping, struggling to breathe"],
      ["{W} {D} saans lene mein bahut dikkat hai, inhaler se bhi aaram nahi"],
      ["{W} {D} साँस लेने में बहुत दिक्कत है, इनहेलर से भी आराम नहीं"]),
    S(EM, "immediate", "elder", "now",
      ["{S} suddenly cannot lift one arm and the words are coming out jumbled"],
      ["{N} {D} ek haath utha nahi pa rahe aur awaaz atak rahi hai"],
      ["{N} {D} एक हाथ उठा नहीं पा रहे और आवाज़ अटक रही है"]),
    S(EM, "immediate", "none", None,
      ["My 3 week old baby has a temperature", "Our newborn is very sleepy and not feeding"],
      ["Navjaat baby ko bukhar hai, 3 hafte ka hai", "3 hafte ke baby ne doodh pina band kar diya"],
      ["तीन हफ्ते के बच्चे को बुखार है"]),
    S(EM, "immediate", "none", None,
      ["My wife is 8 months pregnant and the baby has not moved since morning"],
      ["Wife 8 mahine pregnant hai, subah se baby hil nahi raha"],
      ["पत्नी आठ महीने की गर्भवती है, सुबह से बच्चा हिल नहीं रहा"]),
    S(EM, "immediate", "elder", "now",
      ["{S} is sweating a lot and has pain going down the left arm", "{S} {has} tightness in the chest spreading to the jaw"],
      ["{W} {D} bahut paseena aa raha hai aur baayein haath mein dard ja raha hai, seene mein bhaaripan"],
      ["{W} {D} बहुत पसीना आ रहा है और सीने में भारीपन है"]),
    S(EM, "immediate", "elder", None,
      ["{S} is very drowsy today, not eating and does not recognise us"],
      ["{N} aaj bahut sust hain, khana nahi kha rahe aur pehchaan nahi rahe"],
      ["{N} आज बहुत सुस्त हैं, खाना नहीं खा रहे और पहचान नहीं रहे"]),
    S(EM, "immediate", "child", None,
      ["{S} fell while playing and the arm looks broken and bent"],
      ["{N} khelte hue gir gaya, haath toot gaya lagta hai"],
      ["{N} खेलते हुए गिर गया, हाथ टूट गया लगता है"]),
]

CT_SHARE = {GP: 0.30, PM: 0.20, NU: 0.15, SP: 0.20, EM: 0.15}
LANG_SHARE = {"en": 0.35, "hi": 0.25, "hinglish": 0.40}

HG_VARIANTS = {
    "bukhar": ["bukhar", "bukhaar", "bukar"], "khansi": ["khansi", "khaansi", "khasi"],
    "hai": ["hai", "hai", "h", "he"], "nahi": ["nahi", "nhi", "nahin"], "saans": ["saans", "sans", "saas"],
    "dard": ["dard", "dardh"], "ulti": ["ulti", "vomit"], "seene": ["seene", "sine"],
    "bahut": ["bahut", "bohot", "bht"], "kamzori": ["kamzori", "kamjori"], "chakkar": ["chakkar", "chakar"],
    "sar": ["sar", "sir"], "tez": ["tez", "tej"], "raha": ["raha", "rha"], "rahi": ["rahi", "rhi"],
}
EN_SUFFIX = ["", "", "", ". Please help", ". What should we do?", ". Need a doctor"]
HG_SUFFIX = ["", "", "", ", kya karein?", ", please help", ", doctor chahiye"]
HI_SUFFIX = ["", "", "", "। क्या करें?", "। कृपया मदद करें", "। डॉक्टर चाहिए"]


def _who_pool(who: str) -> list[str]:
    return ["elder", "adult", "child"] if who == "any" else [who]


def render(sc: dict, lang: str, rng: random.Random) -> str:
    key = {"en": "en", "hi": "hi", "hinglish": "hg"}[lang]
    tpl = rng.choice(sc[key])
    grp = rng.choice(_who_pool(sc["who"])) if sc["who"] != "none" else "adult"
    fill: dict[str, str] = {}
    if lang == "en":
        pool = EN_WHO[grp] if "{has}" in tpl else [p for p in EN_WHO[grp] if p[0] != "I"]
        subj, has = rng.choice(pool)
        fill = {"S": subj, "has": has}
    elif lang == "hinglish":
        fill = {"W": rng.choice(HG_W[grp]), "N": rng.choice(HG_N[grp])}
    else:
        fill = {"W": rng.choice(HI_W[grp]), "N": rng.choice(HI_N[grp])}
    fill["D"] = rng.choice(DUR[sc["dur"]][key]) if sc["dur"] else ""
    text = tpl.format(**fill)
    text = " ".join(text.split()).replace(" ,", ",")
    if lang == "hinglish":
        words = [rng.choice(HG_VARIANTS[w]) if w in HG_VARIANTS and rng.random() < 0.35 else w
                 for w in text.split()]
        text = " ".join(words)
        if rng.random() < 0.5:
            text = text.lower()
        text += rng.choice(HG_SUFFIX)
    elif lang == "en":
        if text.startswith("I ") is False and rng.random() < 0.15:
            text = text.lower()
        text += rng.choice(EN_SUFFIX)
    else:
        text += rng.choice(HI_SUFFIX)
    return text[0].upper() + text[1:] if lang == "en" and text[0].islower() and rng.random() < 0.5 else text


def make_vignettes(n: int, rng: random.Random) -> list[dict]:
    by_ct: dict[str, list[dict]] = {}
    for sc in SCENARIOS:
        by_ct.setdefault(sc["care_type"], []).append(sc)
    rows, seen = [], set()
    cts, cw = list(CT_SHARE), list(CT_SHARE.values())
    langs, lw = list(LANG_SHARE), list(LANG_SHARE.values())
    attempts = 0
    while len(rows) < n and attempts < n * 50:
        attempts += 1
        ct = rng.choices(cts, cw)[0]
        sc = rng.choice(by_ct[ct])
        lang = rng.choices(langs, lw)[0]
        text = render(sc, lang, rng)
        if text in seen:
            continue
        seen.add(text)
        rows.append({"id": f"DEV_{len(rows) + 1:04d}", "text": text, "language": lang,
                     "care_type": sc["care_type"], "urgency": sc["urgency"]})
    return rows


# --- caregivers ------------------------------------------------------------
FIRST = ["Aarti", "Rohit", "Sunita", "Vikas", "Neha", "Amit", "Pooja", "Rahul", "Kavita", "Sanjay", "Meena",
         "Arjun", "Priya", "Deepak", "Anjali", "Manoj", "Ritu", "Suresh", "Nisha", "Imran", "Farah", "Gurpreet",
         "Harpreet", "Sneha", "Tarun", "Lakshmi", "Joseph", "Mary", "Abdul", "Shabnam"]
LAST = ["Sharma", "Verma", "Gupta", "Singh", "Yadav", "Khan", "Kumar", "Mehta", "Joshi", "Chauhan", "Malik",
        "Bansal", "Das", "Nair", "Thomas", "Ansari", "Kaur", "Rawat", "Mishra", "Saxena"]
ROLES = {
    "paramedic": (14, ["vitals_check", "fever_assessment", "wound_dressing", "first_aid", "sample_collection",
                       "elderly_care", "fall_assessment", "dehydration_care"]),
    "nurse": (14, ["injection", "iv_drip", "wound_care", "catheter_care", "post_op_care", "elderly_care",
                   "newborn_care", "bedsore_care", "feeding_tube_care", "diabetic_foot_care"]),
    "gp": (14, ["general_medicine", "pediatrics_basic", "teleconsult", "report_review", "elderly_care"]),
}
# 8 core specialties x3 + 4 others x2 = 32 specialists (>=3 per core specialty so every referral shows 3 options)
CORE_SPECIALTIES = ["dermatology", "orthopedics", "cardiology", "pediatrics", "ent", "gynecology", "neurology", "pulmonology"]
OTHER_SPECIALTIES = ["ophthalmology", "endocrinology", "psychiatry", "oncology"]
SPECIALTIES = CORE_SPECIALTIES + OTHER_SPECIALTIES
SPECIALTY_QUAL = {
    "dermatology": "MBBS, MD (Dermatology)", "orthopedics": "MBBS, MS (Orthopaedics)",
    "cardiology": "MBBS, MD, DM (Cardiology)", "pediatrics": "MBBS, MD (Paediatrics)", "ent": "MBBS, MS (ENT)",
    "gynecology": "MBBS, MS (Obstetrics & Gynaecology)", "neurology": "MBBS, MD, DM (Neurology)",
    "pulmonology": "MBBS, MD (Pulmonary Medicine)", "ophthalmology": "MBBS, MS (Ophthalmology)",
    "endocrinology": "MBBS, MD, DM (Endocrinology)", "psychiatry": "MBBS, MD (Psychiatry)",
    "oncology": "MBBS, MD, DM (Medical Oncology)",
}
SPECIALTY_SKILLS = {
    "dermatology": ["skin_conditions", "rash_assessment"], "orthopedics": ["joint_pain", "back_pain", "fracture_follow_up"],
    "cardiology": ["heart_checkup", "bp_management"], "pediatrics": ["child_health", "growth_development"],
    "ent": ["ear_nose_throat", "hearing_assessment"], "gynecology": ["pregnancy_care", "womens_health"],
    "neurology": ["headache_clinic", "nerve_conditions"], "pulmonology": ["breathing_conditions", "chronic_cough"],
    "ophthalmology": ["eye_checkup", "vision_care"], "endocrinology": ["diabetes_care", "thyroid_care"],
    "psychiatry": ["mental_health", "sleep_problems"], "oncology": ["lump_assessment", "cancer_screening"],
}
QUAL = {"paramedic": ["EMT-Basic", "EMT-Advanced", "Diploma in Paramedical Science"],
        "nurse": ["GNM", "BSc Nursing", "Post Basic BSc Nursing"],
        "gp": ["MBBS", "MBBS, MD (General Medicine)", "MBBS, DNB (Family Medicine)"]}
EXTRA_LANGS = ["pa", "ur", "bn", "ta", "ml"]


def _localities() -> list[dict]:
    return json.loads((ROOT / "config" / "localities.json").read_text(encoding="utf-8"))["localities"]


def _slots(rng: random.Random, base: date) -> list[str]:
    """Slots over today + 2 days; today always has some late-day slots so same-day demos work."""
    out = []
    for d in range(3):
        day = base + timedelta(days=d)
        hours = set(rng.sample(range(8, 21), k=rng.randint(2, 5)))
        if d == 0:
            hours |= set(rng.sample(range(15, 22), k=2))
        for h in sorted(hours):
            out.append(datetime(day.year, day.month, day.day, h, rng.choice([0, 30])).isoformat() + "+05:30")
    return out


def make_caregivers(rng: random.Random, base: date) -> list[dict]:
    locs = _localities()
    plan = [(r, None) for r, (n, _) in ROLES.items() for _ in range(n)] + [("specialist", s) for s in CORE_SPECIALTIES for _ in range(3)]         + [("specialist", s) for s in OTHER_SPECIALTIES for _ in range(2)]
    out = []
    for i, (role, spec) in enumerate(plan, start=1):
        loc = locs[(i * 7) % len(locs)]  # spread every role across all localities
        if role == "specialist":
            sk = [spec] + SPECIALTY_SKILLS[spec]
            qual = SPECIALTY_QUAL[spec]
            modes = rng.choice([["clinic", "teleconsult"], ["clinic"], ["teleconsult", "clinic"]])
            years = rng.randint(6, 28)
        else:
            skills = ROLES[role][1]
            sk = rng.sample(skills, k=rng.randint(3, min(5, len(skills))))
            qual = rng.choice(QUAL[role])
            modes = ["teleconsult"] if role == "gp" and rng.random() < 0.7 else (["teleconsult", "clinic"] if role == "gp" else ["home_visit"])
            years = rng.randint(2, 22)
        langs = rng.choice([["hi", "en"], ["hi", "en"], ["hi"], ["en"], ["hi", "en"]])
        if rng.random() < 0.25:
            langs = langs + [rng.choice(EXTRA_LANGS)]
        prefix = "Dr. " if role in ("gp", "specialist") else ""
        out.append({
            "caregiver_id": f"CG_{i:03d}",
            "name": f"{prefix}{rng.choice(FIRST)} {rng.choice(LAST)}",
            "role": role,
            "specialty": spec,
            "skills": sk,
            "qualification": qual,
            "years_experience": years,
            "lat": round(loc["lat"] + rng.uniform(-0.012, 0.012), 5),
            "lng": round(loc["lng"] + rng.uniform(-0.012, 0.012), 5),
            "locality": f"{loc['name']}, {loc['city']}",
            "consultation_modes": modes,
            "availability_slots": _slots(rng, base),
            "languages": langs,
            "rating": round(rng.uniform(3.6, 5.0), 1),
        })
    return out


def make_taxonomy() -> dict:
    return {
        "_note": "Synthetic, self-generated dev taxonomy. Replace with the official taxonomy when released.",
        "care_types": [{"id": k, "definition_en": v["en"], "definition_hi": v["hi"]} for k, v in CARE_TYPES.items()],
        "urgency_levels": [{"id": k, "definition_en": v["en"], "definition_hi": v["hi"]} for k, v in URGENCY.items()],
        "red_flags": [{"id": a, "label_en": b, "label_hi": c} for a, b, c in RED_FLAGS],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--base-date", default=date.today().isoformat(),
                    help="first day of caregiver availability (YYYY-MM-DD)")
    ap.add_argument("--out", default=str(ROOT / "dev_data"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)

    (out / "taxonomy.json").write_text(json.dumps(make_taxonomy(), ensure_ascii=False, indent=2), encoding="utf-8")
    rows = make_vignettes(a.n, rng)
    with open(out / "vignettes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "text", "language", "care_type", "urgency"])
        w.writeheader()
        w.writerows(rows)
    cgs = make_caregivers(random.Random(a.seed + 1), date.fromisoformat(a.base_date))
    (out / "caregivers.json").write_text(json.dumps(cgs, ensure_ascii=False, indent=2), encoding="utf-8")

    from collections import Counter
    print(f"vignettes={len(rows)} caregivers={len(cgs)}")
    for col in ("care_type", "urgency", "language"):
        print(col, dict(Counter(r[col] for r in rows)))


if __name__ == "__main__":
    main()
