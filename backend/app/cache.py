"""Response cache: the same request gives the same answer (consistency, like grounded RAG).

Key = SHA-256 of (normalised user input + conversation history + assessment_state + language + location + debug flag
+ version). The version hashes every config file, the trained model files and CACHE_VERSION, so a new model or
config never serves an old answer. Entries live in process memory only, expire after RESPONSE_CACHE_TTL_S
(default 900 s) and are never written to disk; only the hash of the request text is kept as the key.

The decision path itself is deterministic (rules -> pathway -> local model -> combine; LLM at temperature 0 with a
fixed seed where the provider supports one). The cache also pins what still depends on the clock (caregiver slots)
and on a remote LLM, so a repeated request within the TTL is answered identically.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from collections import OrderedDict
from functools import lru_cache
from typing import Any, Optional

from .config import get_settings
from .lang import clean

CACHE_VERSION = "1"
MAX_ENTRIES = 1024


@lru_cache
def version() -> str:
    """Hash of config contents + model file names/sizes + LLM model name (never the key)."""
    s = get_settings()
    h = hashlib.sha256(CACHE_VERSION.encode())
    for p in sorted(s.config_dir.rglob("*.json")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    if s.models_dir.exists():
        for p in sorted(s.models_dir.rglob("*")):
            if p.is_file():
                h.update(f"{p.relative_to(s.models_dir)}:{p.stat().st_size}:{int(p.stat().st_mtime)}".encode())
    h.update(f"{s.llm_provider}:{s.llm_model}".encode())
    return h.hexdigest()[:16]


def _norm(t: Optional[str]) -> str:
    return clean(t or "").lower()


def key(req, debug: bool) -> str:
    body = {
        "u": _norm(req.user_input),
        "h": [[t.role, _norm(t.content)] for t in req.conversation_history if t.content],
        "s": req.assessment_state or None,
        "l": req.language,
        "loc": [round(req.location.lat, 5), round(req.location.lng, 5)] if req.location else None,
        "d": bool(debug),
        "v": version(),
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, ttl_s: float, max_entries: int = MAX_ENTRIES) -> None:
        self.ttl_s, self.max_entries = ttl_s, max_entries
        self._d: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = self.misses = 0

    def get(self, k: str) -> Optional[Any]:
        if self.ttl_s <= 0:
            return None
        with self._lock:
            hit = self._d.get(k)
            if hit is None or time.monotonic() - hit[0] > self.ttl_s:
                self._d.pop(k, None)
                self.misses += 1
                return None
            self._d.move_to_end(k)
            self.hits += 1
            return copy.deepcopy(hit[1])

    def put(self, k: str, value: Any) -> None:
        if self.ttl_s <= 0:
            return
        with self._lock:
            self._d[k] = (time.monotonic(), copy.deepcopy(value))
            self._d.move_to_end(k)
            while len(self._d) > self.max_entries:
                self._d.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._d.clear()
            self.hits = self.misses = 0


@lru_cache
def response_cache() -> ResponseCache:
    return ResponseCache(get_settings().response_cache_ttl_s)
