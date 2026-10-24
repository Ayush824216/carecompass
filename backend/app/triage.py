"""Care type + urgency decision: local model (A or C), optional LLM (B), asymmetric-safety combine."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from .config import get_settings
from .schemas import EMERGENCY_CARE_TYPE, MOST_URGENT, URGENCY_RANK
from .textclf import best_local_model

log = logging.getLogger("carecompass.triage")


@lru_cache
def triage_cfg() -> dict:
    return json.loads((get_settings().config_dir / "triage.json").read_text(encoding="utf-8"))


@dataclass
class Decision:
    care_type: str
    urgency: str
    source: str
    confidence: float = 0.0
    probs: dict = field(default_factory=dict)
    red_flags: list[str] = field(default_factory=list)
    llm_reasoning: Optional[str] = None


def _argmax(d: dict[str, float], exclude: tuple[str, ...] = ()) -> tuple[str, float]:
    items = [(k, v) for k, v in d.items() if k not in exclude] or list(d.items())
    return max(items, key=lambda kv: kv[1])


def decide_from_probs(probs: dict[str, dict[str, float]], cfg: Optional[dict] = None) -> tuple[str, str, float]:
    cfg = cfg or triage_cfg()
    pc, pu = probs["care_type"], probs["urgency"]
    p_em = max(pc.get(EMERGENCY_CARE_TYPE, 0.0), pu.get(MOST_URGENT, 0.0))
    if cfg.get("coherent_emergency", True):
        if p_em >= cfg["emergency_threshold"]:
            return EMERGENCY_CARE_TYPE, MOST_URGENT, p_em
        care, pcare = _argmax(pc, (EMERGENCY_CARE_TYPE,))
        nonimm = {k: v for k, v in pu.items() if k != MOST_URGENT}
        tot = sum(nonimm.values()) or 1.0
        urg = "same_day" if nonimm.get("same_day", 0) / tot >= cfg.get("same_day_threshold", 0.5) else "routine"
        return care, urg, pcare
    care, pcare = _argmax(pc)
    urg, _ = _argmax(pu)
    return care, urg, pcare


def more_urgent(a: str, b: str) -> str:
    return a if URGENCY_RANK.get(a, 0) >= URGENCY_RANK.get(b, 0) else b


def local_decision(text: str) -> Optional[Decision]:
    m = best_local_model()
    if m is None:
        return None
    probs = m.predict_proba(text)
    care, urg, conf = decide_from_probs(probs)
    return Decision(care_type=care, urgency=urg, source=m.name, confidence=conf, probs=probs)


def combine(local: Optional[Decision], llm: Optional[Decision]) -> Optional[Decision]:
    """Prefer the LLM when valid; on urgency disagreement take the MORE urgent one."""
    if llm is None:
        return local
    if local is None:
        return llm
    out = Decision(care_type=llm.care_type, urgency=more_urgent(llm.urgency, local.urgency),
                   source=f"{llm.source}+{local.source}", confidence=llm.confidence, probs=local.probs,
                   red_flags=llm.red_flags, llm_reasoning=llm.llm_reasoning)
    if local.care_type == EMERGENCY_CARE_TYPE or out.urgency == MOST_URGENT:
        out.care_type, out.urgency = EMERGENCY_CARE_TYPE, MOST_URGENT
    return out
