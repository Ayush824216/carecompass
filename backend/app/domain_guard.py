"""Domain guard: keep the assistant strictly on health-care routing.

Runs after language detection and the safety gate (a red flag always wins, so "hello, papa behosh ho gaye"
still goes to the emergency path). Classifies the latest user turn into:

  health_request                 -> normal pipeline
  greeting_smalltalk             -> polite redirect
  off_topic                      -> polite redirect
  unclear_or_gibberish           -> "no health problem found": ask what, who, since when (never a clinical question)
  math_or_code                   -> "not a health question"
  unknown_term                   -> "I do not recognise this name; describe the symptoms" (never pretend to know it)
  medicine_or_diagnosis_request  -> "I can't name medicines or diseases, but I can route you"
  abusive_or_prompt_injection    -> neutral redirect; injected instructions are never followed

Fast multilingual rules first; the LLM is only a tie-breaker for ambiguous multi-word text, with a timeout and a
rules-only fallback. A message that mixes small talk and a health problem is a health_request.

Evidence gate: health_request needs at least one evidence span (app.evidence) in the user's own words. A person
mention alone ("abba", "papa") is not evidence, and text with no evidence of any class is unclear, not health.
"""
from __future__ import annotations

import re
import unicodedata

from . import llm
from . import evidence
from .intake import extract_slots
from .lang import clean

HEALTH = "health_request"
GREETING = "greeting_smalltalk"
OFF_TOPIC = "off_topic"
UNCLEAR = "unclear_or_gibberish"
MEDICINE = "medicine_or_diagnosis_request"
ABUSE = "abusive_or_prompt_injection"
MATH = "math_or_code"
UNKNOWN_TERM = "unknown_term"
GIVE_UP = "abstain_give_up"  # pipeline-only: after 3 non-health turns in a row we stop asking
CLASSES = (HEALTH, GREETING, OFF_TOPIC, UNCLEAR, MEDICINE, ABUSE, MATH, UNKNOWN_TERM)


def _rx(*parts: str) -> re.Pattern:
    return re.compile("|".join(parts), re.I)


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
MATH_CODE = _rx(
    r"^[\s\d.,+\-*/x×÷^=()%<>!?]*\d\s*[+\-*/x×÷^=%]\s*[\d(][\s\d.,+\-*/x×÷^=()%?]*$",
    r"\b(solve|calculate|integrate|derivative|equation|kitna\s+hota|kitne\s+hote|plus|minus|times|multiply|divided\s+by)\b.*\d"
    r"|\d.*\b(plus|minus|guna|into)\b",
    r"\b(def|function|return|import|console\.log|printf?|elif|lambda|var|const|let)\b.*[(){}=;:]",
    r"[{};]\s*$", r"=>|#include|</?\w+>|\bselect\b.+\bfrom\b",
)
BP_LIKE = re.compile(r"^\s*\d{2,3}\s*/\s*\d{2,3}\s*$")  # "140/90" is a reading, not a sum
# a word that looks like a disease name but is in none of our lexicons ("xyzitis")
UNKNOWN_MED = re.compile(r"\b[a-z]{2,}(itis|osis|emia|aemia|oma|pathy|algia|plegia|iasis|rrhoea|rrhea|ectomy|uria|cele)\b", re.I)
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
    """At least one evidence span in the user's own words (symptom, complaint or red flag)."""
    return evidence.has_evidence([text])


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
    if MATH_CODE.search(t) and not BP_LIKE.search(t):
        return MATH
    if OFF.search(t):
        return OFF_TOPIC
    if UNKNOWN_MED.search(t):
        return UNKNOWN_TERM
    from . import input_type  # learned classifier + simple gibberish features (lexicon share, repeats, vowels)
    if _looks_gibberish(t) or input_type.looks_gibberish(t):
        return UNCLEAR
    learned = input_type.predict(t)
    if learned in (GREETING, OFF_TOPIC, MATH, UNCLEAR):
        return learned
    # no evidence span: never start clinical questioning (evidence gate); ask what, who and since when instead
    if len(WORD.findall(t)) >= 4:
        c = _llm_tiebreak(t)
        if c and c != HEALTH:
            return c
    return UNCLEAR


REDIRECTS = {
    GREETING: {
        "en": "Hello! I can only help with health and care. Please tell me who is unwell and what the problem is.",
        "hi": "नमस्ते! मैं सिर्फ़ सेहत से जुड़ी मदद कर सकता हूँ। बताइए, किसकी तबीयत ठीक नहीं है और क्या परेशानी है?",
        "hinglish": "Namaste! Main sirf sehat se judi madad kar sakta hoon. Batayein, kis ki tabiyat theek nahi hai aur kya pareshani hai?",
    },
    OFF_TOPIC: {
        "en": "This does not look like a health question. I can only help with health and care.",
        "hi": "यह सेहत का सवाल नहीं लगता। मैं सिर्फ़ सेहत से जुड़ी मदद करता हूँ।",
        "hinglish": "Ye health ka sawaal nahi lagta. Main sirf sehat se judi madad karta hoon.",
    },
    UNKNOWN_TERM: {
        "en": "I do not recognise this name. Please describe the symptoms.",
        "hi": "मैं इस नाम को नहीं पहचानता। अपने लक्षण बताइए।",
        "hinglish": "Main is naam ko nahi pehchaanta. Apne symptoms batayein.",
    },
    MEDICINE: {
        "en": "I cannot suggest medicines or name an illness. But I can connect you to the right doctor or nurse. Please describe the symptoms.",
        "hi": "मैं दवा या बीमारी का नाम नहीं बता सकता। लेकिन सही डॉक्टर या नर्स तक पहुँचाने में मदद कर सकता हूँ। लक्षण बताइए।",
        "hinglish": "Main dawai ya bimari ka naam nahi bata sakta. Lekin sahi doctor ya nurse tak pahunchane mein madad kar sakta hoon. Symptoms batayein.",
    },
    UNCLEAR: {
        "en": "I could not find a health problem in this message. What is the problem, who has it, and since when?",
        "hi": "इस संदेश में मुझे कोई सेहत की परेशानी समझ नहीं आई। क्या तकलीफ है, किसे है, और कब से?",
        "hinglish": "Is message mein mujhe koi health problem samajh nahi aayi. Kya takleef hai, kisko, aur kab se?",
    },
    ABUSE: {
        "en": "I am here only to help find health care. If someone is unwell, please describe the problem.",
        "hi": "मैं सिर्फ़ सेहत की देखभाल ढूँढने में मदद के लिए हूँ। अगर किसी की तबीयत खराब है, तो परेशानी बताइए।",
        "hinglish": "Main sirf health care dhoondhne mein madad ke liye hoon. Agar kisi ki tabiyat kharab hai, to pareshani batayein.",
    },
}


REDIRECTS[MATH] = REDIRECTS[OFF_TOPIC]
GIVE_UP_TEXT = {
    "en": "I am not able to understand this. If someone is unwell, please talk to a doctor; in an emergency, call 112.",
    "hi": "मैं यह बात समझ नहीं पा रहा। अगर तबीयत खराब है तो डॉक्टर से बात करें, इमरजेंसी में 112 पर कॉल करें।",
    "hinglish": "Main is baat ko samajh nahi pa raha. Agar tabiyat kharab hai to doctor se baat karein, emergency mein 112.",
}
MAX_UNCLEAR_TURNS = 3


def give_up_text(lang: str) -> str:
    return GIVE_UP_TEXT.get(lang) or GIVE_UP_TEXT["en"]


def redirect_text(domain_class: str, lang: str) -> str:
    m = REDIRECTS.get(domain_class, REDIRECTS[UNCLEAR])
    return m.get(lang) or m["en"]


REDIRECT_TEXTS = {v for m in REDIRECTS.values() for v in m.values()} | set(GIVE_UP_TEXT.values())
