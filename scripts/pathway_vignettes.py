"""Hand-written pathway vignette templates (docs/CLINICAL_PATHWAYS.md), labelled from the spec tables.

Each template: (template_id, pathway, stage, care_type, urgency, who, en, hinglish, hindi).
who: adult | elder (65+, unambiguous) | child | none. Placeholders: {S} {has} (English subject), {W} (Hinglish /
Hindi "X ko"), and [a|b|c] alternatives that never change the label. Labels are authored, not produced by the
pathway engine, so evaluation measures how well the engine and the ML models read new phrasings.
"""
from __future__ import annotations

import random
import re

GP, PM, NU, SP, EM = "gp_teleconsult", "paramedic_home_visit", "nurse_home_visit", "specialist_referral", "emergency_referral"
R, SD, IM = "routine", "same_day", "immediate"

EN_WHO = {
    "adult": [("I", "have"), ("My wife", "has"), ("My husband", "has"), ("My brother", "has"), ("My sister", "has"),
              ("My father", "has"), ("My mother", "has")],
    "elder": [("My 72 year old father", "has"), ("My grandmother", "has"), ("My grandfather", "has"),
              ("My 68 year old mother", "has")],
    "child": [("My 6 year old son", "has"), ("My 8 year old daughter", "has"), ("My child", "has")],
}
HG_W = {"adult": ["Mujhe", "Meri wife ko", "Mere husband ko", "Bhai ko", "Didi ko", "Papa ko", "Mummy ko"],
        "elder": ["Dadi ko", "Dada ji ko", "Nani ko", "72 saal ke papa ko"],
        "child": ["6 saal ke bete ko", "Beti ko", "Bachche ko"]}
HI_W = {"adult": ["मुझे", "मेरी पत्नी को", "मेरे पति को", "भाई को", "दीदी को", "पापा को", "मम्मी को"],
        "elder": ["दादी को", "दादाजी को", "नानी को", "72 साल के पापा को"],
        "child": ["छह साल के बेटे को", "बेटी को", "बच्चे को"]}

T = [
    # ------------------------------------------------ FEVER
    ("F01", "fever", "S0", GP, R, "adult", "{S} {has} had a mild fever since yesterday, around [100|99.8], eating and drinking normally",
     "{W} kal se halka bukhar hai, [100|99] tha, khana peena theek hai", "{W} कल से हल्का बुखार है, [100|99] था, खाना पीना ठीक है"),
    ("F02", "fever", "S1", PM, SD, "adult", "{S} {has} had fever for [2|3] days with cough",
     "{W} [2|do|teen] din se bukhar hai aur khansi bhi", "{W} [दो|तीन] दिन से बुखार है और खांसी भी"),
    ("F03", "fever", "S1", PM, SD, "adult", "{S} {has} had high fever for [4|5] days with pain behind the eyes and body ache",
     "{W} [4|5] din se tez bukhar, aankhon ke peeche dard aur badan toot raha hai", "{W} [चार|पाँच] दिन से तेज़ बुखार, आँखों के पीछे दर्द और बदन टूट रहा है"),
    ("F04", "fever", "S1", PM, SD, "adult", "{S} gets fever with chills every evening, then sweating",
     "{W} roz shaam ko thand lagkar bukhar aata hai, phir paseena", "{W} रोज़ शाम को ठंड लगकर बुखार आता है, फिर पसीना"),
    ("F05", "fever", "S1", PM, SD, "adult", "{S} {has} a fever of [103|103.5] since this morning",
     "{W} subah se [103|103.5] bukhar hai", "{W} सुबह से [103|103.5] बुखार है"),
    ("F06", "fever", "S2", GP, SD, "adult", "Platelets are [80000|75k|60,000] after the fever and there is stomach pain",
     "Bukhar ke baad platelets [80 hazaar|75k|60000] aaye, pet mein dard bhi hai", "बुखार के बाद प्लेटलेट्स [80 हज़ार|75000] आए, पेट में दर्द भी है"),
    ("F07", "fever", "S2", GP, SD, "adult", "{S} {has} had fever for [8|9|10] days that keeps rising, with stomach pain",
     "{W} [8|9|10] din se bukhar hai, roz badhta hai, pet dard bhi", "{W} [आठ|नौ|दस] दिन से बुखार है, रोज़ बढ़ता है, पेट दर्द भी"),
    ("F08", "fever", "S2", GP, SD, "adult", "{S} {has} fever with burning urine and pain in the side of the back",
     "{W} bukhar aur peshab mein jalan hai, kamar ke side mein dard", "{W} बुखार और पेशाब में जलन है, कमर के बगल में दर्द"),
    ("F09", "fever", "S2", GP, SD, "adult", "{S} {has} a temperature of [104|104.5] since yesterday",
     "{W} kal se [104|104.5] bukhar hai", "{W} कल से [104|104.5] बुखार है"),
    ("F10", "fever", "S2", SP, SD, "adult", "{S} {has} had fever on and off for [3 weeks|a month]",
     "{W} [3 hafte|mahine bhar] se bukhar aa jaa raha hai", "{W} [तीन हफ्ते|एक महीने] से बुखार आ जा रहा है"),
    ("F11", "fever", "S3", EM, IM, "adult", "The platelet count is [15000|18k|12,000] after the fever",
     "Bukhar ke baad platelets [15000|18 hazaar|12k] reh gaye", "बुखार के बाद प्लेटलेट्स [15000|18000] रह गए"),
    ("F12", "fever", "S3", EM, IM, "adult", "{S} {has} fever and the neck has become stiff",
     "{W} bukhar hai aur gardan akad gayi hai", "{W} बुखार है और गर्दन अकड़ गई है"),
    ("F13", "fever", "S3", EM, IM, "adult", "{S} {has} fever, yellow eyes and is very drowsy now",
     "{W} bukhar ke saath aankhen peeli aur ab bahut sust hain", "{W} बुखार के साथ आँखें पीली और अब बहुत सुस्ती है"),
    ("F14", "fever", "S3", EM, IM, "none", "My [1|2] month old baby has a fever of [100.6|101]",
     "Mere [1|2] mahine ke bachche ko [100.6|101] bukhar hai", "मेरे [एक|दो] महीने के बच्चे को [100.6|101] बुखार है"),
    ("F15", "fever", "S2", PM, SD, "elder", "{S} {has} had fever for [2|3] days and feels weak",
     "{W} [2|3] din se bukhar hai, kamzori hai", "{W} [दो|तीन] दिन से बुखार है, कमज़ोरी है"),
    ("F16", "fever", "S2", PM, SD, "elder", "{S} {has} high fever and joint pain so bad they cannot walk",
     "{W} tez bukhar aur ghutno mein itna dard ki chal nahi pa rahe", "{W} तेज़ बुखार और घुटनों में इतना दर्द कि चल नहीं पा रहे"),
    ("F17", "fever", "S1", PM, SD, "none", "My wife is [5|6] months pregnant and has had a mild fever since yesterday",
     "Meri wife [5|6] mahine pregnant hai, kal se halka bukhar hai", "मेरी पत्नी [पाँच|छह] महीने की गर्भवती है, कल से हल्का बुखार है"),
    ("F18", "fever", "S2", PM, SD, "adult", "{S} {has} diabetes and has had fever for [2|3] days",
     "{W} sugar hai aur [2|3] din se bukhar hai", "{W} शुगर है और [दो|तीन] दिन से बुखार है"),
    # ------------------------------------------------ COUGH
    ("C01", "cough", "S0", GP, R, "adult", "{S} {has} had a dry cough for [4|5|6] days, nothing else",
     "{W} [4|5|6] din se sukhi khansi hai, aur kuch nahi", "{W} [चार|पाँच] दिन से सूखी खांसी है, और कुछ नहीं"),
    ("C02", "cough", "S0", GP, R, "adult", "{S} {has} a cough with white phlegm for [3|4] days, no fever",
     "{W} [3|4] din se balgam wali khansi hai, bukhar nahi hai", "{W} [तीन|चार] दिन से बलगम वाली खांसी है, बुखार नहीं है"),
    ("C03", "cough", "S1", PM, SD, "adult", "{S} {has} cough with phlegm and fever for [3|4] days",
     "{W} balgam wali khansi aur [3|4] din se bukhar hai", "{W} बलगम वाली खांसी और [तीन|चार] दिन से बुखार है"),
    ("C04", "cough", "S1", PM, SD, "child", "{S} {has} had a cough for [2|3] days",
     "{W} [2|3] din se khansi hai", "{W} [दो|तीन] दिन से खांसी है"),
    ("C05", "cough", "S1", PM, SD, "adult", "{S} {has} had yellow phlegm for [10|12] days",
     "{W} [10|12] din se peela balgam aa raha hai", "{W} [दस|बारह] दिन से पीला बलगम आ रहा है"),
    ("C06", "cough", "S1", GP, SD, "adult", "{S} {has} had a cough for a month, no fever",
     "{W} mahine bhar se khansi hai, bukhar nahi", "{W} एक महीने से खांसी है, बुखार नहीं"),
    ("C07", "cough", "S2", SP, SD, "adult", "{S} {has} had a cough for [3|4] weeks with night sweats and weight loss",
     "{W} [3|4] hafte se khansi, raat ko paseena aur wazan kam ho gaya", "{W} [तीन|चार] हफ्ते से खांसी, रात को पसीना और वज़न कम हो गया"),
    ("C08", "cough", "S2", SP, SD, "adult", "{S} saw thin streaks of blood in the phlegm",
     "{W} balgam mein thode khoon ke dhaage dikhe", "{W} बलगम में थोड़े खून के धागे दिखे"),
    ("C09", "cough", "S2", SP, SD, "adult", "{S} {has} asthma and is wheezing, the inhaler helps only a little",
     "{W} asthma hai, seeti jaisi awaaz aa rahi, inhaler se thoda hi aaram", "{W} दमा है, सीटी जैसी आवाज़ आ रही है, इनहेलर से थोड़ा ही आराम"),
    ("C10", "cough", "S3", EM, IM, "adult", "{S} coughed up a spoonful of blood",
     "{W} khansi mein chammach bhar khoon aaya", "{W} खांसी में चम्मच भर खून आया"),
    ("C11", "cough", "S3", EM, IM, "adult", "{S} is coughing and cannot speak full sentences",
     "{W} khansi ke saath bol nahi pa rahe", "{W} खांसी के साथ बोल नहीं पा रहे"),
    ("C12", "cough", "S3", EM, IM, "child", "{S} {has} a barking cough and makes a noise while breathing",
     "{W} kutte ke bhaunkne jaisi khansi hai, saans lete waqt awaaz aati hai", "{W} भौंकने जैसी खांसी है, सांस लेते समय आवाज़ आती है"),
    ("C13", "cough", "S3", EM, IM, "elder", "{S} {has} a cough and since today is talking confused",
     "{W} khansi hai aur aaj se ulta-seedha bol rahe hain", "{W} खांसी है और आज से उल्टा सीधा बोल रहे हैं"),
    ("C14", "cough", "S1", PM, SD, "elder", "{S} {has} had a dry cough for [4|5] days",
     "{W} [4|5] din se sukhi khansi hai", "{W} [चार|पाँच] दिन से सूखी खांसी है"),
    ("C15", "cough", "S1", PM, SD, "adult", "{S} {has} heart disease and a dry cough for [4|5] days",
     "{W} dil ki bimari hai aur [4|5] din se sukhi khansi", "{W} दिल की बीमारी है और [चार|पाँच] दिन से सूखी खांसी"),
    # ------------------------------------------------ STOMACH
    ("S01", "stomach", "S0", GP, R, "adult", "{S} {has} had loose motions [2|3] times since this morning, drinking water fine",
     "{W} subah se [2|3] baar dast hue, paani pee rahe hain", "{W} सुबह से [2|3] बार दस्त हुए, पानी पी रहे हैं"),
    ("S02", "stomach", "S0", GP, R, "adult", "{S} vomited twice today but is drinking fluids",
     "{W} aaj se do baar ulti hui par paani pee rahe hain", "{W} आज से दो बार उल्टी हुई पर पानी पी रहे हैं"),
    ("S03", "stomach", "S1", PM, SD, "adult", "{S} {has} had loose motions for [2|3] days with mild fever",
     "{W} [2|3] din se dast aur halka bukhar hai", "{W} [दो|तीन] दिन से दस्त और हल्का बुखार है"),
    ("S04", "stomach", "S1", PM, SD, "adult", "{S} {has} had [7|8] loose motions today",
     "{W} aaj [7|8] baar dast hue", "{W} आज [7|8] बार दस्त हुए"),
    ("S05", "stomach", "S1", PM, SD, "adult", "{S} {has} loose motions and a dry mouth since yesterday",
     "{W} kal se dast hai aur muh sookh raha hai", "{W} कल से दस्त है और मुँह सूख रहा है"),
    ("S06", "stomach", "S2", NU, SD, "adult", "{S} vomited [10|12] times and cannot keep even water down",
     "{W} [10|12] baar ulti hui, paani bhi nahi ruk raha", "{W} [10|12] बार उल्टी हुई, पानी भी नहीं रुक रहा"),
    ("S07", "stomach", "S2", NU, SD, "adult", "{S} {has} diarrhoea and feels dizzy on standing",
     "{W} dast ho rahe hain aur khade hone par chakkar aata hai", "{W} दस्त हो रहे हैं और खड़े होने पर चक्कर आता है"),
    ("S08", "stomach", "S2", NU, SD, "adult", "{S} {has} loose motions and is passing very little urine",
     "{W} dast ho rahe hain aur peshab bahut kam aa raha hai", "{W} दस्त हो रहे हैं और पेशाब बहुत कम आ रहा है"),
    ("S09", "stomach", "S2", GP, SD, "adult", "{S} {has} blood in the stool with fever",
     "{W} potty mein khoon aur bukhar hai", "{W} पॉटी में खून और बुखार है"),
    ("S10", "stomach", "S2", GP, SD, "adult", "{S} takes iron tablets and the stool is black",
     "{W} iron ki goli le rahe hain aur potty kaali aa rahi hai", "{W} आयरन की गोली ले रहे हैं और पॉटी काली आ रही है"),
    ("S11", "stomach", "S3", EM, IM, "adult", "The stool has become black and sticky since yesterday",
     "Kal se potty kaali aur chipchipi aa rahi hai", "कल से पॉटी काली और चिपचिपी आ रही है"),
    ("S12", "stomach", "S3", EM, IM, "adult", "{S} vomited blood this morning",
     "{W} subah khoon ki ulti hui", "{W} सुबह खून की उल्टी हुई"),
    ("S13", "stomach", "S3", EM, IM, "adult", "{S} {has} pain that moved to the lower right of the belly, worse on walking",
     "{W} dard naabhi se daayein neeche aa gaya, chalne par badhta hai", "{W} दर्द नाभि से दाएँ नीचे आ गया, चलने पर बढ़ता है"),
    ("S14", "stomach", "S3", EM, IM, "none", "My wife is pregnant and has severe stomach pain",
     "Meri wife pregnant hai aur pet mein tez dard hai", "मेरी पत्नी गर्भवती है और पेट में तेज़ दर्द है"),
    ("S15", "stomach", "S3", EM, IM, "child", "{S} has not passed urine for [12|14] hours and has loose motions",
     "{W} [12|14] ghante se peshab nahi kiya, dast ho rahe hain", "{W} [12|14] घंटे से पेशाब नहीं किया, दस्त हो रहे हैं"),
    ("S16", "stomach", "S2", NU, SD, "elder", "{S} {has} had loose motions for [2|3] days",
     "{W} [2|3] din se dast ho rahe hain", "{W} [दो|तीन] दिन से दस्त हो रहे हैं"),
    ("S17", "stomach", "S2", NU, SD, "child", "{S} {has} had diarrhoea for [3|4] days",
     "{W} [3|4] din se dast ho rahe hain", "{W} [तीन|चार] दिन से दस्त हो रहे हैं"),
    # ------------------------------------------------ CHEST PAIN
    ("H01", "chest_pain", "S0", GP, R, "none", "Chest hurts when I press it after the gym, [22|25|28] years old",
     "Gym ke baad chest dabane par dard hota hai, [22|25] saal", "जिम के बाद सीने को दबाने पर दर्द होता है, [22|25] साल"),
    ("H02", "chest_pain", "S0", GP, R, "none", "Chest pain on movement since a knock while playing, [20|24] years old",
     "Khelte hue chot ke baad seene mein hilne par dard, [20|24] saal", "खेलते हुए चोट के बाद सीने में हिलने पर दर्द, [20|24] साल"),
    ("H03", "chest_pain", "S1", GP, SD, "none", "Burning in the chest after meals, [24|26|30] years old, nothing else",
     "Khaane ke baad seene mein jalan, [24|26] saal, aur kuch nahi", "खाने के बाद सीने में जलन, [24|26] साल, और कुछ नहीं"),
    ("H04", "chest_pain", "S1", GP, SD, "none", "Acidity and chest burning at night after dinner, [27|32] years old",
     "Raat ko khaane ke baad acidity aur seene mein jalan, [27|32] saal", "रात को खाने के बाद एसिडिटी और सीने में जलन, [27|32] साल"),
    ("H05", "chest_pain", "S2", SP, SD, "adult", "{S} {has} diabetes and gets chest discomfort on and off, not right now",
     "{W} sugar hai, seene mein kabhi kabhi takleef hoti hai, abhi nahi", "{W} शुगर है, सीने में कभी कभी तकलीफ होती है, अभी नहीं"),
    ("H06", "chest_pain", "S3", EM, IM, "adult", "{S} {has} heavy pressure in the chest and is sweating",
     "{W} seene mein bhaari dabav hai aur paseena aa raha hai", "{W} सीने में भारी दबाव है और पसीना आ रहा है"),
    ("H07", "chest_pain", "S3", EM, IM, "adult", "{S} {has} chest pain going to the left arm",
     "{W} seene ka dard baayen haath tak ja raha hai", "{W} सीने का दर्द बाएँ हाथ तक जा रहा है"),
    ("H08", "chest_pain", "S3", EM, IM, "none", "[48|55|62] years old with high BP, having chest pain",
     "[48|55|62] saal, BP ki bimari hai, seene mein dard ho raha hai", "[48|55|62] साल, बीपी की बीमारी है, सीने में दर्द हो रहा है"),
    ("H09", "chest_pain", "S3", EM, IM, "adult", "{S} {has} sudden sharp pain on breathing and breathlessness",
     "{W} achanak saans lete waqt chubhne wala dard aur saans phool rahi hai", "{W} अचानक साँस लेते समय चुभने वाला दर्द और साँस फूल रही है"),
    ("H10", "chest_pain", "S3", EM, IM, "adult", "{S} {has} had chest pain for more than [10|15] minutes",
     "{W} [10|15] minute se zyada seene mein dard hai", "{W} [दस|पंद्रह] मिनट से ज़्यादा सीने में दर्द है"),
    ("H11", "chest_pain", "S3", EM, IM, "elder", "{S} {has} sugar and a strange discomfort in the chest",
     "{W} sugar hai aur seene mein ajeeb sa dard", "{W} शुगर है और सीने में अजीब सा दर्द"),
    ("H12", "chest_pain", "S3", EM, IM, "adult", "{S} {has} chest tightness and feels faint",
     "{W} seene mein jakdan aur chakkar aa raha hai", "{W} सीने में जकड़न और चक्कर आ रहा है"),
    ("H13", "chest_pain", "S1", GP, SD, "none", "Burning in the chest with sour burps after food, [23|29] years old",
     "Khaane ke baad seene mein jalan aur khatti dakaar, [23|29] saal", "खाने के बाद सीने में जलन और खट्टी डकार, [23|29] साल"),
    # ------------------------------------------------ HEADACHE
    ("A01", "headache", "S0", GP, R, "adult", "{S} {has} the usual migraine again today",
     "{W} purana migraine hai, aaj phir wahi dard", "{W} पुराना माइग्रेन है, आज फिर वही दर्द"),
    ("A02", "headache", "S0", GP, R, "adult", "{S} {has} a headache like the ones that happened before",
     "{W} sir dard hai, pehle bhi aisa hota hai", "{W} सिर दर्द है, पहले भी ऐसा होता है"),
    ("A03", "headache", "S1", GP, SD, "adult", "{S} {has} a headache like this for the first time since yesterday",
     "{W} kal se pehli baar aisa sir dard ho raha hai", "{W} कल से पहली बार ऐसा सिर दर्द हो रहा है"),
    ("A04", "headache", "S1", GP, SD, "adult", "{S} {has} a headache and fever since yesterday",
     "{W} kal se sir dard aur bukhar hai", "{W} कल से सिर दर्द और बुखार है"),
    ("A05", "headache", "S1", PM, SD, "child", "{S} {has} a headache and fever",
     "{W} sir dard aur bukhar hai", "{W} सिर दर्द और बुखार है"),
    ("A06", "headache", "S2", SP, SD, "adult", "{S} {has} had a headache getting worse every day for [3|4] weeks",
     "{W} [3|4] hafte se roz sir dard badh raha hai", "{W} [तीन|चार] हफ्ते से रोज़ सिर दर्द बढ़ रहा है"),
    ("A07", "headache", "S2", SP, SD, "adult", "{S} {has} a headache that wakes them from sleep",
     "{W} sir dard neend se utha deta hai", "{W} सिर दर्द नींद से उठा देता है"),
    ("A08", "headache", "S2", SP, SD, "adult", "{S} {has} a headache and BP is [165/100|170/105]",
     "{W} sir dard hai aur BP [165/100|170/105] aaya", "{W} सिर दर्द है और बीपी [165/100|170/105] आया"),
    ("A09", "headache", "S2", SP, SD, "none", "[55|60|62] years old, a new headache for the first time",
     "[55|60] saal, pehli baar aisa sir dard", "[55|60] साल, पहली बार ऐसा सिर दर्द"),
    ("A10", "headache", "S3", EM, IM, "adult", "{S} suddenly {has} the worst headache of their life",
     "{W} achanak zindagi ka sabse tez sir dard ho raha hai", "{W} अचानक ज़िंदगी का सबसे तेज़ सिर दर्द हो रहा है"),
    ("A11", "headache", "S3", EM, IM, "adult", "{S} {has} a headache and one arm has become weak",
     "{W} sir dard aur ek haath mein kamzori aa gayi", "{W} सिर दर्द और एक हाथ में कमज़ोरी आ गई"),
    ("A12", "headache", "S3", EM, IM, "adult", "{S} fell, hit the head and vomited twice",
     "{W} gir gaye, sir par chot lagi, do baar ulti hui", "{W} गिर गए, सिर पर चोट लगी, दो बार उल्टी हुई"),
    ("A13", "headache", "S3", EM, IM, "adult", "{S} {has} a headache with BP [190/120|200/125]",
     "{W} sir dard aur BP [190/120|200/125] hai", "{W} सिर दर्द और बीपी [190/120|200/125] है"),
    ("A14", "headache", "S3", EM, IM, "none", "[7|8] months pregnant with a headache and blurred vision",
     "[7|8] mahine pregnant, sir dard aur aankhon ke aage dhundhla", "[सात|आठ] महीने की गर्भवती, सिर दर्द और आँखों के आगे धुंधला"),
    ("A15", "headache", "S3", EM, IM, "adult", "{S} {has} a headache, fever and a stiff neck",
     "{W} sir dard, bukhar aur gardan akad gayi", "{W} सिर दर्द, बुखार और गर्दन अकड़ गई"),
]

HG_TYPO = {"bukhar": ["bukhaar", "bukar"], "khansi": ["khasi", "khaansi"], "hai": ["h", "he"], "nahi": ["nhi", "nahin"],
           "dard": ["dardh"], "saans": ["sans"], "bahut": ["bht", "bohot"], "raha": ["rha"], "rahi": ["rhi"]}
ALT = re.compile(r"\[([^\]]+)\]")


def _alts(s: str, rng: random.Random) -> str:
    return ALT.sub(lambda m: rng.choice(m.group(1).split("|")), s)


def render(t: tuple, lang: str, rng: random.Random) -> str:
    _tid, _pw, _st, _ct, _urg, who, en, hg, hi = t
    tpl = {"en": en, "hinglish": hg, "hi": hi}[lang]
    grp = who if who in ("adult", "elder", "child") else "adult"
    if lang == "en":
        pool = EN_WHO[grp] if "{has}" in tpl else [p for p in EN_WHO[grp] if p[0] != "I"]
        s, has = rng.choice(pool)
        text = tpl.replace("{S}", s).replace("{has}", has)
    else:
        text = tpl.replace("{W}", rng.choice((HG_W if lang == "hinglish" else HI_W)[grp]))
    text = _alts(text, rng)
    if lang == "hinglish":
        text = " ".join(rng.choice(HG_TYPO[w]) if w in HG_TYPO and rng.random() < 0.25 else w for w in text.split())
        if rng.random() < 0.4:
            text = text.lower()
    return " ".join(text.split())


def generate(rng: random.Random, per_template: int = 6) -> list[dict]:
    """~6 renders per template (2 per language), deduplicated: about 80-100 vignettes per pathway."""
    rows, seen = [], set()
    for t in T:
        tid, pw, st, ct, urg = t[:5]
        made, tries = 0, 0
        while made < per_template and tries < per_template * 12:
            tries += 1
            lang = ("en", "hinglish", "hi")[made % 3]
            text = render(t, lang, rng)
            if text in seen:
                continue
            seen.add(text)
            rows.append({"text": text, "language": lang, "care_type": ct, "urgency": urg,
                         "pathway": pw, "stage": st, "template_id": tid})
            made += 1
    return rows
