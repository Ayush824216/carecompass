"""Per-request privacy mode and anonymised metrics.

- Incognito (request header `X-Incognito: 1`): no response cache, no metrics, no latency log line, and no LLM
  call (local models only) for that request.
- LOCAL_ONLY=true (env): no external API call for any request; the decision panel shows "Processed locally".
- Metrics are counts only (decision classes, stages, latency buckets): never text, never health details per user.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar

_incognito: ContextVar[bool] = ContextVar("incognito", default=False)


def incognito() -> bool:
    return _incognito.get()


@contextmanager
def request_mode(is_incognito: bool):
    tok = _incognito.set(bool(is_incognito))
    try:
        yield
    finally:
        _incognito.reset(tok)


def local_only() -> bool:
    from .config import get_settings
    return get_settings().local_only or incognito()


# ---------------------------------------------------------------- anonymised metrics
LAT_BUCKETS_MS = (50, 100, 250, 500, 1000, 3000)
_lock = threading.Lock()
_m: dict = {}


def reset_metrics() -> None:
    with _lock:
        _m.clear()
        _m.update({"requests": 0, "domain_class": {}, "care_type": {}, "urgency": {}, "pathway_stage": {},
                   "follow_up_questions": 0, "emergencies": 0, "latency_ms": {f"<={b}": 0 for b in LAT_BUCKETS_MS} | {">3000": 0}})


reset_metrics()


def record(body: dict, trace: dict, total_ms: float) -> None:
    """Count one answered request (never called in incognito). Only labels and buckets, no text."""
    if incognito():
        return
    with _lock:
        _m["requests"] += 1
        for key, val in (("domain_class", trace.get("domain_class")), ("care_type", body.get("care_type")),
                         ("urgency", body.get("urgency"))):
            if val:
                _m[key][val] = _m[key].get(val, 0) + 1
        prim = ((trace.get("pathways") or {}).get("primary") or {})
        if prim.get("pathway"):
            k = f"{prim['pathway']}:{prim.get('stage')}"
            _m["pathway_stage"][k] = _m["pathway_stage"].get(k, 0) + 1
        _m["follow_up_questions"] += int(bool(body.get("follow_up_question")))
        _m["emergencies"] += int(body.get("care_type") == "emergency_referral")
        b = next((f"<={x}" for x in LAT_BUCKETS_MS if total_ms <= x), ">3000")
        _m["latency_ms"][b] += 1


def metrics() -> dict:
    with _lock:
        import copy
        return copy.deepcopy(_m)
