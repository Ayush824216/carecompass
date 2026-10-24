"""stomach pathway: rules, signs and questions live in config/pathways/stomach.json (mentor-reviewable)."""
from __future__ import annotations

from .engine import PathwayResult, build_facts, detect_signs, evaluate_pathway, load
from .slots import parse

PATHWAY_ID = "stomach"
NOTES = {"doctor_today": {"en": "Iron tablets can darken stool, but a doctor should check today.", "hi": "आयरन की गोली से पॉटी काली हो सकती है, फिर भी आज ही डॉक्टर को दिखाएँ।", "hinglish": "Iron ki goli se potty kaali ho sakti hai, phir bhi aaj hi doctor ko dikhayein."}}


def evaluate(user_texts: list[str]) -> PathwayResult:
    """Evaluate only this pathway on the given user texts (used by tests and tools)."""
    _, pathways, _ = load()
    slots = parse(user_texts)
    facts, neg, known = build_facts(slots, detect_signs(slots))
    return evaluate_pathway(pathways[PATHWAY_ID], facts, neg, known)
