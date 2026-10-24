"""Complaint-based clinical pathways for the eight symptom categories (docs/CLINICAL_PATHWAYS.md,
docs/SYMPTOM_CATEGORIES.md): fever, cough, breathing, chest pain, headache and dizziness, abdominal pain,
vomiting and loose motions, urinary problems."""
from .engine import (PathwayOutcome, PathwayResult, chip_options, identify_question, load, next_question,  # noqa: F401
                     question_text, run, sign_label)

PATHWAY_IDS = ("fever", "cough", "breathing", "chest_pain", "headache", "abdominal", "vomiting", "urinary")
