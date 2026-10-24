"""Urinary problems pathway: rules, signs and questions live in config/pathways/urinary.json (mentor-reviewable)."""
from __future__ import annotations

from .engine import PathwayResult, build_facts, detect_signs, evaluate_pathway, load
from .slots import parse

PATHWAY_ID = "urinary"
NOTES = {"urine_test": {"en": "A urine test helps the doctor; the paramedic can collect the sample at home.", "hi": "पेशाब की जाँच से डॉक्टर को मदद मिलती है; पैरामेडिक घर से सैंपल ले सकते हैं।", "hinglish": "Peshab ki jaanch se doctor ko madad milti hai; paramedic ghar se sample le sakte hain."}, "sugar_test": {"en": "A blood sugar check is worth doing.", "hi": "ब्लड शुगर की जाँच करवाना ठीक रहेगा।", "hinglish": "Blood sugar ki jaanch karwana theek rahega."}}


def evaluate(user_texts: list[str]) -> PathwayResult:
    """Evaluate only this pathway on the given user texts (used by tests and tools)."""
    _, pathways, _ = load()
    slots = parse(user_texts)
    facts, neg, known = build_facts(slots, detect_signs(slots))
    return evaluate_pathway(pathways[PATHWAY_ID], facts, neg, known)
