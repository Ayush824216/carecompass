"""Model B: LLM triage with taxonomy definitions + k nearest training examples as few-shot context.

Retrieval uses TF-IDF char n-gram cosine (fast, CPU, handles Hinglish spelling). Output is validated strictly;
anything invalid returns None so the caller falls back to the local model.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Optional

from . import data_adapter, llm, safety
from .lang import clean, normalise
from .schemas import CARE_TYPES, URGENCIES
from .triage import Decision, triage_cfg

log = logging.getLogger("carecompass.llm_triage")


class Retriever:
    def __init__(self, rows: list[dict]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.rows = [r for r in rows if r.get("care_type") and r.get("urgency")]
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)
        self.M = self.vec.fit_transform([f"{clean(r['text']).lower()} {normalise(r['text'])}" for r in self.rows])

    def top_k(self, text: str, k: int = 5) -> list[dict]:
        q = self.vec.transform([f"{clean(text).lower()} {normalise(text)}"])
        sims = (self.M @ q.T).toarray().ravel()
        idx = sims.argsort()[::-1][:k]
        return [self.rows[i] for i in idx]


@lru_cache
def retriever() -> Retriever:
    return Retriever(data_adapter.load_vignettes())


@lru_cache
def _blocklist() -> re.Pattern:
    """Disease names (internal mapping) + common medicine words that must never appear in user-facing text."""
    from .config import get_settings
    groups = json.loads((get_settings().config_dir / "disease_to_care_type.json").read_text(encoding="utf-8"))["groups"]
    names = {d for by_u in groups.values() for ds in by_u.values() for d in ds if len(d) > 3}
    names -= {"allergy", "flu", "common cold", "indigestion", "insect bite"}  # everyday words users say themselves
    meds = ["paracetamol", "ibuprofen", "aspirin", "antibiotic", "crocin", "dolo", "calpol", "combiflam", "azithromycin",
            "amoxicillin", "metformin", "insulin dose", "ors sachet", "cetirizine", "dose of", "mg ", "tablet of",
            "diagnos", "you have ", "suffering from", "infection", "virus"]
    alts = sorted((re.escape(n) for n in names | set(meds)), key=len, reverse=True)
    return re.compile(r"(" + "|".join(alts) + r")", re.I)


def safe_text(s: str) -> bool:
    return bool(s) and not _blocklist().search(s)


def _definitions(lang: str) -> str:
    tax = data_adapter.load_taxonomy()
    ct = "\n".join(f"- {c['id']}: {c.get('definition_en', '')}" for c in tax.get("care_types", []))
    ur = "\n".join(f"- {u['id']}: {u.get('definition_en', '')}" for u in tax.get("urgency_levels", []))
    rf = ", ".join(safety.FLAG_LABELS)
    return f"CARE TYPES:\n{ct}\n\nURGENCY:\n{ur}\n\nRED FLAG IDS: {rf}"


LANG_NAME = {"en": "simple English", "hi": "simple Hindi in Devanagari script", "hinglish": "simple Hinglish (Hindi in Latin script)"}


def system_prompt(lang: str) -> str:
    return (
        "You are the routing engine of an Indian home-healthcare service. You route requests; you NEVER diagnose, "
        "never name diseases and never suggest medicines.\n"
        "Pick exactly one care_type and one urgency using these definitions.\n\n"
        f"{_definitions(lang)}\n\n"
        "Rules:\n"
        "1. If any red flag is present (and not negated, e.g. 'no chest pain' is NOT a red flag), use "
        "emergency_referral + immediate and list the red flag ids.\n"
        "2. Elderly, infants, or people who cannot travel favour home visits over teleconsult.\n"
        "3. Long-standing (weeks/months) or organ-specific problems favour specialist_referral.\n"
        "4. When torn between two urgency levels, choose the more urgent one.\n"
        f"5. reasoning: one or two short sentences in {LANG_NAME.get(lang, 'simple English')}, based only on the "
        "user's own words (symptoms, duration, who). No disease names, no medicines, no diagnosis.\n"
        'Reply with JSON only: {"care_type": str, "urgency": str, "red_flags": [str], "reasoning": str}'
    )


def user_prompt(text: str, history_text: str, examples: list[dict]) -> str:
    ex = "\n".join(f'Input: "{e["text"]}" -> {{"care_type": "{e["care_type"]}", "urgency": "{e["urgency"]}"}}'
                   for e in examples)
    conv = f"\nConversation so far (user turns and answers):\n{history_text}\n" if history_text else ""
    return f"Labelled examples of similar requests:\n{ex}\n{conv}\nRequest to route: \"{text}\""


def validate(obj: Optional[dict]) -> Optional[dict]:
    if not isinstance(obj, dict):
        return None
    ct, ur = obj.get("care_type"), obj.get("urgency")
    if ct not in CARE_TYPES or ur not in URGENCIES:
        return None
    flags = obj.get("red_flags") or []
    if not isinstance(flags, list):
        flags = []
    flags = [f for f in flags if isinstance(f, str) and f in safety.FLAG_LABELS]
    reasoning = obj.get("reasoning") if isinstance(obj.get("reasoning"), str) else ""
    if not safe_text(reasoning):
        reasoning = ""
    return {"care_type": ct, "urgency": ur, "red_flags": flags, "reasoning": reasoning.strip()[:400]}


def llm_decision(text: str, lang: str, history_text: str = "") -> Optional[Decision]:
    if not llm.available():
        return None
    k = int(triage_cfg().get("llm_k_examples", 5))
    try:
        examples = retriever().top_k(f"{history_text} {text}", k=k)
    except Exception:
        examples = []
    out = validate(llm.chat_json(system_prompt(lang), user_prompt(text, history_text, examples)))
    if out is None:
        return None
    return Decision(care_type=out["care_type"], urgency=out["urgency"], source="llm", confidence=0.8,
                    red_flags=out["red_flags"], llm_reasoning=out["reasoning"] or None)
