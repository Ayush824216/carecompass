"""Complaint-based clinical pathways (fever, cough, stomach, chest pain, headache). See docs/CLINICAL_PATHWAYS.md."""
from .engine import (PathwayOutcome, PathwayResult, chip_options, identify_question, load, next_question,  # noqa: F401
                     question_text, run, sign_label)

PATHWAY_IDS = ("fever", "cough", "stomach", "chest_pain", "headache")
