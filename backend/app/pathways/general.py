"""General pathway (eyes, ears, teeth, skin, a named condition): rules, signs and questions live in config/pathways/general.json. A condition name is never confirmed or denied."""
from __future__ import annotations

from .engine import PathwayResult, build_facts, detect_signs, evaluate_pathway, load
from .slots import parse

PATHWAY_ID = "general"
NOTES: dict = {"rabies": {"en": "Wash the bite or scratch with soap and running water for 15 minutes; rabies protection is needed today.", "hi": "काटे या खरोंच वाली जगह को साबुन और बहते पानी से 15 मिनट धोएँ; रेबीज़ से बचाव आज ही ज़रूरी है।", "hinglish": "Kaate ya kharonch wali jagah ko sabun aur behte paani se 15 minute dhoyein; rabies se bachav aaj hi zaroori hai."}}


def evaluate(user_texts: list[str]) -> PathwayResult:
    """Evaluate only this pathway on the given user texts (used by tests and tools)."""
    _, pathways, _ = load()
    slots = parse(user_texts)
    facts, neg, known = build_facts(slots, detect_signs(slots))
    return evaluate_pathway(pathways[PATHWAY_ID], facts, neg, known)
