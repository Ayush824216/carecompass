"""Domain guard: keep the assistant strictly on health-care routing.

Runs after language detection and the safety gate (a red flag always wins, so "hello, papa behosh ho gaye"
still goes to the emergency path). Classifies the latest user turn into:

  health_request                 -> normal pipeline
  greeting_smalltalk             -> polite redirect
  off_topic                      -> polite redirect
  unclear_or_gibberish           -> ask for symptom / who / since when
  medicine_or_diagnosis_request  -> "I can't name medicines or diseases, but I can route you"
  abusive_or_prompt_injection    -> neutral redirect; injected instructions are never followed

Fast multilingual rules first; the LLM is only a tie-breaker for ambiguous multi-word text, with a timeout and a
rules-only fallback. A message that mixes small talk and a health problem is a health_request.
"""
from __future__ import annotations

import re
import unicodedata

from . import llm
from .intake import extract_slots
from .lang import clean, normalise

HEALTH = "health_request"
GREETING = "greeting_smalltalk"
OFF_TOPIC = "off_topic"
UNCLEAR = "unclear_or_gibberish"
MEDICINE = "medicine_or_diagnosis_request"
ABUSE = "abusive_or_prompt_injection"
CLASSES = (HEALTH, GREETING, OFF_TOPIC, UNCLEAR, MEDICINE, ABUSE)


def _rx(*parts: str) -> re.Pattern:
    return re.compile("|".join(parts), re.I)


# Care / health vocabulary beyond the symptom slots (EN, Hinglish, Devanagari)
HEALTH_WORDS = _rx(
    r"\b(sick|ill|unwell|not\s+well|not\s+feeling\s+well|health|healthy|patient|symptom|doctor|dr\.?|nurse|paramedic|caregiver|"
    r"hospital|clinic|ambulance|check[- ]?up|blood\s+test|bp|sugar|diabet|pregnan|injection|dressing|wound|surgery|operation|"
    r"medical|treatment|therapy|physio|bedridden|elderly|disabled|hurt|hurting|ache|aching|sore|bleed|fell|fall|injur|accident|"
    r"crying|not\s+eating|not\s+sleeping|tired|weak|faint|vomit|fever|cough|cold|pain|breath|dizzy|rash|itch|swell)\w*",
    r"\b(tabiyat|tabiyet|tabeeyat|bimar|beemar|bimaar|takleef|taklif|dard|bukhar|khansi|zukaam|ulti|dast|chakkar|kamzori|"
    r"chot|ghaav|khoon|sujan|soojan|khujli|jalan|peshab|latrine|pet\s+kharab|thik\s+nahi|theek\s+nahi|thik\s+nhi|theek\s+nhi|"
    r"ilaaj|ilaj|dekhbhal|mareez|marij|daktar|davakhana|aspatal|haspatal|garbh|pregnent|ro\s+raha|ro\s+rahi|khana\s+nahi|"
    r"neend\s+nahi|gir\s+gay|gir\s+gai|behosh|saans|sans|sar\s+dard|sir\s+dard|kamar|ghutn)\w*",
    r"(kabz|constipat|acne|pimple|muhas|period|mahwari|aankh|eye|kaan|ear|naak|nose|gala|throat|daant|tooth|teeth|"
    r"skin|chamdi|hair|nail|urin|peshab|stool|potty|concentrat|dhyaan|irritab|chidchid|memory|forget|bhool|anxi|stress|"
    r"depress|udaas|sleep|pill|tablet|goli|dawai|dawa|poison|zeher|zahar|burn|jal\s+gay|heart|dil|chest|seen[ae]|haath|hand|"
    r"arm|pair|leg|foot|feet|back|pet|stomach|tummy|belly|head|face|chehr|mouth|muh|munh|lips|hont|tongue|body|sharir|"
    r"badan|blood|khoon|bp|shaking|kaanp|tremor|numb|sunn|lump|gaanth|thirst|pyaas|lakwa|stroke|fit|daura|chhale|ulcer|"
    r"mucus|balgam|sneez|cheenk|tel\s+pee|kerosene|tezaab|acid|bijli|current|shock|jhatka)\w*",
    r"कब्ज़|कब्ज|मुहांसे|पीरियड|आँख|आंख|कान|नाक|गला|दाँत|दांत|त्वचा|बाल|पेशाब|ध्यान|चिड़चिड़|भूल|तनाव|उदास|नींद|गोली|दवा|ज़हर|जहर|"
    r"जल\s*ग|दिल|सीने|सीना|हाथ|पैर|पीठ|चेहरा|चेहरे|मुँह|मुंह|होंठ|जीभ|शरीर|बदन|खून|बीपी|शुगर|काँप|कांप|सुन्न|गांठ|प्यास|लकवा|दौरा|छाले|तेज़ाब|तेजाब|केरोसिन|करंट|हड्डी|टूट",
    r"तबीयत|बीमार|तकलीफ|दर्द|बुखार|खांसी|खाँसी|जुकाम|उल्टी|दस्त|चक्कर|कमज़ोरी|कमजोरी|चोट|घाव|खून|सूजन|खुजली|जलन|पेशाब|"
    r"इलाज|देखभाल|मरीज़|मरीज|डॉक्टर|नर्स|अस्पताल|गर्भ|साँस|सांस|बेहोश|ठीक नहीं|सिर|पेट|घुटन|कमर|इंजेक्शन|ड्रेसिंग",
)
MEDICINE_ASK = _rx(
    r"\b(which|what)\s+(medicine|medication|tablet|pill|drug|antibiotic|syrup)s?\b", r"\bdos(e|age)\b",
    r"\b(prescribe|prescription)\b", r"\bwhat\s+(disease|illness|condition)\b", r"\bdiagnos\w*", r"\bwhat\s+do\s+i\s+have\b",
    r"\bis\s+it\s+(cancer|covid|dengue|malaria|tb)\b",
    r"\b(kaunsi|kaun\s+si|konsi|kon\s+si|kya)\s+(dawai|dawa|dava|davai|goli|tablet|medicine)\b", r"\b(dawai|dawa|goli|tablet)\s+(\S+\s+)?(lun|loon|du|dun|batao|bataiye|bataye|lena|leni|chahiye)\b",
    r"\bkitni\s+(goli|tablet|dose)\b", r"\b(kya|kaunsi|kaun\s+si|konsi)\s+(bimari|bimaari|beemari|rog)\b", r"\bmujhe\s+kya\s+hua\s+hai\b",
    r"कौन\s*सी\s*दवा|कौनसी\s*दवा|दवाई?\s*बताओ|कितनी\s*गोली|क्या\s*बीमारी|कौन\s*सी\s*बीमारी|मुझे\s*क्या\s*हुआ",
)
INJECTION = _rx(
    r"\b(ignore|disregard|forget|override|bypass)\b\s+(\S+\s+){0,3}(instruction|rule|prompt|guideline|system|previous|above)s?",
    r"\b(system\s+prompt|developer\s+mode|jailbreak|dan\s+mode|reveal\s+(your\s+)?(prompt|instructions))\b",
    r"\byou\s+are\s+now\b", r"\b(act|behave)\s+as\s+(a|an)\b", r"\bpretend\s+(to\s+be|you)\b", r"</?\s*(system|instruction)s?\s*>",
    r"\b(apne|apni)\s+(rules|instructions|niyam)\s+(bhool|ignore)", r"निर्देश\s*(भूल|अनदेखा)",
)
INSULT = _rx(
    r"\b(stupid|idiot|dumb|useless|shut\s+up|nonsense|bloody|moron|loser|hate\s+you|f+u+c+k\w*|bitch|bastard)\b",
    r"\b(pagal|bewakoof|bevkoof|bakwas|bakwaas|ullu|gadha|gadhe|kutta|kutte|kamina|kameena|harami|chup\s+kar|bekar)\b",
    r"पागल|बेवकूफ|बकवास|उल्लू|गधा|कुत्ता|कमीना|हरामी|चुप\s*कर",
)
GREET = _rx(
    r"^\W*(hi+|hello+|hey+|hii+|helo|yo|namaste|namaskar|namaskaar|pranam|salaam|salam|sat\s+sri\s+akal|ram\s+ram|"
    r"good\s+(morning|afternoon|evening|night)|gm|thanks?|thank\s+you|thanku|thnx|ty|shukriya|dhanyavad|dhanyawad|"
    r"ok+|okay|k|theek\s+hai|thik\s+hai|achha|accha|bye|goodbye|alvida|see\s+you)\b",
    r"\b(kaise\s+ho|kaisi\s+ho|kaise\s+hain|kya\s+haal|kya\s+hal|how\s+are\s+you|how\s+r\s+u|what'?s\s+up|sup|wassup|"
    r"kya\s+kar\s+rahe|who\s+are\s+you|tum\s+kaun|aap\s+kaun|your\s+name|tumhara\s+naam|aapka\s+naam|nice\s+to\s+meet)\b",
    r"नमस्ते|नमस्कार|प्रणाम|धन्यवाद|शुक्रिया|कैसे\s*हो|कैसे\s*हैं|क्या\s*हाल|आप\s*कौन|ठीक\s*है",
)
OFF = _rx(
    r"\b(weather|mausam|baarish|rain\s+today|cricket|match|ipl|score|football|movie|film|song|gaana|gana|music|actor|"
    r"politic|election|modi|rahul\s+gandhi|government|sarkar|news|stock|share\s+market|sensex|bitcoin|crypto|price\s+of|"
    r"coding|code|python|javascript|program|homework|math|maths|exam|recipe|khana\s+banana|cook|joke|chutkula|shayari|"
    r"poem|story|kahani|capital\s+of|who\s+is|who\s+was|history\s+of|translate|girlfriend|boyfriend|shaadi|marriage|"
    r"love|pyaar|date|game|pubg|free\s+fire|instagram|youtube|whatsapp|train|flight|ticket|hotel|job|salary|naukri|"
    r"loan|bank|recharge|mobile\s+number|laptop|computer|phone\s+kharab)\w*",
    r"मौसम|क्रिकेट|मैच|फिल्म|गाना|राजनीति|चुनाव|सरकार|खबर|शेयर|मज़ाक|चुटकुला|कहानी|कविता|नौकरी|पढ़ाई",
)
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")
WORD = re.compile(r"[a-zऀ-ॿ]+", re.I)


def _looks_gibberish(text: str) -> bool:
    t = EMOJI.sub("", clean(text)).strip()
    letters = WORD.findall(t)
    if not letters:
        return True  # only emojis / digits / punctuation
    joined = "".join(letters)
    if len(joined) <= 2:
        return True
    latin = [w for w in letters if re.match(r"[a-z]", w, re.I)]
    if latin:
        # strings like "asdfgh", "qwrtzp": long consonant runs or no vowels at all
        bad = [w for w in latin if (len(w) >= 3 and not re.search(r"[aeiouy]", w, re.I)) or re.search(r"[^aeiouy\W\d]{5,}", w, re.I)]
        if len(bad) >= max(1, len(latin) // 2):
            return True
    return False


GREET_FILLER = set("""hi hii hiii hello helo hey yo namaste namaskar namaskaar pranam salaam salam ram sat sri akal good morning
afternoon evening night gm thanks thank thanku thnx ty you shukriya dhanyavad dhanyawad ok okay k theek thik hai achha accha bye
goodbye alvida see kaise kaisi ho hain kya haal hal how are r u what s up sup wassup kar rahe who tum aap kaun your name tumhara
aapka naam nice to meet babu bhai bhaiya didi dost yaar bro sir madam ji jee aajkal aaj kal etc question sawal sab mera meri mere
main mai is the a an doing today bot chal raha rahi there everyone all dear hum log batao bataiye so much very""".split())
GREET_FILLER |= {"नमस्ते", "नमस्कार", "प्रणाम", "धन्यवाद", "शुक्रिया", "कैसे", "हो", "हैं", "है", "क्या", "हाल", "आप", "तुम", "कौन",
                 "ठीक", "जी", "भाई", "दोस्त"}


def _greeting_only(t: str) -> bool:
    if not GREET.search(t):
        return False
    rest = [w for w in WORD.findall(t.lower()) if w not in GREET_FILLER]
    return len(rest) <= 1


def has_health_signal(text: str) -> bool:
    if extract_slots([text]).symptoms:
        return True
    return bool(HEALTH_WORDS.search(clean(text)) or HEALTH_WORDS.search(normalise(text)))


def _llm_tiebreak(text: str) -> str | None:
    if not llm.available():
        return None
    out = llm.chat_json(
        "You classify messages sent to a health-care routing assistant in India (English/Hindi/Hinglish). "
        f"Reply JSON {{\"class\": one of {list(CLASSES)}}}. A message describing anyone's health problem, symptoms, "
        "injury, or a need for a nurse/doctor/caregiver is health_request.",
        f"Message: \"{text[:500]}\"", max_tokens=30, timeout=3.0)
    c = (out or {}).get("class")
    return c if c in CLASSES else None


def classify(text: str, answering_clinical_question: bool = False) -> str:
    """Domain class of one user turn. Answers to a pending clinical question are always health."""
    t = unicodedata.normalize("NFC", text or "").strip()
    if INJECTION.search(t):
        return ABUSE
    if answering_clinical_question:
        return HEALTH
    if not t:
        return UNCLEAR
    # "which medicine / what disease" without any symptom: we never name medicines or diseases
    if MEDICINE_ASK.search(t):
        return HEALTH if extract_slots([t]).symptoms else MEDICINE
    if has_health_signal(t):
        return HEALTH
    if INSULT.search(t):
        return ABUSE
    if _greeting_only(t):
        return GREETING
    if OFF.search(t):
        return OFF_TOPIC
    if _looks_gibberish(t):
        return UNCLEAR
    # no positive evidence of another class: never block a possible health request.
    # The LLM (if configured) may still recognise small talk / off-topic text; otherwise the pipeline handles it.
    if len(WORD.findall(t)) >= 4:
        return _llm_tiebreak(t) or HEALTH
    return HEALTH


REDIRECTS = {
    GREETING: {
        "en": "Hello! I can only help with health and care. Please tell me who is unwell and what the problem is.",
        "hi": "नमस्ते! मैं सिर्फ़ सेहत से जुड़ी मदद कर सकता हूँ। बताइए, किसकी तबीयत ठीक नहीं है और क्या परेशानी है?",
        "hinglish": "Namaste! Main sirf sehat se judi madad kar sakta hoon. Batayein, kis ki tabiyat theek nahi hai aur kya pareshani hai?",
    },
    OFF_TOPIC: {
        "en": "Sorry, I can only help you find the right health care. Is someone unwell?",
        "hi": "माफ़ कीजिए, मैं सिर्फ़ सही देखभाल ढूँढने में मदद करता हूँ। क्या किसी की तबीयत खराब है?",
        "hinglish": "Maaf kijiye, main sirf health care dhoondhne mein madad karta hoon. Kya kisi ki tabiyat kharab hai?",
    },
    MEDICINE: {
        "en": "I cannot suggest medicines or name an illness. But I can connect you to the right doctor or nurse. Please describe the symptoms.",
        "hi": "मैं दवा या बीमारी का नाम नहीं बता सकता। लेकिन सही डॉक्टर या नर्स तक पहुँचाने में मदद कर सकता हूँ। लक्षण बताइए।",
        "hinglish": "Main dawai ya bimari ka naam nahi bata sakta. Lekin sahi doctor ya nurse tak pahunchane mein madad kar sakta hoon. Symptoms batayein.",
    },
    UNCLEAR: {
        "en": "I did not understand that. Please describe the problem, who it is for, and since when. For example: \"My father has had a fever for 2 days\".",
        "hi": "मैं समझ नहीं पाया। कृपया बताइए क्या परेशानी है, किसे है और कब से। जैसे: \"पापा को दो दिन से बुखार है\"।",
        "hinglish": "Main samajh nahi paaya. Batayein kya pareshani hai, kise hai aur kab se. Jaise: \"Papa ko do din se bukhar hai\".",
    },
    ABUSE: {
        "en": "I am here only to help find health care. If someone is unwell, please describe the problem.",
        "hi": "मैं सिर्फ़ सेहत की देखभाल ढूँढने में मदद के लिए हूँ। अगर किसी की तबीयत खराब है, तो परेशानी बताइए।",
        "hinglish": "Main sirf health care dhoondhne mein madad ke liye hoon. Agar kisi ki tabiyat kharab hai, to pareshani batayein.",
    },
}


def redirect_text(domain_class: str, lang: str) -> str:
    m = REDIRECTS.get(domain_class, REDIRECTS[UNCLEAR])
    return m.get(lang) or m["en"]


REDIRECT_TEXTS = {v for m in REDIRECTS.values() for v in m.values()}
