"""fever pathway: rules, signs and questions live in config/pathways/fever.json (mentor-reviewable)."""
from __future__ import annotations

from .engine import PathwayResult, build_facts, detect_signs, evaluate_pathway, load
from .slots import parse

PATHWAY_ID = "fever"
NOTES = {"home_blood_test": {"en": "A home blood test visit is also advised.", "hi": "घर पर खून की जाँच भी करवानी चाहिए।", "hinglish": "Ghar par blood test bhi karwana chahiye."}}


def evaluate(user_texts: list[str]) -> PathwayResult:
    """Evaluate only this pathway on the given user texts (used by tests and tools)."""
    _, pathways, _ = load()
    slots = parse(user_texts)
    facts, neg, known = build_facts(slots, detect_signs(slots))
    return evaluate_pathway(pathways[PATHWAY_ID], facts, neg, known)
