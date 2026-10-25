"""Mood / mental health pathway: rules, signs and questions live in config/pathways/mood.json. Never a disease label or medicine."""
from __future__ import annotations

from .engine import PathwayResult, build_facts, detect_signs, evaluate_pathway, load
from .slots import parse

PATHWAY_ID = "mood"
NOTES: dict = {"perinatal": {"en": "Support for feelings during and after pregnancy (perinatal mental health) is part of care; the gynaecologist can help too. Tele-MANAS 14416 is free, 24x7.", "hi": "गर्भावस्था के दौरान और बाद की भावनाओं के लिए मदद (पेरिनेटल मानसिक स्वास्थ्य) इलाज का हिस्सा है; स्त्री रोग विशेषज्ञ भी मदद कर सकती हैं। टेली-मानस 14416 मुफ़्त, 24x7।", "hinglish": "Pregnancy ke dauran aur baad ki feelings ke liye madad (perinatal mental health) ilaaj ka hissa hai; gynaecologist bhi madad kar sakti hain. Tele-MANAS 14416 muft, 24x7."}}


def evaluate(user_texts: list[str]) -> PathwayResult:
    """Evaluate only this pathway on the given user texts (used by tests and tools)."""
    _, pathways, _ = load()
    slots = parse(user_texts)
    facts, neg, known = build_facts(slots, detect_signs(slots))
    return evaluate_pathway(pathways[PATHWAY_ID], facts, neg, known)
