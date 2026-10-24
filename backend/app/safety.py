"""Deterministic red-flag engine (English, Hindi Devanagari, Hinglish).

Safety is scored on emergency recall and under-triage is penalised heavily, so this engine is
deliberately sensitive. It is run on the raw input, the normalised input and every user turn of
the conversation history, and its result is unioned with any red flags from the LLM.
Any red flag => emergency path, no follow-ups, no caregiver matching.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .lang import clean, normalise

EMERGENCY_CARE_TYPE = "emergency_referral"
MOST_URGENT = "immediate"

W = r"(?:\S+\s+)"  # one word + trailing space, for "up to N words between" gaps

# --- simple flags: any pattern match (not negated, not excluded) fires the flag -----------------
SIMPLE: dict[str, list[str]] = {
    "chest_pain": [
        r"chest\s*(pain|pressure|tightness|heaviness|discomfort)", r"(pain|pressure|tightness|heaviness)\s+in\s+(the\s+|my\s+|his\s+|her\s+)?chest",
        r"heart\s*attack", r"(crushing|squeezing)\s+(pain\s+)?(in\s+)?(the\s+)?chest",
        rf"\b(seene|sine|seena|sina|chhati|chati|chest)\s+{W}{{0,3}}(dard|dardh|pain|dabav|dabaav|bhaari|bhari|bharipan|jakdan)",
        r"dil\s+(ka\s+daura|mein\s+dard|me\s+dard)",
        r"(सीने|छाती|सीना)[^।,.!?]{0,20}(दर्द|दबाव|भारीपन|भारी|जकड़न)", r"दिल का दौरा", r"दिल में दर्द",
    ],
    "severe_breathing_difficulty": [
        r"(can'?t|cannot|can not|unable to|not able to|struggling to|hard to|difficult to)\s+breath",
        r"(difficulty|trouble|problem|difficulties)\s+(in\s+|with\s+)?breathing", r"breathing\s+(difficulty|problem|trouble)",
        r"short(ness)?\s+of\s+breath", r"breathless", r"gasping", r"choking", r"not\s+breathing", r"stopped\s+breathing",
        r"breathing\s+(very\s+)?(fast|rapid|heavily|hard)", r"cannot breathe", r"dyspn", r"respiratory\s+distress",
        r"breathing\s+is\s+(very\s+)?(hard|difficult|laboured|labored)",
        rf"\b(saa?ns|sans|saas|swas|shwas|swaas)\s+{W}{{0,3}}(nahi\s+aa|nhi\s+aa|nahin\s+aa|ruk|phool|phul|ful\b|fool|dikk?at|takleef|taklif|problem|tang|band|nahi\s+le|nhi\s+le|atak|ukhad)",
        r"dam\s+gh[ou]t",
        r"(साँस|सांस|सास|श्वास)[^।,.!?]{0,25}(नहीं आ|फूल|रुक|दिक्कत|तकलीफ|परेशानी|नहीं ले|बंद|अटक|उखड़)", r"दम घुट",
    ],
    "blue_lips": [
        r"(lips?|face|nails?|fingers?|tongue)\s+(are\s+|is\s+)?(turning\s+|turned\s+|going\s+|gone\s+)?(blue|bluish|purple)",
        r"blue\s+(lips|face)",
        rf"\b(hont|honth|hoth|hoot|honthon|chehra|nakhun)\s+{W}{{0,2}}(neel|neele|neela|nila|nile|blue)",
        r"(होंठ|होठ|चेहरा|नाखून)[^।,.!?]{0,15}(नीले|नीला|नीली|नील)",
    ],
    "unconscious": [
        r"unconscious", r"unresponsive", r"(not|isn'?t|is\s+not|stopped)\s+(responding|responsive|waking|conscious)",
        r"passed\s+out", r"faint(ed|ing)", r"syncop", r"loc", r"loss\s+of\s+consciousness", r"collapsed", r"lost\s+consciousness", r"(won'?t|can'?t|cannot)\s+wake",
        r"\bbeh?oo?sh", r"\bbehos\b", r"\bhosh\s+(mein\s+|me\s+)?(nahi|nhi|nahin)", r"\bhosh\s+(kho|ud)",
        r"(jawab|response)\s+(nahi|nhi|nahin)\s+de", r"(uth|jaag)\s+(nahi|nhi)\s+rah",
        r"बेहोश", r"(?<!बे)होश\s*(में)?\s*नहीं", r"(?<!बे)होश खो", r"जवाब नहीं दे",
    ],
    "seizure": [
        r"seizure", r"convuls", r"\bfits?\b", r"epilep", r"jerking", r"\bdaura\b(?!\s+(par|pe))", r"\bdora\s+pad",
        r"mirgi", r"jhatk[ae]", r"दौरा", r"मिर्गी", r"झटके",
        r"froth|foam\w*\s+(at|from)\s+(the\s+)?mouth", r"(muh|munh|mooh)\s+(se|mein)\s+(jhaag|jhag|jhaig)", r"(मुँह|मुंह)\s*(से|में)\s*झाग",
        r"(whole\s+body|all\s+over|body\s+is)\s+(\S+\s+)?(shaking|jerking|twitching)|(shaking|jerking|twitching)\s+all\s+over",
        r"(eyes?\s+(rolled|rolling)\s+(up|back))|(aankh\w*\s+(upar|ulat)\w*)",
        r"(poora|pura|saara|sara)\s+(sharir|shareer|badan|body)\s+(\S+\s+)?(kaanp|kanp|akad|jhatk)", r"(पूरा|सारा)\s*(शरीर|बदन)\s*(\S+\s*)?(काँप|कांप|अकड़|झटक)",
    ],
    "low_blood_sugar": [
        r"hypoglyc", r"(sugar|glucose|शुगर)\s+(\S+\s+){0,3}([2-5]\d|6[0-5])\b(?!\s*(saal|years?|sal|%|mg/dl\s+high))",
        r"(sugar|glucose)\s+(\S+\s+){0,2}(is\s+|has\s+)?(very\s+)?(low|dropped|crashed|fallen)", r"low\s+(blood\s+)?sugar",
        r"(sugar|shugar)\s+(\S+\s+){0,2}(kam|low|gir)\s+(ho\s+)?(gayi|gai|gyi|hai)", r"शुगर\s*(\S+\s*)?(कम|गिर|लो)",
    ],
    "urinary_retention": [
        r"(can'?t|cannot|unable\s+to|not\s+able\s+to)\s+(pass\s+urine|urinate|pee)", r"(no|not\s+passed\s+any)\s+urine\s+(since|for)",
        r"(haven'?t|hasn'?t|not)\s+(passed|peed)\s+(any\s+)?(urine)?\s*(since|for|all)",
        r"(peshab|pishab|pesab|urine)\s+(\S+\s+){0,2}(ruk\s+gay|band\s+ho\s+gay|nahi\s+(ho|aa|utar)\s+(raha|rahi|rha|rhi))",
        r"(पेशाब)\s*(\S+\s*)?(रुक\s*गया|बंद\s*हो|नहीं\s*(हो|आ|उतर))",
    ],
    "sudden_vision_loss": [
        r"(can'?t|cannot|unable\s+to|not\s+able\s+to)\s+see\b", r"(lost|losing|loss\s+of)\s+(\S+\s+)?(vision|sight|eyesight)",
        r"(vision|sight)\s+(\S+\s+)?(gone|went|blacked|blacking|disappeared|suddenly)", r"everything\s+(is\s+|went\s+)?(dark|black)",
        r"(sudden|suddenly)\s+(\S+\s+){0,2}(blind|dark|vision|see)", r"(dikhna|dikhai\s+dena)\s+band", r"dikh(ai|ayi)?\s+(nahi|nhi)\s+(de|raha|rahi)",
        r"andhera\s+(chha|aa)", r"दिखना बंद", r"दिखाई\s*नहीं\s*दे", r"अंधेरा\s*छा",
    ],
    "stroke_signs": [
        r"slurr", r"dysarthria|hemipar|hemipleg|facial\s+palsy",r"(face|mouth)\s+(is\s+)?(droop|drooping|tilted|twisted|crooked|deviated)", r"droop",
        r"(one|left|right)\s+side\s+(of\s+(the\s+|his\s+|her\s+)?(body|face)\s+)?(is\s+)?(weak|numb|paraly|not\s+moving)",
        r"weakness\s+(on|in)\s+one\s+side", r"(lt|rt|left|right)\.?\s+side\s+(\S+\s+)?weak", r"paraly", r"\bstroke\b", r"sudden\w*\s+(loss\s+of\s+)?(vision|speech)",
        r"can'?t\s+(speak|talk)\s+properly",
        r"(can'?t|cannot|unable\s+to|not\s+able\s+to)\s+(lift|move|raise|feel)\s+(\S+\s+){0,2}(arm|leg|hand|side)",
        r"(words|speech)\s+(\S+\s+){0,3}(jumbled|garbled|mixed\s+up|confused)|jumbled\s+(words|speech)|trouble\s+(speaking|finding\s+words)",
        r"(face|mouth|smile)\s+(\S+\s+){0,3}(droop|crooked|twisted|tilted|lopsided|deviated|uneven)", r"(crooked|lopsided|uneven)\s+(face|smile|mouth)",
        rf"\b(haath|hath|pair|baazu|bazu)\s+{W}{{0,2}}(utha|hila|chala)\s+(nahi|nhi)\s+(pa|sak)",
        r"(हाथ|पैर|बाजू|बाज़ू)\s*(\S+\s*)?(उठा|हिला)\s*नहीं\s*(पा|सक)",
        rf"\b(awaaz|awaz|aawaz|aawaaz|zuban|zubaan|jubaan|juban|bolne|boli|bol)\s+{W}{{0,3}}(ladkh?ad|lad\s*khad|atak|saaf\s+nahi|nahi\s+nikal)",
        rf"\b(chehra|chehre|muh|munh|mooh|muhn)\s+{W}{{0,3}}(tedh|terh|tirch|latak|tedha)",
        rf"\b(ek\s+taraf|ek\s+side|aadha|aadhe|adha|adhe|left\s+side|right\s+side)\s+{W}{{0,2}}(kamz?j?or|sunn|lakwa|kaam\s+nahi|hil\s+nahi|chal\s+nahi)",
        r"lakwa|lakva|laqwa", r"\bstroke\b",
        r"(आवाज़|आवाज|ज़ुबान|जुबान|बोली|बोलने)[^।,.!?]{0,15}(लड़खड़|लडखड|अटक|साफ नहीं)",
        r"(चेहरा|चेहरे|मुँह|मुंह)[^।,.!?]{0,20}(टेढ़|टेढा|टेड़|लटक)", r"लकवा",
        r"(एक तरफ|आधे शरीर|आधा शरीर)[^।,.!?]{0,15}(कमज़ोर|कमजोर|सुन्न|काम नहीं)",
    ],
    "heavy_bleeding": [
        r"(heavy|heavily|lots?\s+of|severe|profuse|uncontrolled|non[- ]?stop|massive|a\s+lot\s+of)\s+(bleeding|blood)",
        r"bleeding\s+(heavily|a\s+lot|profusely|badly|won'?t\s+stop|not\s+stopping|non[- ]?stop|nonstop|continuously)",
        r"blood\s+(won'?t|will\s+not|is\s+not|isn'?t)\s+stop",
        r"(keeps|keep|kept|still|continuous\w*|constantly)\s+(on\s+)?bleeding", r"bleeding\s+(\S+\s+)?(through|soak)", r"soak\w*\s+(\S+\s+){0,3}blood",
        r"blood\s+(\S+\s+){0,2}(soak|gushing|spurting|pouring|squirting)", r"(deep|big|large|gaping)\s+(cut|wound|gash|laceration)",
        r"(gehra|gahra|bada)\s+(kat|cut|ghaav|zakhm)", r"(गहरा|बड़ा)\s*(कट|घाव|ज़ख्म|जख्म)",
        # blood in the cough of unstated amount is NOT flagged here: the cough pathway asks how much (streaks vs a
        # spoonful) and escalates large amounts or blood with breathlessness, chest pain or fainting at once
        r"vomit\w*\s+(of\s+)?blood", r"ha?ematemesis|melena", r"blood\s+in\s+(the\s+)?vomit",
        r"cough\w*\s+(up\s+)?(a\s+lot\s+of|lots\s+of|so\s+much|a\s+cup|cups|a\s+spoon\w*|spoonfuls?)\s+(of\s+)?blood",
        rf"\b(bahut|bohot|bht|zyada|jyada|kaafi|lagatar|bahot)\s+{W}{{0,2}}(kh[oo]+n|khun|blood|bleeding)",
        rf"\b(kh[oo]+n|khun|blood|bleeding)\s+{W}{{0,3}}(ruk\s+nahi|ruk\s+nhi|band\s+nahi|band\s+nhi|rukta\s+nahi)",
        r"(kh[oo]+n|khun)\s+ki\s+ult", r"ult\w*\s+(mein|me)\s+(kh[oo]+n|khun)",
        r"(बहुत|ज़्यादा|ज्यादा|लगातार|काफी)[^।,.!?]{0,10}(खून|ख़ून|रक्त)", r"(खून|ख़ून)[^।,.!?]{0,15}(रुक नहीं|बंद नहीं)",
        r"खून की उल्टी", r"उल्टी में खून",
    ],
    "severe_allergic_reaction": [
        r"(face|tongue|lips?)\s+(is\s+|are\s+|has\s+|have\s+)?(\S+\s+)?(swelling|swollen|swelled|puff)",
        r"swelling\s+(of|in|on)\s+(the\s+|his\s+|her\s+|my\s+)?(face|tongue|lips)", r"anaphyla",
        r"throat\s+(is\s+)?(closing|tight\w*)",
        rf"\b(chehra|chehre|jeebh|jibh|hont|honth|hoth)\s+{W}{{0,3}}(sooj|suj|phool\s+gay|sujan|soojan)",
        r"(चेहरा|चेहरे|जीभ|होंठ|होठ)[^।,.!?]{0,15}(सूज|सूजन)",
    ],
    "suicidal_intent": [
        r"suicid", r"kill\s+(my|him|her)sel", r"end\w*\s+(my|his|her)\s+life", r"(don'?t|do\s+not|doesn'?t)\s+want\s+to\s+live",
        r"want\s+to\s+die", r"self[- ]?harm", r"(cut|cutting|hurt|hurting|harm|harming)\s+(my|him|her)sel",
        r"no\s+reason\s+to\s+live", r"better\s+off\s+dead", r"end\s+it\s+all", r"(end|finish)\s+(everything|it)\s*$",
        r"take\s+(my|his|her)\s+(own\s+)?life", r"no\s+point\s+(in\s+)?(living|life)", r"(wants?|going|trying|thinking)\s+to\s+(end|finish)\s+(it|myself|herself|himself|everything)",
        r"(sab|sabkuch|sab\s+kuch|zindagi|jindagi)\s+(\S+\s+)?(khatam|khtm)\s+(kar|karna|kardu|kar\s+du)",
        r"(ज़िंदगी|जिंदगी|सब कुछ|सबकुछ)\s*(\S+\s*)?(खत्म|ख़त्म)\s*कर",
        r"(jeena|jina|jeene)\s+(ka\s+mann\s+)?(nahi|nhi|nahin)", r"marna\s+chah", r"mar\s+ja(a)?na\s+chah", r"mar\s+jaunga|mar\s+jaungi",
        r"khudkushi|khudkhushi|aatmhatya|atmahatya|aatmahatya", r"khud\s+ko\s+(khatam|maar|mar|nuksan|nuksaan|hurt|chot)",
        r"jaan\s+de\s+(du|dun|denge|dunga|dungi)",
        r"आत्महत्या|खुदकुशी|ख़ुदकुशी", r"जीना नहीं", r"जीने का मन नहीं", r"मरना चाह", r"खुद को\s*(खत्म|ख़त्म|मार|नुकसान)", r"जान दे",
    ],
    "poisoning_overdose": [
        r"poison", r"overdose", r"intoxicat", r"pesticide|insecticide|rat\s*(poison|kill)",
        r"(swallow|drank|drink|drunk|ate|took|taken|consumed)\w*\s+(\S+\s+){0,3}(bleach|acid|kerosene|phenyl|detergent|pesticide|poison|toilet\s+cleaner)",
        r"(too\s+many|a\s+lot\s+of|whole\s+(bottle|strip)\s+of|all\s+(the|his|her|my))\s+(\S+\s+)?(pills|tablets|medicines?)",
        r"(snake|scorpion)\s*(bite|bit|sting|stung)", r"bitten\s+by\s+a\s+(snake|scorpion)",
        r"zeh[ae]r|jah[ae]r|jeher|zahar", r"(keede|keeda|chuhe|chuha|machhar)\s+maar", r"kerosene|phenyl|tezaab|tezab",
        r"mitti\s+ka\s+tel\s+(\S+\s+)?(pee|pi|kha|nigal)|मिट्टी\s*का\s*तेल\s*(\S+\s*)?(पी|खा)",
        rf"\b(saari|sari|bahut|zyada|jyada|poori|puri)\s+{W}{{0,3}}(goliyan|goliya|goli|tablets?|dawai|dawa|dawaiyan)\s+{W}{{0,2}}(kha|le|pee|pi|nigal)",
        r"\b(saanp|sanp|saap|bichhu|bichu)\b",
        r"ज़हर|जहर|विष", r"(चूहे|कीड़े|कीडे)[^।,.!?]{0,6}मार", r"(सारी|बहुत|ज़्यादा|ज्यादा|पूरी)[^।,.!?]{0,6}(गोलियाँ|गोलियां|गोली|दवा|दवाई)",
        r"साँप|सांप|बिच्छू", r"तेज़ाब|तेजाब|केरोसिन|फिनाइल",
    ],
    "severe_burns": [
        r"(severe|severely|bad|badly|major|large|serious|deep|extensive)\w*\s+(\S+\s+){0,3}burn",
        # "burning in the chest / stomach / urine" is a sensation, not a burn injury
        r"burn(?!ing\s+(sensation|feeling|in\s+(the\s+|my\s+|his\s+|her\s+)?(chest|stomach|urine|throat)|of\s+(the\s+)?chest))\w*\s+(\S+\s+){0,5}(large|whole|entire|face|body|chest|severe|badly)",
        r"caught\s+fire", r"on\s+fire",
        r"electric\w*\s+(shock|burn)|electrocut", r"acid\s+(attack|burn)",
        r"\bjal\s+(gaye|gayi|gaya|gae|gyi|gya|gai)", r"jhulas", r"aag\s+(lag|mein|me)", r"(current|karant|bijli)\s+(lag|ka\s+jhatka)",
        r"जल\s*(गए|गई|गया|गये)", r"झुलस", r"आग\s*(लग|में)", r"करंट",
    ],
    "major_trauma": [
        r"(road|car|bike|scooter|truck|bus|motorcycle|two[- ]wheeler)\s+accident", r"accident",
        r"(fell|fallen|fall)\s+(\S+\s+){0,2}(from|off)\s+(\S+\s+){0,2}(roof|terrace|height|building|tree|ladder|balcony)",
        r"(broken|fractured)\s+(\S+\s+)?(bone|leg|arm|hip|neck|back)", r"bone\s+(is\s+)?(sticking|broken|out)", r"fracture",
        r"(haddi|haath|hath|pair|taang|tang|baazu|bazu)\s+(\S+\s+)?(toot|tut|tooti|tuti)", r"haddi\s+(tedhi|bahar)",
        r"(arm|leg|wrist|ankle|hip)\s+(is\s+|looks\s+|seems\s+)?(broken|fractured|deformed)",
        r"(chhat|chat|chhath|seedhi|ped)\s+se\s+gir",
        r"एक्सीडेंट|दुर्घटना", r"(हड्डी|हाथ|पैर|टांग|बाज़ू|बाजू)\s*(\S+\s*)?(टूट)", r"हड्डी\s*(टेढ़|बाहर)", r"(छत|सीढ़ी|पेड़)\s*से\s*गिर",
    ],
    "altered_mental_state": [
        r"\bconfus", r"disorient", r"mental\s+(status\s+)?change", r"altered\s+(mental|sensorium|consciousness)",
        r"not\s+making\s+sense", r"talking\s+nonsense", r"delirious",
        r"(talking|speaking|behaving|acting)\s+(very\s+)?(strange|strangely|odd|oddly|weird|weirdly|abnormal|funny)",
        r"(ajeeb|ajib)\s+(\S+\s+)?(baat|harkat|vyavhar|behave)", r"(अजीब)\s*(\S+\s*)?(बात|हरकत|व्यवहार)",
        r"(not|isn'?t|can'?t|cannot)\s+recogni[sz]", r"very\s+drowsy", r"responds\s+to\s+(pain|voice)\s+only",
        r"beh?ki\s+beh?ki|bahki\s+bahki|ulti\s+seedhi\s+baat|ajeeb\s+baat", r"pehchaan?\s+(nahi|nhi)", r"\bbhram",
        r"बहकी", r"भ्रम", r"पहचान नहीं", r"उल्टी सीधी बात",
    ],
}

# Clause-level exclusions per flag: if any of these is in the same clause, the flag is not fired.
EXCLUDE: dict[str, list[str]] = {
    "seizure": [r"\bfits?\s+(well|fine|properly|in)\b", r"\bfit\s+(hai|hain|hoon|hu|h|he|ho|rehte|rehti)\b",
                r"dil\s+ka\s+daura", r"fit\s+(and|&)\s+fine", r"chill|shiver|\bcold\b|thand|sardi\s+se|ठंड"],
    "stroke_signs": [],
    # heavy periods over weeks/months is a specialist problem, not a haemorrhage; "a little blood" is not heavy
    "heavy_bleeding": [r"\b(thoda|thodi|little|slight|minor|halka|halki|a\s+bit)\b\s*(sa\s+|si\s+)?(\S+\s+)?(kh[oo]+n|khun|blood|bleed)",
                       r"(bleed\w*|blood|kh[oo]+n|khun)\s+(\S+\s+)?(a\s+(bit|little)|thoda|slightly)",
                       r"(small|minor|chhota|chhoti|tiny)\s+(\S+\s+)?(cut|wound|scratch|kat|ghaav|kharonch)",
                       r"(थोड़ा|थोड़ी|हल्का)\s*(सा\s*)?(खून)", r"(छोटा|छोटी)\s*(सा\s*)?(कट|घाव)",
                       r"period|mahwari|maahwari|masik|menstru|पीरियड|माहवारी|मासिक",
                       # "khoon ki kami" (anaemia) and "khoon ki jaanch" (blood test) are not bleeding
                       r"(kh[oo]+n|khun)\s+(ki|ka)\s+(kami|kamee|jaa?n?ch|test|report|sample)|blood\s+(test|report|sample)|an(a)?emi",
                       r"(खून|ख़ून)\s*(की|का)\s*(कमी|जाँच|जांच|टेस्ट|रिपोर्ट)"],
    # clearly chest-wall pain (on pressing / movement / after gym or a knock) with no cardiac feature in the clause
    "chest_pain": [r"^(?!.*(bhaari|bhari|dabav|dabaav|pressure|heav|squeez|tight|paseen|pasin|sweat|saans|breath|jabd|jaw|left\s+arm|"
                   r"baa?ye?i?n?\s+haath|भारी|दबाव|पसीना|साँस|सांस)).*((dabane|daba\w*|press\w*)\s+(par|pe|karne|se)|on\s+pressing|when\s+i\s+press|"
                   r"(gym|workout|exercise|lifting|weight\s+uthane|kasrat)\s+(ke\s+)?baad|after\s+(the\s+)?(gym|workout|exercise|lifting)|"
                   r"hilne\s+par|on\s+movement|muscle\s+(pain|pull|strain)|chot\s+ke\s+baad|दबाने\s*पर)"],
    # a blocked catheter is a same-day nursing problem; low sugar target talk ("keep sugar above 70") is not an event
    "low_blood_sugar": [r"\b(target|keep|should\s+be|range|normal)\b"],
    # gradual vision trouble over months is a specialist problem
    "sudden_vision_loss": [r"(months?|years?|mahin|saal|महीन|साल|gradual|slowly|dheere)"],
    "major_trauma": [r"\b(minor|small|chhota|chhoti|halka)\b\s+(\S+\s+)?accident"],
    "severe_breathing_difficulty": [],
}
# Per-pattern exclusions: only the bare keyword is suppressed, acute signs in the same clause still fire.
# e.g. "discharged after a stroke" (history) vs "had a stroke last year, now slurred speech again" (acute sign).
STROKE_HISTORY = [r"(after|since|post|had|history\s+of|old|previous|past|pichle\s+saal)\s+(\S+\s+){0,2}(stroke|paraly|lakwa|lakva)",
                  r"(stroke|paraly\w*|lakwa|lakva|लकवा)\s+(\S+\s+){0,3}(for|since|से)\s+(\S+\s+)?(years?|months?|saal|mahin\w*|साल|महीन)",
                  r"(years?|months?|saal|mahin\w*|साल|महीन\w*)\s+(\S+\s+){0,2}(se\s+|से\s+)?(\S+\s+)?(paraly|lakwa|लकवा)",
                  r"bedridden|bistar\s+par|बिस्तर\s*पर",
                  r"(stroke|lakwa|lakva|paralysis)\s+(\S+\s+){0,2}(ke\s+baad|hua\s+tha|aaya\s+tha|pada\s+tha|last\s+year|years?\s+ago)",
                  r"(लकवा|स्ट्रोक)\s*(के बाद|हुआ था|पड़ा था)"]
PATTERN_EXCLUDE: dict[str, list[str]] = {
    r"paraly": STROKE_HISTORY, r"\bstroke\b": STROKE_HISTORY, r"lakwa|lakva|laqwa": STROKE_HISTORY, r"लकवा": STROKE_HISTORY,
    r"dysarthria|hemipar|hemipleg|facial\s+palsy": STROKE_HISTORY,
}
# Message-level exclusions (checked against the whole text, not just the clause).
TEXT_EXCLUDE: dict[str, list[str]] = {
    "urinary_retention": [r"catheter|कैथेटर"],
    # chest discomfort that comes and goes and is not happening right now, with no cardiac feature anywhere:
    # the chest pain pathway routes it (S2 cardiology with risk factors), it is not a current emergency
    "chest_pain": [r"^(?!.*(bhaa?ri|dabaa?v|pressure|heav|squeez|tight|paseen|pasin|sweat|saans|breath|jabd|jaw|left\s+arm|"
                   r"baa?ye?i?n?\s+haath|faint|chakkar|behosh|भारी|दबाव|पसीना|साँस|सांस|चक्कर|बेहोश))"
                   r".*(on\s+and\s+off|comes\s+and\s+goes|kabhi\s+kabhi|aata[- ]jaata|कभी[- ]कभी|आता[- ]जाता)"
                   r".{0,60}(not\s+(right\s+)?now|abhi\s+(nahi|nhi|theek)|अभी\s+(नहीं|ठीक))"],
}
CHRONIC = re.compile(r"(months?|years?|mahin|saal|महीन|साल)")
EXERTION = re.compile(r"(stairs|walk|exercise|exertion|climb|seedh?i|chadhne|chalne|chalte|daudne|सीढ़ी|चढ़ने|चलने)", re.I)
EXERTION_ONLY = re.compile(r"\b(chalne|seedh?i(yan)?\s+chadhne|kaam\s+karne|daudne)\s+(par|pe|se)\b|\b(on|when|while|after)\s+(walking|climbing|exertion|exercise)\b|"
                           r"(चलने|सीढ़ी चढ़ने)\s*(पर|से)", re.I)

# --- combo flags: need a trigger AND a qualifier somewhere in the (whole) text --------------------
FEVER = r"(fever|temperature|bukh?aa?r|bukar|बुखार|ताप)"
COMBOS: dict[str, tuple[list[str], list[str]]] = {
    "fever_stiff_neck_confusion": (
        [FEVER],
        [r"stiff\w*\s+neck|neck\s+(is\s+)?(stiff|rigid)|neck\s+stiff", r"gardan\s+(\S+\s+)?(akad|akd|jakad|jakd|stiff)",
         r"गर्दन[^।,.!?]{0,10}(अकड़|अकड|जकड़)", r"\bconfus", r"beh?ki|bahki", r"बहकी|भ्रम", r"rash\s+that\s+does\s*n.?t\s+fade",
         r"(talking|speaking|behaving|acting)\s+(very\s+)?(strange|odd|weird)", r"ajeeb|ajib|अजीब", r"(very\s+)?(drowsy|sleepy)\s+and\s+(not|hard)"],
    ),
    "infant_danger_signs": (
        [r"\b(baby|infant|newborn|new\s*born|navjaat|shishu)\b", r"\b([0-9]|1[0-2]|one|two|three|four|five|six)\s*[- ]?(month|months|mahine|mahina|week|weeks|hafte|din)\s*[- ]?(old|ka|ki|ke)\b",
         r"नवजात|शिशु", r"(एक|दो|तीन|चार|पाँच|पांच|छह|[0-9]+)\s*(महीने|हफ्ते|दिन)\s*(का|की|के)"],
        [r"(high|very\s+high|tez|tej|bahut)\s+(\S+\s+)?(fever|bukh?aa?r|temperature)", r"तेज़?\s*बुखार|बहुत बुखार",
         r"(not|isn'?t|stopped|refus\w*)\s+(feeding|drinking|taking\s+(milk|feeds))", r"(doodh|feed|milk)\s+(\S+\s+)?(nahi|nhi|nahin)",
         r"दूध[^।,.!?]{0,10}नहीं", r"letharg|limp|floppy|\bsust\b|सुस्त", r"not\s+moving|hil\s+nahi|हिल\s*नहीं",
         r"breathing\s+fast|tez\s+saans|तेज़? साँस", r"blue|neela|नीला", r"seizure|fit|daura|दौरा", r"(won'?t|not)\s+wak"],
    ),
    # an (elderly) fall followed by inability to stand / hip pain: possible fracture
    "fall_cannot_stand": (
        [r"\b(fell|fall|fallen|slipped|slip|gir|girr|fisal)\w*", r"(गिर|फिसल)"],
        [r"(can'?t|cannot|unable\s+to|not\s+able\s+to)\s+(stand|get\s+up|bear\s+weight|move\s+(the\s+)?(leg|hip))",
         r"\bhip\b|kulh|कूल्ह", r"(uth|khade|khada|khadi)\s+(\S+\s+)?(nahi|nhi)\s+(ho\s+)?(pa|sak)", r"(उठ|खड़े|खड़ी)\s*(\S+\s*)?नहीं\s*(हो\s*)?(पा|सक)"],
    ),
    # pain spreading to the left arm / jaw is cardiac only together with sweating, chest or breathing symptoms
    "cardiac_referred_pain": (
        [r"(pain|ache|dard|heaviness)\s+(\S+\s+){0,4}(left\s+(arm|shoulder)|jaw|baa?ye?i?n?\s+(haath|kandhe)|jabd)",
         r"(left\s+(arm|shoulder)|jaw|baa?ye?i?n?\s+(haath|kandhe)|jabd\w*)\s+(\S+\s+){0,2}(pain|ache|dard|hurt)",
         r"(बाएँ|बाएं|बायें)\s*(हाथ|कंधे)[^।,.!?]{0,15}दर्द", r"जबड़[^।,.!?]{0,10}दर्द"],
        [r"sweat|paseen|pasina|पसीना", r"chest|seene|sine|chhati|सीने|छाती", r"breath|saans|सांस|साँस", r"ghabrah|घबराह|uneasy|nause|vomit|ulti|उल्टी"],
    ),
    # any fever in a baby under ~3 months (reported as "young_infant_fever", surfaced as infant_danger_signs)
    "young_infant_fever": (
        [r"\b(newborn|new\s*born|navjaat)\b", r"\b([0-9]|1[0-2]|one|two|three|four|five|six)\s*[- ]?(week|weeks|hafte|hafta|din|days?)\s*[- ]?(old|ka|ki|ke)\b",
         r"\b([0-2]|one|two)\s*[- ]?(month|months|mahine|mahina)\s*[- ]?(old|ka|ki|ke)\b", r"नवजात",
         r"(एक|दो|तीन|चार|[0-9]+)\s*(हफ्ते|हफ़्ते|दिन)\s*(का|की|के)", r"(एक|दो|[0-2])\s*(महीने)\s*(का|की|के)"],
        [FEVER],
    ),
    "pregnancy_emergency": (
        [r"pregnan", r"garbh|garbhvati|garbhwati|pet\s+se\s+hai|expecting", r"गर्भ|प्रेग्नेंट|गर्भवती"],
        [r"bleed|blood(?!\s*(ki\s+|ka\s+)?(test|report|sugar|pressure|sample|group|check|bp|kami|kamee|jaa?n?ch))|spotting",
         r"(kh[oo]+n|khun)(?!\s*(ki\s+|ka\s+)?(jaa?n?ch|test|report|sample|kami|kamee))",
         r"(खून|ख़ून|रक्त)(?!\s*(की|का)?\s*(जाँच|जांच|टेस्ट|रिपोर्ट|सैंपल|कमी))", r"(severe|tez|tej|bahut|unbearable)\s+(\S+\s+)?(pain|dard)",
         r"(तेज़|तेज|बहुत)\s*दर्द", r"water\s+(broke|break)|paani\s+(gir|nikal|aa)", r"पानी\s*(गिर|निकल)",
         r"seizure|fit|daura|दौरा",
         r"(baby|bachch?[aei])\s+(\S+\s+){0,2}(not\s+mov|hasn'?t\s+mov|stopped\s+mov|hil\s+(nahi|nhi)|hilna\s+band)",
         r"(no|less|reduced|decreased)\s+(fetal\s+|baby'?s?\s+)?movement", r"बच्चा\s*(\S+\s*)?हिल\s*(नहीं|ना)",
         r"severe\s+headache.*(blur|vision)", r"behosh|बेहोश|faint"],
    ),
    "severe_head_injury": (
        [r"head\s+(injury|trauma)|hit\s+(\S+\s+)?head|head\s+(\S+\s+){0,2}(hit|injur|bang|bump)|(fell|fall|accident)\s+(\S+\s+){0,6}head",
         r"\b(sar|sir|sarr)\s+(\S+\s+){0,2}(chot|chott|lag\s+gay|phat|fat\s+gay|takra)", r"सिर[^।,.!?]{0,12}(चोट|फट|टकरा)"],
        [r"vomit|\bult[ie]|उल्टी", r"confus|beh?ki|bhram|भ्रम|बहकी", r"unconscious|behosh|बेहोश|faint", r"bleed|blood|kh[oo]+n|khun|खून",
         r"seizure|fit|daura|दौरा", r"drows|neend|sleepy|नींद", r"severe|bad|serious|gambhir|गंभीर",
         r"(not|can'?t)\s+(walk|talk|speak)|bol\s+nahi"],
    ),
}

FLAG_ALIAS = {"young_infant_fever": "infant_danger_signs", "cardiac_referred_pain": "chest_pain", "fall_cannot_stand": "major_trauma"}

# --- negation ------------------------------------------------------------------------------------
CLAUSE_SPLIT = re.compile(r"[,.;!?।|\n]+|\s(?:but|however|although|lekin|magar|parantu|लेकिन|मगर|परंतु|किंतु)\s", re.I)
PRE_NEG = {"no", "not", "never", "without", "denies", "denied", "deny", "nor", "neither", "dont", "don't", "doesnt",
           "doesn't", "didnt", "didn't", "isnt", "isn't", "hasnt", "hasn't", "havent", "haven't", "negative", "bina",
           "बिना", "koi"}
PRE_BREAK = {"and", "but", "with", "aur", "also", "plus", "now", "then", "और", "अब", "phir", "fir", "since"}
POST_NEG = {"nahi", "nahin", "nhi", "nai", "not", "नहीं", "न", "ना", "mat", "मत"}
POST_FILLER = {"bilkul", "to", "toh", "koi", "hi", "bhi", "ho", "raha", "rahi", "rahe", "rha", "rhi", "hua", "hui", "hue",
               "hota", "hoti", "is", "was", "ki", "ka", "ke", "बिल्कुल", "तो", "कोई", "भी", "ही", "हो", "रहा", "रही", "रहे",
               "हुआ", "हुई", "की", "का", "के", "abhi", "अभी", "at", "all"}


@dataclass
class SafetyResult:
    red_flags: list[str] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)

    @property
    def is_emergency(self) -> bool:
        return bool(self.red_flags)


def _compile(pats: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.I) for p in pats]


_SIMPLE_C = {k: _compile(v) for k, v in SIMPLE.items()}
_PEXCL_C = {re.compile(k, re.I).pattern: _compile(v) for k, v in PATTERN_EXCLUDE.items()}
_EXCL_C = {k: _compile(v) for k, v in EXCLUDE.items()}
_TEXCL_C = {k: _compile(v) for k, v in TEXT_EXCLUDE.items()}
_COMBO_C = {k: (_compile(a), _compile(b)) for k, (a, b) in COMBOS.items()}
_TOKEN = re.compile(r"[\wऀ-ॿ']+")


def _tokens(s: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(s)]


def _negated(clause: str, start: int, end: int) -> bool:
    before = _tokens(clause[:start])[-5:]
    for i in range(len(before) - 1, -1, -1):
        w = before[i]
        if w in PRE_BREAK:
            break
        if w in PRE_NEG:
            # "koi" alone is not a negation unless a negation follows the match ("koi dikkat nahi")
            if w != "koi":
                return True
    after = _tokens(clause[end:])[:4]
    for w in after:
        if w in POST_FILLER or w in ("hai", "hain", "h", "he", "है", "हैं", "थी", "था"):
            continue
        return w in POST_NEG
    return False


def clauses(text: str) -> list[str]:
    return [c.strip() for c in CLAUSE_SPLIT.split(text) if c and c.strip()]


def _scan_text(text: str, found: dict[str, str]) -> None:
    for cl in clauses(text):
        for flag, pats in _SIMPLE_C.items():
            if flag in found:
                continue
            if any(x.search(cl) for x in _EXCL_C.get(flag, [])) or any(x.search(text) for x in _TEXCL_C.get(flag, [])):
                continue
            # breathlessness only on exertion (long-standing, or explicitly "chalne par" / "on walking") is not an
            # emergency by itself: the breathing / fever / cough pathways ask one confirmation question about rest,
            # speech and lip colour. Never when the clause also says rest, severe or "bahut".
            if (flag == "severe_breathing_difficulty" and EXERTION.search(cl)
                    and (CHRONIC.search(text) or EXERTION_ONLY.search(cl))
                    and not re.search(r"\b(rest|sitting|lying|baithe|lete|aaram)\b|severe|bahut|bohot|बहुत|आराम|बैठे", cl, re.I)):
                continue
            for p in pats:
                if any(x.search(cl) for x in _PEXCL_C.get(p.pattern, [])):
                    continue
                m = p.search(cl)
                while m:
                    if not _negated(cl, m.start(), m.end()):
                        found[flag] = cl
                        break
                    m = p.search(cl, m.end())
                if flag in found:
                    break


def _affirmed(pats: list[re.Pattern], text: str) -> str | None:
    for cl in clauses(text):
        for p in pats:
            for m in p.finditer(cl):
                if not _negated(cl, m.start(), m.end()):
                    return cl
    return None


def _scan_combos(text: str, found: dict[str, str]) -> None:
    for flag, (trig, qual) in _COMBO_C.items():
        if flag in found:
            continue
        t = _affirmed(trig, text)
        if t is None:
            continue
        q = _affirmed(qual, text)
        if q is not None:
            found[flag] = f"{t} | {q}"


def check(user_texts: list[str], extra_flags: list[str] | None = None) -> SafetyResult:
    """Run all rules over each user text (raw + normalised) and over the joined conversation."""
    found: dict[str, str] = {}
    raws = [clean(t) for t in user_texts if t and t.strip()]
    for t in raws:
        _scan_text(t, found)
        _scan_text(normalise(t), found)
    joined = " . ".join(raws)
    _scan_combos(joined, found)
    _scan_combos(normalise(joined), found)
    for f in extra_flags or []:
        if f and f not in found:
            found[f] = "confirmed"
    for alias, target in FLAG_ALIAS.items():
        if alias in found:
            found.setdefault(target, found.pop(alias))
    order = list(SIMPLE) + list(COMBOS)
    flags = sorted(found, key=lambda f: order.index(f) if f in order else len(order))
    return SafetyResult(red_flags=flags, evidence=found)


# --- emergency messaging -------------------------------------------------------------------------
FLAG_LABELS = {
    "chest_pain": ("chest pain or pressure", "सीने में दर्द या दबाव", "seene mein dard ya dabav"),
    "severe_breathing_difficulty": ("difficulty breathing", "साँस लेने में तकलीफ", "saans lene mein takleef"),
    "blue_lips": ("blue lips or face", "होंठ या चेहरा नीला पड़ना", "hont ya chehra neela padna"),
    "unconscious": ("unconscious or not responding", "बेहोशी या जवाब न देना", "behoshi ya jawab na dena"),
    "seizure": ("a seizure / fit", "दौरा पड़ना", "daura padna"),
    "low_blood_sugar": ("very low blood sugar", "शुगर बहुत कम होना", "sugar bahut kam hona"),
    "urinary_retention": ("unable to pass urine", "पेशाब पूरी तरह रुक जाना", "peshab ruk jaana"),
    "sudden_vision_loss": ("sudden loss of vision", "अचानक दिखना बंद होना", "achanak dikhna band hona"),
    "stroke_signs": ("signs of a stroke (face drooping, slurred speech or one-sided weakness)",
                     "लकवे के लक्षण (चेहरा टेढ़ा, बोली लड़खड़ाना या एक तरफ कमज़ोरी)",
                     "lakwe ke lakshan (chehra tedha, awaaz ladkhadana ya ek taraf kamzori)"),
    "heavy_bleeding": ("heavy bleeding", "बहुत ज़्यादा खून बहना", "bahut zyada khoon behna"),
    "severe_allergic_reaction": ("swelling of the face, lips or throat", "चेहरे, होंठ या गले में सूजन", "chehre, hont ya gale mein soojan"),
    "suicidal_intent": ("thoughts of suicide or self-harm", "खुद को नुकसान पहुँचाने के विचार", "khud ko nuksaan pahunchane ke vichaar"),
    "poisoning_overdose": ("possible poisoning or overdose", "ज़हर या दवा की ज़्यादा खुराक", "zeher ya dawa ki zyada khuraak"),
    "severe_burns": ("severe burns", "गंभीर रूप से जलना", "gambhir roop se jalna"),
    "major_trauma": ("a serious injury or accident", "गंभीर चोट या दुर्घटना", "gambhir chot ya accident"),
    "altered_mental_state": ("confusion or unusual behaviour", "भ्रम या असामान्य व्यवहार", "bhram ya ajeeb vyavhaar"),
    "fever_stiff_neck_confusion": ("fever with stiff neck or confusion", "बुखार के साथ गर्दन में अकड़न या भ्रम",
                                   "bukhar ke saath gardan akadna ya bhram"),
    "infant_danger_signs": ("danger signs in a young baby", "छोटे बच्चे में खतरे के लक्षण", "chhote bachche mein khatre ke lakshan"),
    "pregnancy_emergency": ("bleeding or severe pain in pregnancy", "गर्भावस्था में खून आना या तेज़ दर्द",
                            "pregnancy mein khoon aana ya tez dard"),
    "severe_head_injury": ("a serious head injury", "सिर में गंभीर चोट", "sar mein gambhir chot"),
}

STEPS = {
    "en": ("Call 112 (emergency) or 108 (ambulance) now. Stay with the person and keep them still and comfortable. "
           "Do not drive yourself if you feel unwell. Do not give food, drink or medicine unless the emergency operator tells you to."),
    "hi": ("अभी 112 (आपातकाल) या 108 (एम्बुलेंस) पर कॉल करें। मरीज़ के साथ रहें और उन्हें आराम से लिटाए रखें। "
           "अगर आपकी तबीयत ठीक नहीं है तो खुद गाड़ी न चलाएँ। जब तक आपातकालीन ऑपरेटर न कहे, खाना, पानी या दवा न दें।"),
    "hinglish": ("Abhi 112 (emergency) ya 108 (ambulance) par call karein. Mareez ke saath rahein aur unhe aaram se litaye rakhein. "
                 "Agar aapki tabiyat theek nahi hai to khud gaadi na chalayein. Jab tak emergency operator na kahe, khana, paani ya dawa na dein."),
}
SUICIDE_EXTRA = {
    "en": " You can also call the Tele-MANAS helpline 14416 (free, 24x7). You are not alone.",
    "hi": " आप टेली-मानस हेल्पलाइन 14416 (मुफ़्त, 24x7) पर भी कॉल कर सकते हैं। आप अकेले नहीं हैं।",
    "hinglish": " Aap Tele-MANAS helpline 14416 (free, 24x7) par bhi call kar sakte hain. Aap akele nahi hain.",
}


def flag_label(flag: str, lang: str) -> str:
    en, hi, hg = FLAG_LABELS.get(flag, (flag.replace("_", " "),) * 3)
    return {"hi": hi, "hinglish": hg}.get(lang, en)


def emergency_reasoning(flags: list[str], lang: str) -> str:
    labels = ", ".join(flag_label(f, lang) for f in flags[:3])
    head = {
        "en": f"Warning sign reported: {labels}. This needs emergency help now. ",
        "hi": f"खतरे का संकेत: {labels}। इसके लिए अभी आपातकालीन मदद चाहिए। ",
        "hinglish": f"Khatre ka sanket: {labels}. Iske liye abhi emergency madad chahiye. ",
    }.get(lang) or ""
    if not head:
        lang = "en"
        head = f"Warning sign reported: {labels}. This needs emergency help now. "
    extra = SUICIDE_EXTRA[lang] if "suicidal_intent" in flags else ""
    return head + STEPS[lang] + extra
