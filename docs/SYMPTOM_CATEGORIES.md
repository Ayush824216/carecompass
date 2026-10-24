# SwasthMitra Symptom Categories

Companion to `docs/CLINICAL_PATHWAYS.md`. This file defines the eight symptom categories the assessment must support.
Possible causes are educational only and never a diagnosis. Urgency always comes from the deterministic safety rules and pathways.

## Objectives

1. Identify the user's primary symptom category.
2. Ask relevant follow-up questions based on each answer.
3. Maintain an accurate temporary assessment state.
4. Detect missing, contradictory, unclear, and potentially serious information.
5. Identify relevant possible causes without claiming a confirmed diagnosis.
6. Evaluate urgency using deterministic safety rules.
7. Explain why an urgency category was selected.
8. Recommend safe next steps.
9. Offer suitable public-resource discovery, nearby hospital search, or caregiver matching where appropriate.
10. Offer an authorized emergency-contact action when warranted.
11. Preserve the user's privacy and never invent successful external actions.
12. Monitor application behavior and assessment quality without unnecessarily storing sensitive health information.

## The eight primary symptom categories

Implement eight complete assessment workflows.

Each category must have its own relevant follow-up logic, safety checks, missing-information handling, possible-cause explanations, and appropriate next actions.

### CATEGORY 1 — COUGH AND SPUTUM

Initial choices:
- Dry cough.
- Wet cough or cough with mucus.
- Wheezing or chest tightness with cough.
- Cough with blood in sputum.
- Persistent or recurring cough.

Relevant follow-up questions may cover:
- Duration and onset.
- Whether symptoms are worsening.
- Mucus characteristics where useful.
- Fever or chills.
- Breathlessness.
- Chest pain.
- Wheezing.
- Night sweats.
- Unintentional weight loss.
- Relevant TB exposure or contact when appropriate.
- Other relevant medical risk factors.

Possible educational explanations may include airway irritation, allergies, respiratory infections, bronchitis, asthma-related problems, pneumonia, tuberculosis, and other causes when supported by the reported information.

Do not automatically conclude that cough with blood means tuberculosis.

Blood in sputum must trigger additional safety assessment and appropriate medical evaluation. A few small streaks and substantial bleeding must not receive identical handling.

If blood is accompanied by severe breathing difficulty, chest or upper-back pain, fainting, or other documented emergency warning signs, show emergency guidance immediately.

Persistent cough with relevant TB-associated symptoms should trigger appropriate professional evaluation and guidance about formal testing. Never diagnose TB from symptoms alone.

### CATEGORY 2 — FEVER AND CHILLS

Ask relevant questions about:
- Duration.
- Measured temperature, if available.
- Chills and general condition.
- Associated cough or breathing symptoms.
- Rash.
- Headache or neck stiffness.
- Vomiting or inability to drink.
- Confusion or unusual drowsiness.
- Relevant exposures and risk factors.

Explain possible infectious or non-infectious causes cautiously.

Emergency warning signs must be checked before continuing ordinary questioning.

Do not infer fever severity when the user has not measured or reported a temperature.

### CATEGORY 3 — BREATHING PROBLEMS

Ask about:
- Sudden versus gradual onset.
- Difficulty breathing at rest.
- Ability to speak normally.
- Wheezing.
- Chest pain.
- Blue or grey lips.
- Fainting or confusion.
- Relevant history when necessary.

Severe or sudden breathing difficulty and other established emergency warning signs must trigger immediate escalation.

Do not continue a lengthy AI interview while an emergency response is indicated.

Do not reassure a breathless user that the problem is merely anxiety or allergy without adequate evaluation.

### CATEGORY 4 — CHEST PAIN

Ask relevant questions about:
- Location and onset.
- Nature of the pain.
- Duration.
- Whether the pain spreads elsewhere.
- Breathlessness.
- Sweating, fainting, nausea, or other associated symptoms.
- Relevant medical history.

Emergency warning signs must be evaluated immediately.

Do not use a chatbot to rule out a heart attack or another serious cause.

Possible explanations must remain educational and secondary to appropriate safety guidance.

### CATEGORY 5 — HEADACHE AND DIZZINESS

Ask about:
- Sudden versus gradual onset.
- Severity and progression.
- Vision or speech changes.
- Weakness, numbness, confusion, or fainting.
- Fever and neck stiffness.
- Recent head injury.
- Relevant medical history.

Severe sudden headache, new neurological symptoms, significant injury, or other documented warning signs must trigger appropriate urgent or emergency guidance.

Possible explanations may include migraine, tension-type headache, dehydration-related concerns, and other causes where appropriate.

Do not diagnose stroke, migraine, or another neurological condition from a conversational model alone.

### CATEGORY 6 — ABDOMINAL PAIN

Ask about:
- Location.
- Onset and duration.
- Severity and progression.
- Vomiting.
- Fever.
- Abdominal swelling.
- Blood in vomit or stool.
- Urinary symptoms.
- Relevant pregnancy possibility where appropriate and voluntarily disclosed.

Escalate concerning patterns using documented safety rules.

Do not automatically label abdominal pain as acidity or indigestion.

### CATEGORY 7 — VOMITING AND DIARRHEA

Ask about:
- Duration and frequency.
- Ability to keep fluids down.
- Signs that may suggest dehydration.
- Urine output changes.
- Blood in stool or vomit.
- Fever.
- Severe abdominal pain.
- Relevant vulnerability factors.

Provide general educational guidance when appropriate.

Identify warning signs that require medical evaluation. Do not prescribe medication or invent dosage instructions.

### CATEGORY 8 — URINARY PROBLEMS

Ask about:
- Pain or burning during urination.
- Urination frequency.
- Visible blood.
- Fever or chills.
- Back or flank pain.
- Vomiting.
- Difficulty passing urine.
- Relevant pregnancy status or medical history when necessary.

Explain possible urinary or kidney-related causes cautiously.

Use documented warning signs to determine the appropriate escalation path.