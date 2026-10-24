"""Small grounded knowledge base (kb/chunks.jsonl) with deterministic retrieval and citations.

Chunks (id, source, title, text) come only from our own curated material: the clinical pathway stage routing
(config/pathways), the sections of docs/CLINICAL_PATHWAYS.md and docs/SYMPTOM_CATEGORIES.md, the care-type and
urgency taxonomy, and the curated precautions in config/assessment.json. Built by scripts/build_kb.py; rebuilt in
memory if the file is missing. Retrieval: TF-IDF char n-gram cosine, fixed top-k, ties broken by chunk id, and a
minimum score below which nothing is cited (that part of the explanation is left out). No generated text.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .config import ROOT, get_settings

KB_FILE = ROOT / "kb" / "chunks.jsonl"
TOP_K = 3
MIN_SCORE = 0.12
DOCS = {"docs/CLINICAL_PATHWAYS.md": ("cp", "Clinical pathways spec"),
        "docs/SYMPTOM_CATEGORIES.md": ("sc", "Symptom categories")}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:48]


def build_chunks() -> list[dict]:
    from . import data_adapter
    from .pathways import engine
    common, pathways, _ = engine.load()
    tax = data_adapter.load_taxonomy()
    ct_def = {c["id"]: c.get("definition_en", "") for c in tax.get("care_types", [])}
    ur_def = {u["id"]: u.get("definition_en", "") for u in tax.get("urgency_levels", [])}
    chunks = []
    for pid, p in pathways.items():
        label = p.label.get("en") if isinstance(p.label, dict) else str(p.label)
        for st, route in p.cfg["stages"].items():
            stage = common["stages"][st]
            stage = stage.get("en") if isinstance(stage, dict) else stage
            chunks.append({"id": f"pathway:{pid}:{st}", "source": f"config/pathways/{pid}.json",
                           "title": f"Clinical pathway – {label} {st}",
                           "text": f"{label} pathway, stage {st} ({stage}): {route['care_type']} "
                                   f"({ct_def.get(route['care_type'], '')}), urgency {route['urgency']} "
                                   f"({ur_def.get(route['urgency'], '')})."})
    for cid, d in ct_def.items():
        chunks.append({"id": f"taxonomy:care:{cid}", "source": "taxonomy", "title": f"Care type – {cid}", "text": d})
    for uid, d in ur_def.items():
        chunks.append({"id": f"taxonomy:urgency:{uid}", "source": "taxonomy", "title": f"Urgency – {uid}", "text": d})
    from .assessment import load_cfg
    for cat, spec in load_cfg()["categories"].items():
        text = " ".join(x["en"] for x in spec.get("precautions", []) + spec.get("call_112_if", []))
        chunks.append({"id": f"care:{cat}", "source": "config/assessment.json", "title": f"Precautions – {cat}",
                       "text": text})
    for rel, (prefix, title) in DOCS.items():
        p = ROOT / rel
        if not p.exists():
            continue
        head, buf = None, []
        for line in p.read_text(encoding="utf-8").splitlines() + ["## end"]:
            if line.startswith("## ") or line.startswith("### "):
                body = " ".join(x.strip() for x in buf if x.strip())
                if head and len(body) > 40:
                    chunks.append({"id": f"{prefix}:{_slug(head)}", "source": rel, "title": f"{title} – {head}",
                                   "text": body[:1500]})
                head, buf = line.lstrip("# ").strip(), []
            else:
                buf.append(line)
    seen, out = set(), []
    for c in chunks:  # ids are unique and stable
        if c["id"] not in seen:
            seen.add(c["id"])
            out.append(c)
    return sorted(out, key=lambda c: c["id"])


@lru_cache
def chunks() -> list[dict]:
    if KB_FILE.exists():
        return [json.loads(l) for l in KB_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    return build_chunks()


@lru_cache
def _index():
    from sklearn.feature_extraction.text import TfidfVectorizer
    cs = chunks()
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    return vec, vec.fit_transform([f"{c['title']} {c['text']}".lower() for c in cs])


def by_id(cid: str) -> dict | None:
    return next((c for c in chunks() if c["id"] == cid), None)


def retrieve(query: str, k: int = TOP_K, prefix: str = "", min_score: float = MIN_SCORE) -> list[dict]:
    """Top-k chunks (optionally with an id prefix), score >= min_score, ties broken by id (deterministic)."""
    vec, M = _index()
    sims = (M @ vec.transform([query.lower()]).T).toarray().ravel()
    rows = [(round(float(s), 6), c["id"]) for s, c in zip(sims, chunks()) if c["id"].startswith(prefix)]
    rows = sorted((r for r in rows if r[0] >= min_score), key=lambda r: (-r[0], r[1]))[:k]
    return [{"id": cid, "title": by_id(cid)["title"], "score": round(s, 3)} for s, cid in rows]


def cite(cid: str) -> dict | None:
    c = by_id(cid)
    return {"id": cid, "title": c["title"], "score": 1.0} if c else None
