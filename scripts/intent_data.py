"""Generated training rows for the intent classes of the input-type classifier (no real patients, no LLM):
joke_or_lyric | hypothetical | absurd_or_impossible | animal_patient | deceased_patient | past_event, plus real
health sentences that look like them (hard negatives: "seene mein dard", "kutte ne kaata", "breakup ke baad neend
nahi aati"). Song references are short titles / hooks only.

Each class has many sentence frames (the group for the split) that draw from shared marker lists, so a frame unseen
in training still carries known markers ("mari hui", "agar", "pichle saal", an animal as the patient)."""
from __future__ import annotations

import random

PEOPLE = ["papa", "mummy", "dadi", "dada", "nani", "nana", "beta", "beti", "didi", "bhai", "meri wife", "mere pati",
          "chacha", "mausi", "bua", "tauji"]
PEOPLE_EN = ["my father", "my mother", "grandma", "grandpa", "my son", "my daughter", "my wife", "my husband", "my uncle", "my aunt"]
PEOPLE_HI = ["पापा", "मम्मी", "दादी", "दादा", "नानी", "बेटे", "बेटी", "भाई", "चाचा"]
SYM = ["bukhar", "seene mein dard", "saans lene mein dikkat", "heart attack", "ulti", "sar dard", "pet dard", "khansi",
       "chakkar", "lakwa", "daura", "dast", "kamar dard", "zukaam", "kamzori"]
SYM_EN = ["fever", "chest pain", "trouble breathing", "a heart attack", "vomiting", "a headache", "stomach pain", "a cough",
          "a stroke", "a seizure", "diarrhoea", "dizziness"]
SYM_HI = ["बुखार", "सीने में दर्द", "साँस की तकलीफ", "हार्ट अटैक", "उल्टी", "सिर दर्द", "पेट दर्द", "खांसी", "चक्कर"]
ANIMALS = ["kutte", "kutta", "billi", "gaay", "bhains", "bakri", "ullu", "tote", "ghode", "murgi", "bandar", "khargosh",
           "kabootar", "chidiya", "bail"]
ANIMALS_EN = ["dog", "cat", "cow", "goat", "parrot", "horse", "puppy", "kitten", "rabbit", "hamster", "buffalo", "hen"]
ANIMALS_HI = ["कुत्ते", "बिल्ली", "गाय", "बकरी", "तोते", "घोड़े", "भैंस"]
OBJECTS = ["phone", "laptop", "fridge", "tv", "gaadi", "bike", "pankhe", "computer", "ghadi", "kursi", "AC", "cooler", "mobile"]
NATURE = ["chand", "suraj", "baadal", "ped", "pahad", "nadi", "taaron"]
ODD_SITES = ["kidney", "pair", "nakhoon", "baal", "daant", "kaan", "ungli", "ghutne", "aankh", "kohni", "edi"]
DEAD = ["mari hui", "mare hue", "swargiya", "late", "jo guzar chuke", "jo ab nahi rahe", "marhoom", "guzre hue"]
DEAD_EN = ["my late", "my dead", "my deceased", "my departed"]
DEAD_HI = ["मरी हुई", "मरे हुए", "स्वर्गीय", "गुज़रे हुए"]
PAST = ["pichle saal", "do saal pehle", "bachpan mein", "kai saal pehle", "pichle mahine", "2019 mein", "das saal pehle"]
PAST_EN = ["last year", "two years ago", "as a child", "years ago", "back in 2018", "a decade ago"]
PAST_HI = ["पिछले साल", "दो साल पहले", "बचपन में", "कई साल पहले"]
COND = ["agar", "maan lo", "suppose", "agar kabhi", "kabhi agar", "agr"]
COND_EN = ["what if", "suppose", "in case", "if ever", "hypothetically, if"]
COND_HI = ["अगर", "मान लो", "यदि"]
SONGS = ["dil mein mere hai dard disco", "dard-e-disco", "dil to pagal hai", "dil chahta hai", "dil se re",
         "dil hai ki manta nahi", "tujhe dekha to ye jaana sanam", "kal ho na ho", "jiya jale jaan jale", "chaiyya chaiyya",
         "dil deewana", "ae dil hai mushkil", "dil dhadakne do", "dhak dhak karne laga", "mera dil bhi kitna pagal hai",
         "dil ka kya kasoor", "tere bina dil nahi lagta", "sanam re", "pehla nasha", "tum hi ho", "channa mereya",
         "dil na jaane kyun", "pal pal dil ke paas", "dil diyan gallan", "dil ibadat", "kajra re", "dil cheez kya hai",
         "o saathi re", "suraj hua maddham", "dil tu hi bataa", "dil ko karaar aaya", "dil laga liya maine",
         "teri meri prem kahani", "dil todne wale", "heart attack wala gaana", "fever wala gaana", "दिल तो पागल है",
         "दिल चाहता है", "तुम ही हो"]
FUN = ["lol", "😂", "haha", "🤣", "hehe", "😜", "lmao", "🎵", "💃", "🎶"]
HEARTBREAK = ["mera dil toot gaya", "dil toot gaya yaar", "uski yaad mein dil mein dard hai", "breakup ho gaya, dil tut gaya",
              "usne mera dil tod diya", "my heart is broken", "heartbroken after the breakup", "मेरा दिल टूट गया",
              "उसकी याद में दिल दुखता है", "dil dukhta hai uski yaad mein", "pyaar mein dil toot gaya",
              "she broke my heart", "dil ke tukde ho gaye"]


def intent_rows(rng: random.Random, per_frame: int = 30) -> list[dict]:
    rows: list[dict] = []

    def r(xs):
        return rng.choice(xs)

    def frames(label: str, fs: list, n: int = per_frame):
        for i, fn in enumerate(fs):
            for _ in range(n):
                rows.append({"text": fn(), "label": label, "group": f"{label}_{i}"})

    frames("joke_or_lyric", [
        lambda: r(SONGS), lambda: f"{r(SONGS)} {r(FUN)}", lambda: f"{r(SONGS)} wala gaana bajao",
        lambda: f"{r(SONGS)} ki line yaad aa gayi {r(FUN)}", lambda: f"gaana: {r(SONGS)}",
        lambda: f"doctor doctor, mere {r(OBJECTS)} ko {r(SYM)} hai {r(FUN)}",
        lambda: f"{r(['exam ka result', 'bijli ka bill', 'match ka last over', 'crush ka message', 'boss ka mail'])} dekh ke {r(['heart attack aa gaya', 'saans ruk gayi', 'bukhar aa gaya'])} {r(FUN)}",
        lambda: f"hans hans ke {r(['pet dard ho gaya', 'saans ruk gayi', 'aansu aa gaye'])} {r(FUN)}",
        lambda: f"{r(['monday', 'office', 'school', 'shaadi'])} ka naam sunke {r(SYM)} ho jaata hai {r(FUN)}",
        lambda: f"this {r(['meme', 'joke', 'video', 'reel'])} gave me {r(['a heart attack', 'a fever', 'a stroke'])} {r(FUN)}",
        lambda: f"i'm dying of {r(['laughter', 'boredom', 'cringe'])} {r(FUN)}",
        lambda: f"ek joke sunao {r(['dil', 'doctor', 'bukhar', 'hospital'])} wala", lambda: r(HEARTBREAK),
        lambda: f"{r(HEARTBREAK)} {r(['', '💔', 'yaar', 'bro'])}".strip(),
        lambda: f"मज़ाक: डॉक्टर साहब मेरे {r(['फोन', 'लैपटॉप'])} को {r(SYM_HI)} है {r(FUN)}",
    ])
    frames("absurd_or_impossible", [
        lambda: f"{r(ODD_SITES)} mein heart attack aa gaya", lambda: f"mere {r(ODD_SITES)} mein saans nahi aa rahi",
        lambda: f"{r(ODD_SITES)} ko lakwa maar gaya", lambda: f"mere {r(OBJECTS)} ko {r(SYM)} hai",
        lambda: f"{r(OBJECTS)} ki saans ruk gayi", lambda: f"my {r(['phone', 'laptop', 'car', 'tv', 'fridge'])} has {r(SYM_EN)}",
        lambda: f"heart attack in my {r(['kidney', 'toe', 'hair', 'nail', 'elbow', 'ear'])}",
        lambda: f"{r(NATURE)} ko {r(SYM)} ho gaya", lambda: f"मेरे {r(['फोन', 'लैपटॉप', 'फ्रिज', 'टीवी'])} को {r(SYM_HI)} है",
        lambda: f"{r(['बाल', 'नाखून', 'किडनी', 'एड़ी'])} में हार्ट अटैक", lambda: f"mere {r(OBJECTS)} ka dil toot gaya",
        lambda: f"{r(['baal', 'nakhoon'])} mein {r(['bukhar', 'dard', 'khoon'])} aa raha hai",
    ])
    frames("animal_patient", [
        lambda: f"{r(ANIMALS)} ko {r(SYM)} hai", lambda: f"meri {r(['billi', 'gaay', 'bakri', 'murgi', 'bhains'])} {r(['bimaar hai', 'kuch kha nahi rahi', 'ulti kar rahi hai', 'chal nahi pa rahi'])}",
        lambda: f"{r(ANIMALS)} ke {r(['dil', 'pet', 'pair', 'aankh'])} mein {r(['dard', 'heart attack', 'soojan'])}",
        lambda: f"my {r(ANIMALS_EN)} {r(['is vomiting', 'has a fever', 'is not eating', 'is limping', 'is sick'])}",
        lambda: f"our {r(ANIMALS_EN)} {r(['has diarrhoea', 'cannot breathe properly', 'is coughing', 'got hurt'])}",
        lambda: f"{r(ANIMALS_HI)} को {r(SYM_HI)} है", lambda: f"hamare {r(['kutte', 'tote', 'ghode', 'bail'])} ki tabiyat kharab hai",
        lambda: f"{r(['ullu', 'chidiya', 'kabootar'])} ki {r(['aankh', 'pankh', 'taang'])} mein chot hai",
        lambda: f"mere pet {r(['dog', 'cat', 'parrot'])} ko {r(SYM)} hai", lambda: f"{r(ANIMALS)} {r(['bimaar', 'sust', 'udaas'])} hai, kya karun",
        lambda: f"मेरी {r(['बिल्ली', 'गाय', 'बकरी'])} बीमार है", lambda: f"the {r(ANIMALS_EN)} at home seems to have {r(SYM_EN)}",
    ])
    frames("deceased_patient", [
        lambda: f"{r(DEAD)} {r(PEOPLE)} ko {r(SYM)} hai", lambda: f"{r(DEAD)} {r(PEOPLE)} ko abhi {r(SYM)} ho raha hai",
        lambda: f"mere {r(DEAD)} {r(PEOPLE)} ko {r(SYM)} aa gaya", lambda: f"{r(DEAD_EN)} {r(['grandfather', 'grandmother', 'uncle', 'father'])} has {r(SYM_EN)} now",
        lambda: f"{r(DEAD_HI)} {r(PEOPLE_HI)} को {r(SYM_HI)} है", lambda: f"{r(DEAD)} {r(PEOPLE)} ki {r(['saans nahi aa rahi', 'tabiyat kharab hai'])}",
        lambda: f"{r(DEAD_EN)} {r(['mother', 'brother', 'aunt'])} is having {r(SYM_EN)}", lambda: f"{r(PEOPLE)} {r(['jo mar chuke hain', 'jo guzar gaye'])} unko {r(SYM)} hai",
        lambda: f"{r(DEAD)} {r(PEOPLE)} ke seene mein dard", lambda: f"{r(DEAD_HI)} {r(PEOPLE_HI)} की साँस नहीं आ रही",
    ])
    frames("past_event", [
        lambda: f"{r(PAST)} {r(PEOPLE)} ko {r(SYM)} hua tha, ab theek hain", lambda: f"{r(PAST)} mujhe {r(SYM)} tha",
        lambda: f"{r(PAST)} mujhe {r(SYM)} hota tha", lambda: f"{r(PAST_EN)} {r(PEOPLE_EN)} had {r(SYM_EN)}, now fine",
        lambda: f"{r(PAST_EN)} I had {r(SYM_EN)}", lambda: f"{r(PAST_HI)} {r(PEOPLE_HI)} को {r(SYM_HI)} हुआ था",
        lambda: f"padosi ko {r(PAST)} {r(SYM)} hua tha", lambda: f"{r(PEOPLE)} ki death {r(PAST)} {r(['heart attack', 'lakwa', 'cancer'])} se hui thi",
        lambda: f"{r(PAST)} {r(SYM)} ka ilaaj hua tha, ab koi dikkat nahi", lambda: f"{r(PAST_EN)} my {r(['dad', 'mom', 'uncle'])} had {r(SYM_EN)}; he is okay now",
    ])
    frames("hypothetical", [
        lambda: f"{r(COND)} {r(PEOPLE)} ko {r(SYM)} ho jaye to kya karein?", lambda: f"{r(COND)} {r(['saans ruk jaaye', 'koi behosh ho jaye', 'heart attack aa jaye', 'khoon na ruke'])} to?",
        lambda: f"{r(COND)} {r(SYM)} ho jaye to kya karna chahiye", lambda: f"{r(COND_EN)} someone has {r(SYM_EN)}?",
        lambda: f"{r(COND_EN)} {r(PEOPLE_EN)} gets {r(SYM_EN)}, what should we do?", lambda: f"{r(COND_HI)} {r(SYM_HI)} हो जाए तो क्या करें?",
        lambda: f"{r(COND)} koi {r(['behosh', 'gir', 'bimaar'])} ho jaye, tab kya karein", lambda: f"in case of {r(SYM_EN)}, what is the first aid?",
        lambda: f"{r(COND)} kabhi {r(SYM)} ho to kaun sa doctor?", lambda: f"{r(COND_EN)} a child has {r(SYM_EN)}, which doctor?",
    ])
    he = [lambda: f"{r(PEOPLE)} ke seene mein dard ho raha hai", lambda: f"{r(PEOPLE)} ko abhi heart attack aaya hai",
          lambda: f"{r(PEOPLE)} ki saans nahi aa rahi", lambda: "mere dil ki dhadkan bahut tez hai",
          lambda: "mera dil ghabra raha hai aur paseena aa raha hai", lambda: f"{r(['kutte', 'billi', 'bandar'])} ne {r(PEOPLE)} ko kaata",
          lambda: "gaana gaate gaate gala kharab ho gaya", lambda: "breakup ke baad se neend nahi aati aur bahut udaas rehti hoon",
          lambda: f"dadi ki death ke baad se papa ko {r(SYM)} hai", lambda: f"{r(PEOPLE_EN)} has {r(SYM_EN)} right now",
          lambda: f"{r(PEOPLE_HI)} को अभी {r(SYM_HI)} है", lambda: f"lol mujhe {rng.randint(2, 5)} din se {r(['bukhar', 'khansi', 'sar dard'])} hai",
          lambda: f"kal se {r(PEOPLE)} ko {r(SYM)} hai", lambda: f"my {r(['dog', 'cat'])} bit {r(PEOPLE_EN)}",
          lambda: "uski yaad mein neend nahi aati, bahut rona aata hai", lambda: f"{r(PEOPLE)} ko {rng.randint(2, 6)} din se {r(SYM)} hai",
          lambda: f"pichle saal heart attack aaya tha, aaj phir {r(['seene mein dard', 'saans ki dikkat'])} hai"]
    for i, fn in enumerate(he):
        for _ in range(30):
            rows.append({"text": fn(), "label": "health", "group": f"health_lookalike_{i}"})
    return rows
