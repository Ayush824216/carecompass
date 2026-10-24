"""cough pathway: rules, signs and questions live in config/pathways/cough.json (mentor-reviewable)."""
from __future__ import annotations

from .engine import PathwayResult, build_facts, detect_signs, evaluate_pathway, load
from .slots import parse

PATHWAY_ID = "cough"
NOTES: dict = {"tb_test": {"en": "A cough of 2 weeks or more with these signs needs a formal test at a TB centre or by a doctor (free at government centres). Symptoms alone never confirm it.",
                           "hi": "2 हफ्ते या ज़्यादा की खांसी और ये लक्षण हों तो टीबी केंद्र या डॉक्टर से पक्की जाँच करवाएँ (सरकारी केंद्रों पर मुफ़्त)। सिर्फ़ लक्षणों से यह पक्का नहीं होता।",
                           "hinglish": "2 hafte ya zyada ki khansi aur ye lakshan hon to TB centre ya doctor se pakki jaanch karwayein (sarkari centre par muft). Sirf lakshanon se yeh pakka nahi hota."}}


def evaluate(user_texts: list[str]) -> PathwayResult:
    """Evaluate only this pathway on the given user texts (used by tests and tools)."""
    _, pathways, _ = load()
    slots = parse(user_texts)
    facts, neg, known = build_facts(slots, detect_signs(slots))
    return evaluate_pathway(pathways[PATHWAY_ID], facts, neg, known)
