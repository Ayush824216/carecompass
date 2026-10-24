# CareCompass Clinical Pathways Spec

Version 1 · Team OCTUPUS · HackIIITD

> **Scope.** This spec drives routing (care type + urgency) and follow-up questions. It is NOT a diagnostic tool.
> Concern patterns such as `dengue_like` are internal routing labels. They are never shown to the user as a diagnosis;
> user-facing text talks about "danger signs" and "what to do next". Thresholds below are conservative routing
> thresholds for a prototype and must be reviewed with the clinical mentors.

---

## 0. How the pathways work

### 0.1 Complaint-based, like real triage
Real triage starts from the chief complaint, not from a disease. We implement 5 deep pathways:

| # | Pathway | Covers (internal concern patterns) |
|---|---|---|
| 1 | **Fever** (bukhar) | viral, dengue-like, malaria-like, typhoid-like, jaundice/hepatitis-like, chikungunya-like, urinary infection-like, meningitis-like, pneumonia-like |
| 2 | **Cough** (khansi) | dry, wet/productive, blood in cough, asthma flare, pneumonia-like, TB-like (>= 2 weeks) |
| 3 | **Stomach** (ulti / dast / pet dard) | gastroenteritis, dehydration, dysentery, GI bleeding, appendicitis-like, obstruction-like |
| 4 | **Chest pain** (seene mein dard) | heart-like, acidity-like, muscle/chest-wall, breathing-related |
| 5 | **Headache** (sir dard) | tension/migraine, fever-related, stroke-like, meningitis-like, head injury, high BP, pregnancy-related |

A message can trigger more than one pathway (for example fever + cough). Run all matching pathways;
the **final urgency is the most urgent** across them, and the care type comes from the most severe one.

### 0.2 Severity stages (same ladder for every pathway)

| Stage | Meaning | Typical routing |
|---|---|---|
| **S0** Mild | Self-limiting, no warning signs | `gp_teleconsult` · `routine` |
| **S1** Needs assessment | Needs vitals/tests or a doctor today | `paramedic_home_visit` or `gp_teleconsult` · `same_day` |
| **S2** Warning signs | Could get worse quickly; needs a doctor/specialist or nursing care today | `gp_teleconsult` / `specialist_referral` / `nurse_home_visit` · `same_day` (some `immediate`) |
| **S3** Emergency | Danger signs | `emergency_referral` · `immediate` (skip matching, show call-for-help) |

### 0.3 Ask like a senior doctor, but stay within 4 questions
A senior doctor asks in this order: **danger signs first → onset and duration → character → associated
symptoms → who the patient is (risk factors) → reports**. To stay within the 4-question limit:

- Use **multi-select chips**. One tap answers many slots ("Inme se kya-kya hai?").
- **Skip** any question whose slots are already in the user's text.
- **Stop immediately** when an S3 sign appears. Never ask further questions on an emergency.
- Always include a "Kuch nahi / None of these" chip.

### 0.4 Numbers we must extract (slot parser)

| Slot | Formats to handle |
|---|---|
| Temperature | `103`, `103 F`, `103°`, `39.5`, `39.5 C`, "tez bukhar", "bahut tez" (no number → ask). Values 35–43 → °C; 95–110 → °F |
| Duration | "2 din", "do din", "parso se", "kal raat se", "ek hafta", "3 hafte", "mahine bhar se", "since Monday" |
| Age | "6 mahine ka baccha", "2 saal", "75 saal ke papa", "buzurg", "newborn", "infant" |
| Platelets | "40000", "40,000", "40k", "40 hazaar", "0.4 lakh", "1.2 lakh", "40 thousand" |
| BP | "180/110", "BP 160 by 100", "BP high hai" (no number → ask if relevant) |
| Counts | "5 baar ulti", "8-10 baar dast", "din mein 6 baar" |
| Blood amount | "dhaage jaisa / thoda sa" vs "chammach bhar / bahut / baar-baar" |

### 0.5 Risk modifiers (apply across all pathways)

| Modifier | Rule |
|---|---|
| Infant < 3 months with fever >= 100.4°F (38°C) | **S3** |
| Child < 5 with any general danger sign: cannot drink/breastfeed, vomits everything, convulsion, very sleepy/unconscious | **S3** |
| Elderly 65+ | Raise fever, cough and stomach pathways by one stage (max S3). New confusion → **S3** |
| Pregnancy | Fever → at least S1 `same_day`. Abdominal pain, bleeding, or headache with vision changes/swelling → **S3** |
| Diabetes, heart, kidney or liver disease, cancer/chemo, on steroids, HIV | Raise by one stage |
| Bedridden / cannot travel | Prefer a home visit over teleconsult at the same urgency |

---

## 1. FEVER pathway (bukhar)

### 1.1 Slots
temperature, duration_days, pattern (continuous / with chills and shivering / comes and goes), chills_rigors,
body_ache, severe_joint_pain, rash, red_spots, bleeding (gums, nose, vomit, urine, black stool), persistent_vomiting,
abdominal_pain, yellow_eyes_or_urine, dark_urine, burning_urine, flank_pain, cough, breathlessness, headache,
stiff_neck, confusion_or_drowsiness, seizure, reduced_urine, cold_clammy_skin, dizziness_on_standing,
able_to_drink, platelet_count, age, pregnancy, comorbidities

### 1.2 Concern patterns (internal only)

| Pattern | Features that point to it | Warning signs (→ S2) | Danger signs (→ S3) |
|---|---|---|---|
| `viral_simple` | Fever < 3 days, body ache, cold/cough, eating and drinking | — | — |
| `dengue_like` | Fever 2–7 days, severe body ache, pain behind eyes, rash, mosquito season | Abdominal pain, persistent vomiting, gum/nose bleeding, very weak/restless, platelets falling, fever going down but patient getting worse | Cold clammy skin, dizziness/fainting on standing, very little or no urine, heavy bleeding, black stool, breathing difficulty, platelets < 20,000 |
| `malaria_like` | Fever with chills/shivering and sweating, comes in cycles | Very weak, persistent vomiting, cannot eat | Confusion, seizure, yellow eyes, dark/cola urine, breathing difficulty, unconscious |
| `typhoid_like` | Fever > 5–7 days, rising step by step, abdominal pain, constipation or loose motions, loss of appetite | Fever > 7 days, severe abdominal pain | Severe abdominal pain with rigid belly, blood in stool, confusion |
| `jaundice_like` | Yellow eyes/skin, dark urine, pale stool, nausea | Persistent vomiting, cannot eat | Confusion/drowsiness, bleeding, swollen abdomen |
| `chikungunya_like` | Sudden high fever + severe joint pain/swelling in hands and feet, rash | Elderly unable to walk, child | Same as general danger signs |
| `uti_like` | Burning urine, frequent urination | Flank/back pain, vomiting, high fever | Confusion (elderly), very low urine |
| `meningitis_like` | Fever + severe headache | — | Stiff neck, confusion, non-fading red/purple rash, seizure → **S3** directly |
| `pneumonia_like` | Fever + cough | Fast breathing, chest pain on breathing | Breathless at rest, blue lips, confusion |

### 1.3 Platelet rules (only when the user shares a report value)

| Platelet count | Routing |
|---|---|
| >= 1.5 lakh | Normal, follow the other rules |
| 1 – 1.5 lakh | At least S1: `paramedic_home_visit` · `same_day` (repeat test, vitals) |
| 50,000 – 1 lakh | S2: `gp_teleconsult` · `same_day`, plus a home blood-test visit |
| 20,000 – 50,000 | S3 if any bleeding or warning sign; otherwise S2 `same_day` with a red note "needs doctor today" |
| < 20,000 | **S3** `emergency_referral` · `immediate` |
| Any value + any bleeding | **S3** |

> "Khoon ki kami" (anaemia) is NOT bleeding. "Khoon ki jaanch" (blood test) is NOT bleeding.

### 1.4 Temperature and duration rules

| Condition | Minimum stage |
|---|---|
| < 101°F, < 3 days, adult, drinking well | S0 |
| Fever >= 2 days (PS example: fever + cough, 2 days) | S1 `paramedic_home_visit` · `same_day` |
| >= 103°F, or > 3 days | S1 `same_day` |
| >= 104°F | S2 `same_day` |
| > 7 days | S2 `same_day` (doctor + tests) |
| > 14 days | S2 `specialist_referral` · `same_day` |
| >= 105.8°F, or any fever + confusion | **S3** |
| Fever with seizure (any age) | **S3** |

### 1.5 Senior-doctor questions (max 4, multi-select, skip what is known)

1. **Danger screen**: "Inme se kuch ho raha hai?"
   `[Bahut sust / behoshi jaisa]` `[Saans phoolna]` `[Kahin se khoon aana]` `[Gardan akadna / bahut tez sir dard]` `[Daura]` `[Kuch nahi]`
2. **Duration and height**: "Bukhar kab se hai aur kitna?"
   `[1 din]` `[2–3 din]` `[4–7 din]` `[1 hafte se zyada]` + `[101 se kam]` `[101–103]` `[103 se zyada]` `[Naapa nahi]`
3. **Associated**: "Bukhar ke saath kya-kya hai?"
   `[Thand lagkar kapkapi]` `[Badan / jodon mein bahut dard]` `[Laal daane]` `[Aankhen / peshab peela]` `[Baar-baar ulti]` `[Pet dard]` `[Peshab mein jalan]` `[Khansi]` `[Kuch nahi]`
4. **Who and reports**: "Patient kaun hai? Koi report hai?"
   `[5 saal se chhota baccha]` `[65+ buzurg]` `[Pregnant]` `[Sugar / heart / kidney patient]` `[Koi nahi]` + optional field "Platelets kitne aaye?"

### 1.6 Worked examples

| Input | Stage | Routing |
|---|---|---|
| "Papa ko do din se bukhar hai aur khansi bhi, saans theek hai" | S1 | paramedic_home_visit · same_day |
| "Kal se halka bukhar, 100 tha, khana kha raha hoon" | S0 | gp_teleconsult · routine |
| "4 din se tez bukhar, aankhon ke peeche dard, badan toot raha hai" | S1 (dengue_like) | paramedic_home_visit · same_day |
| "Dengue test positive, platelets 80 hazaar, pet mein dard" | S2 | gp_teleconsult · same_day (+ home blood test) |
| "Platelets 18000 aur masudon se khoon" | S3 | emergency_referral · immediate |
| "Roz shaam ko thand lagkar bukhar aata hai, phir paseena" | S1 (malaria_like) | paramedic_home_visit · same_day |
| "Bukhar ke saath aankhen peeli aur ab bahut neend aa rahi hai" | S3 | emergency_referral · immediate |
| "8 din se bukhar, roz badhta hai, pet dard aur kabz" | S2 (typhoid_like) | gp_teleconsult · same_day |
| "Tez bukhar aur ghutne-kalaiyon mein itna dard ki chal nahi pa rahi, 70 saal" | S2 (chikungunya_like + elderly) | paramedic_home_visit · same_day |
| "2 mahine ke bacche ko 100.8 bukhar" | S3 (infant) | emergency_referral · immediate |
| "Bukhar aur gardan akad gayi hai, ulti bhi" | S3 (meningitis_like) | emergency_referral · immediate |
| "Bukhar aur peshab mein jalan, kamar ke side mein dard" | S2 (uti_like) | gp_teleconsult · same_day |

---

## 2. COUGH pathway (khansi)

### 2.1 The three types the mentor asked about

| Type | Hinglish | Default stage |
|---|---|---|
| Dry cough | sukhi khansi | S0 if < 3 weeks and no other signs |
| Wet / productive cough | balgam wali khansi (white, yellow, green) | S0–S1; S1 if with fever or > 1 week |
| Blood in cough | khoon wali khansi | Streaks only → **S2** `specialist_referral` · `same_day`. More than a spoonful, repeated, or with breathlessness → **S3** |

### 2.2 Slots
type (dry/wet/blood), sputum_colour, blood_amount, duration, breathlessness (on walking / at rest / cannot speak full sentences),
wheeze, chest_pain_on_breathing, fever, night_sweats, weight_loss, smoker, known_asthma_copd, inhaler_not_helping,
child_barking_or_stridor, whoop, choking_or_swallowed_object, blue_lips, confusion (elderly), age, comorbidities

### 2.3 Stage rules

| Stage | Conditions | Routing |
|---|---|---|
| S0 | Dry or wet cough < 3 weeks, no fever or mild, no breathlessness, adult | gp_teleconsult · routine |
| S1 | Cough + fever >= 2 days, or yellow/green sputum > 1 week, or child/elderly with cough | paramedic_home_visit · same_day |
| S2 | Cough >= 2 weeks with fever / night sweats / weight loss (TB-like); blood streaks; known asthma with wheeze only partly relieved; fast breathing without distress | specialist_referral (chest) or gp_teleconsult · same_day |
| S3 | Breathless at rest or cannot speak full sentences, blue lips, large or repeated blood, stridor or barking with breathing difficulty in a child, choking, chest pain with breathlessness, new confusion in elderly | emergency_referral · immediate |

### 2.4 Senior-doctor questions
1. **Danger**: `[Saans phool rahi / bolne mein dikkat]` `[Khansi mein khoon]` `[Hoth / naakhun neele]` `[Seene mein dard]` `[Kuch nahi]`
2. **Type and duration**: `[Sukhi]` `[Balgam wali]` `[Khoon wali]` × `[1 hafte se kam]` `[1–2 hafte]` `[2 hafte se zyada]`
3. **Associated**: `[Bukhar]` `[Raat ko paseena]` `[Wazan kam hona]` `[Seeti jaisi awaaz]` `[Smoking]` `[Asthma / COPD]` `[Kuch nahi]`
4. **Only if blood**: "Kitna khoon?" `[Balgam mein dhaage jaisa]` `[Chammach bhar ya zyada / baar-baar]`

### 2.5 Worked examples

| Input | Stage | Routing |
|---|---|---|
| "5 din se sukhi khansi, aur kuch nahi" | S0 | gp_teleconsult · routine |
| "Balgam wali khansi aur 3 din se bukhar" | S1 | paramedic_home_visit · same_day |
| "3 hafte se khansi, raat ko paseena, wazan kam ho gaya" | S2 (TB-like) | specialist_referral · same_day |
| "Balgam mein thoda khoon ke dhaage dikhe" | S2 | specialist_referral · same_day |
| "Khansi mein bahut khoon aaya, chammach bhar" | S3 | emergency_referral · immediate |
| "Asthma hai, inhaler se bhi aaram nahi, bol nahi pa rahi" | S3 | emergency_referral · immediate |
| "Bacche ki khansi kutte ke bhaunkne jaisi, saans lete waqt awaaz" | S3 | emergency_referral · immediate |
| "Dadi ko khansi aur aaj se kuch ulta-seedha bol rahi hain" | S3 (elderly confusion) | emergency_referral · immediate |

---

## 3. STOMACH pathway (ulti / dast / pet dard)

### 3.1 Slots
vomiting_count, diarrhoea_count_per_day, duration, blood_in_stool, black_tarry_stool, blood_or_coffee_ground_vomit,
able_to_keep_fluids, urine_output (normal / less / none in 8–12 h), dizziness_on_standing, dry_mouth, sunken_eyes,
child_no_tears_or_dry_diaper, pain_location (right lower / upper / around navel / all over), pain_severity,
pain_worse_on_walking_or_coughing, rigid_belly, fever, pregnancy, no_stool_or_gas_with_swelling, many_people_sick, age

### 3.2 Stage rules

| Stage | Conditions | Routing |
|---|---|---|
| S0 | Loose motions or vomiting < 1 day, drinking fluids, passing urine normally, adult | gp_teleconsult · routine |
| S1 | > 1 day, or >= 6 loose motions a day, or with fever, or mild dehydration (dry mouth) | paramedic_home_visit · same_day |
| S2 | Cannot keep fluids down, very little urine, dizziness on standing, blood in stool with fever; elderly/child with ongoing diarrhoea | nurse_home_visit (fluids under doctor's order) · same_day; infant or frail elderly → immediate |
| S3 | Blood or coffee-ground vomit, black tarry stool, severe pain in the lower right or a rigid belly, abdominal pain in pregnancy, no urine for 12 h (8 h in a child), very drowsy, infant lethargic, no stool/gas with swelling and vomiting | emergency_referral · immediate |

### 3.3 Senior-doctor questions
1. **Danger**: `[Ulti ya potty mein khoon / kaali potty]` `[Pet mein bahut tez dard]` `[Bahut sust / chakkar]` `[Peshab bahut kam ya band]` `[Kuch nahi]`
2. **How much and how long**: `[Aaj se]` `[1–2 din]` `[2 din se zyada]` + `[Din mein 1–5 baar]` `[6+ baar]`
3. **Fluids and pain**: `[Paani bhi nahi ruk raha]` `[Muh sookh raha]` `[Bukhar]` `[Dard daayein neeche]` `[Dard poore pet mein]` `[Kuch nahi]`
4. **Who**: `[Baccha]` `[Buzurg]` `[Pregnant]` `[Sugar / kidney patient]` `[Koi nahi]`

### 3.4 Worked examples

| Input | Stage | Routing |
|---|---|---|
| "Aaj subah se 3 baar dast, paani pee raha hoon" | S0 | gp_teleconsult · routine |
| "2 din se dast aur halka bukhar" | S1 | paramedic_home_visit · same_day |
| "Mummy ko 10 baar ulti, paani bhi nahi ruk raha, chakkar aa rahe" | S2 | nurse_home_visit · same_day |
| "Potty bilkul kaali aur chipchipi aa rahi hai" | S3 | emergency_referral · immediate |
| "Naabhi ke paas se dard daayein neeche aa gaya, chalne par badhta hai, bukhar" | S3 (appendicitis-like) | emergency_referral · immediate |
| "Pregnant hoon aur pet mein tez dard" | S3 | emergency_referral · immediate |
| "Bacche ne 12 ghante se peshab nahi kiya, dast ho rahe" | S3 | emergency_referral · immediate |

---

## 4. CHEST PAIN pathway (seene mein dard)

**Principle: low threshold.** Diabetics, elderly and women often have atypical heart symptoms. When in doubt → S3.

### 4.1 Slots
onset, character (pressure/heavy/squeezing, burning, sharp on breathing, on pressing/movement), radiation (left arm, jaw, back),
sweating, breathlessness, nausea, fainting, duration (> 5 min / continuous / comes and goes), trigger (exertion, after food, movement, injury),
relieved_by_rest, age, diabetes, bp, heart_disease, smoking, cholesterol

### 4.2 Stage rules

| Stage | Conditions | Routing |
|---|---|---|
| S0 | Pain on pressing the chest or with movement, after a strain or minor injury, young, no risk factors, no red flags | gp_teleconsult · routine |
| S1 | Burning after meals, young, no risk factors, no red flags | gp_teleconsult · same_day |
| S2 | Rarely used; recurrent unexplained chest discomfort with risk factors but none right now | specialist_referral (cardiology) · same_day |
| S3 | Pressure/heaviness, radiation to arm/jaw/back, sweating, breathlessness, fainting, pain > 5 min, sudden sharp pain on breathing with breathlessness, OR any current chest pain in age >= 40 or with diabetes/BP/heart disease that is not clearly chest-wall pain | emergency_referral · immediate |

### 4.3 Senior-doctor questions
1. **Danger** (any → stop, S3): `[Dard baayen haath / jabde / peeth tak]` `[Paseena]` `[Saans phoolna]` `[Chakkar / behoshi]` `[Kuch nahi]`
2. **Character**: `[Bhaari / dabav]` `[Jalan]` `[Chubhne jaisa, saans lene par]` `[Dabane / hilne par]`
3. **Timing**: `[Abhi ho raha, 5 min se zyada]` `[Aata-jaata]` `[Khaane ke baad]` `[Chot ke baad]`
4. **Risk**: `[Umar 40+]` `[Sugar]` `[BP]` `[Heart patient]` `[Smoking]` `[Koi nahi]`

### 4.4 Worked examples

| Input | Stage | Routing |
|---|---|---|
| "Seene mein bhaari dabav aur paseena, baayen haath mein dard" | S3 | emergency_referral · immediate |
| "55 saal, sugar hai, seene mein ajeeb sa dard" | S3 | emergency_referral · immediate |
| "Khaane ke baad seene mein jalan, 24 saal, aur kuch nahi" | S1 | gp_teleconsult · same_day |
| "Gym ke baad chest dabane par dard hota hai, 22 saal" | S0 | gp_teleconsult · routine |
| "Achanak saans lete waqt chubhne wala dard aur saans phool gayi" | S3 | emergency_referral · immediate |

---

## 5. HEADACHE pathway (sir dard)

### 5.1 Slots
sudden_worst_ever, fever, stiff_neck, rash, confusion, weakness_one_side, face_droop, slurred_speech, vision_loss_or_double,
seizure, head_injury, vomiting_after_injury, blood_thinners, bp_reading, pregnancy_weeks, swelling_face_hands, new_after_50,
progressive_over_weeks, wakes_from_sleep, known_migraine, one_sided_with_light_sensitivity, duration

### 5.2 Stage rules

| Stage | Conditions | Routing |
|---|---|---|
| S0 | Usual pattern (known migraine/tension), mild to moderate, no red flags | gp_teleconsult · routine |
| S1 | New or more frequent headaches, or headache with fever without danger signs | gp_teleconsult · same_day (paramedic_home_visit if fever and elderly/child) |
| S2 | New headache after age 50, progressive over weeks, wakes from sleep, BP >= 160/100 without other symptoms | specialist_referral (neurology) or gp_teleconsult · same_day |
| S3 | Sudden worst-ever headache, stroke signs (one-sided weakness, face droop, slurred speech, vision loss), fever + stiff neck/confusion/rash, head injury + vomiting/drowsiness or on blood thinners, BP >= 180/120 with symptoms, pregnancy (> 20 weeks) + headache with vision changes or swelling, seizure | emergency_referral · immediate |

### 5.3 Senior-doctor questions
1. **Danger**: `[Achanak, zindagi ka sabse tez dard]` `[Ek taraf kamzori / muh tedha / bolne mein dikkat]` `[Gardan akadna + bukhar]` `[Sir par chot]` `[Kuch nahi]`
2. **Pattern**: `[Pehle bhi aisa hota hai]` `[Pehli baar]` `[Hafton se badh raha]` `[Neend se uthata hai]`
3. **Associated**: `[Ulti]` `[Roshni se takleef]` `[Dhundhla dikhna]` `[Bukhar]` `[BP high]` `[Kuch nahi]`
4. **Who**: `[50+ umar]` `[Pregnant]` `[Khoon patla karne ki dawai]` `[Koi nahi]` + optional "BP reading?"

### 5.4 Worked examples

| Input | Stage | Routing |
|---|---|---|
| "Migraine purana hai, aaj phir wahi dard" | S0 | gp_teleconsult · routine |
| "Achanak itna tez sir dard jaise kabhi nahi hua" | S3 | emergency_referral · immediate |
| "Sir dard aur ek haath mein kamzori, bolne mein atak rahe" | S3 | emergency_referral · immediate |
| "Papa gir gaye, sir par chot, ab 2 baar ulti" | S3 | emergency_referral · immediate |
| "60 saal, pichle 3 hafte se roz sir dard badh raha" | S2 | specialist_referral · same_day |
| "8 mahine pregnant, sir dard aur aankhon ke aage dhundhla" | S3 | emergency_referral · immediate |

---

## 6. Edge cases every pathway must handle (test list)

| # | Edge case | Example | Expected behaviour |
|---|---|---|---|
| 1 | Negation | "bukhar hai par saans ki dikkat nahi" | No breathlessness flag |
| 2 | Double negation / correction | "khoon nahi... nahi ruko, thoda sa aaya tha" | Treat as blood present (latest statement wins, safer) |
| 3 | Celsius vs Fahrenheit | "39.5" vs "103" | Both → high fever |
| 4 | No number | "bahut tez bukhar" | Record fever_reported_high = true and temperature = not measured; never infer a number. Ask "Thermometer se naapa? Kitna aaya?" [<100] [100–102] [102–104] [104+] [Naapa nahi]. Until a reading is given, stage is at least S1 (same-day) for safety, and the summary says "temperature not measured". The same applies to BP, sugar and platelets: only values the user gives are used. |
| 5 | Relative time | "parso se", "kal raat se" | Duration in days |
| 6 | Platelet formats | "40k", "40 hazaar", "0.4 lakh" | 40,000 |
| 7 | Someone else's illness | "padosi ko dengue hua tha" | Not a symptom of the patient |
| 8 | Past history | "pichle saal malaria hua tha" | History only, not current |
| 9 | User names a disease | "mujhe lagta hai dengue hai" | Do not confirm; ask symptoms; route by symptoms |
| 10 | "Khoon" ambiguity | "khoon ki kami hai", "khoon ki jaanch karayi" | NOT bleeding |
| 11 | Multiple complaints | "bukhar aur seene mein dard" | Run both; chest pain rules dominate |
| 12 | Mixed language + Hindi script | "मम्मी को fever hai aur ulti" | Parse both scripts |
| 13 | Age in months | "8 mahine ka baccha" | Infant rules |
| 14 | Pregnancy mentioned late | in the 3rd answer | Re-evaluate stage |
| 15 | Contradiction | "saans theek hai" then "chalne par phoolti hai" | Use the more severe |
| 16 | Medicine request | "kaunsi dawai lun bukhar ke liye" | No medicine advice; continue routing |
| 17 | Report pasted | "Hb 9, platelet 95000, WBC 3000" | Extract platelets; do not interpret other values to the user |
| 18 | Voice-typing errors | "bukhaar", "khasi", "plate let" | Normaliser handles |
| 19 | Fever going down but worse | "bukhar utar gaya par ab bahut kamzori aur pet dard" (dengue critical phase) | Warning sign → S2 at least |
| 20 | Iron tablets + black stool | "iron ki goli le rahi hoon, potty kaali" | Still flag (safer), say a doctor should check today |

---

## 7. Combining with the ML models
- Pathways are deterministic rules that produce `{stage, care_type, urgency, triggered_signs, concern_patterns}`.
- ML ensemble predictions are still computed.
- **Final urgency = the most urgent of (pathway, ML)**. Care type: the pathway's when its stage was decided by explicit rules; otherwise the ML ensemble.
- The safety gate still runs first and last; S3 from any pathway = emergency path.
- For the hidden test (single message, no follow-ups), pathways work on whatever slots are present; missing slots never lower urgency.

## 8. References (for the write-up; verify exact editions before citing)
- WHO, *Dengue: Guidelines for Diagnosis, Treatment, Prevention and Control* (2009): warning signs and severe dengue criteria.
- National Center for Vector Borne Diseases Control (NCVBDC), India: dengue, malaria and chikungunya guidance.
- WHO, *Integrated Management of Childhood Illness (IMCI)*: general danger signs in children.
- NICE NG143, *Fever in under 5s*: traffic-light system for children.
- National TB Elimination Programme (NTEP), India: cough of 2 weeks or more as presumptive TB.
- Standard emergency chest pain and stroke (FAST) red flags.
