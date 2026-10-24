"""Local text classifiers for care_type and urgency.

Model A: TF-IDF (word 1-2 grams on normalised text + char_wb 2-5 grams on raw text) + LogisticRegression
(class_weight="balanced"). CPU-only, always available.
Model C (optional): fine-tuned multilingual transformer, loaded lazily if torch + weights exist.
"""
from __future__ import annotations

import json
import logging
import random
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .config import get_settings
from .lang import clean, normalise

log = logging.getLogger("carecompass.textclf")


def model_input(text: str) -> str:
    """Raw lower-cased text plus its canonical-English normalisation."""
    return f"{clean(text).lower()} || {normalise(text)}"


def build_pipeline(C: float = 4.0):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline

    feats = FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True, min_df=1,
                                 token_pattern=r"[^\s|,.!?।]+")),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=2,
                                 max_features=150_000)),
    ])
    return Pipeline([("feats", feats),
                     ("clf", LogisticRegression(C=C, class_weight="balanced", max_iter=3000))])


def stratified_split(rows: list[dict], val_frac: float = 0.2, seed: int = 42,
                     key=lambda r: (r.get("care_type"), r.get("urgency"))) -> tuple[list[dict], list[dict]]:
    """Deterministic stratified split shared by train.py and evaluate.py."""
    groups: dict = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    rng = random.Random(seed)
    tr, va = [], []
    for k in sorted(groups, key=str):
        g = sorted(groups[k], key=lambda r: str(r.get("id", r.get("text"))))
        rng.shuffle(g)
        n_val = max(1, round(len(g) * val_frac)) if len(g) >= 3 else 0
        va += g[:n_val]
        tr += g[n_val:]
    return tr, va


SOURCE_WEIGHT = {"dev": 1.0, "official": 1.0, "ktas": 0.6, "symptoms_to_diseases": 0.35, "symptom_severity": 0.35}


def fit_models(rows: list[dict], C: float = 4.0) -> dict:
    """Fit care_type and urgency classifiers on internal-format rows (labels may be None)."""
    out = {}
    for target in ("care_type", "urgency"):
        data = [r for r in rows if r.get(target)]
        X = [model_input(r["text"]) for r in data]
        y = [r[target] for r in data]
        w = [SOURCE_WEIGHT.get(r.get("source", "dev"), 1.0) for r in data]
        pipe = build_pipeline(C)
        pipe.fit(X, y, clf__sample_weight=w)
        out[target] = pipe
    return out


class LocalModel:
    """Uniform predict_proba interface over Model A (sklearn) or Model C (transformer)."""

    name = "tfidf_lr"

    def __init__(self, models: dict):
        self.models = models

    def predict_proba(self, text: str) -> dict[str, dict[str, float]]:
        x = [model_input(text)]
        res = {}
        for target, pipe in self.models.items():
            p = pipe.predict_proba(x)[0]
            res[target] = {c: float(v) for c, v in zip(pipe.classes_, p)}
        return res

    def predict_proba_batch(self, texts: list[str]) -> list[dict[str, dict[str, float]]]:
        x = [model_input(t) for t in texts]
        per = {t: (pipe.classes_, pipe.predict_proba(x)) for t, pipe in self.models.items()}
        return [{t: {c: float(v) for c, v in zip(cls, P[i])} for t, (cls, P) in per.items()} for i in range(len(texts))]


def save_model_a(models: dict, path: Optional[Path] = None) -> Path:
    import joblib
    path = path or get_settings().models_dir / "model_a.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(models, path)
    return path


@lru_cache
def load_model_a() -> Optional[LocalModel]:
    import joblib
    p = get_settings().models_dir / "model_a.joblib"
    if not p.exists():
        log.warning("model_a.joblib not found at %s; run scripts/train.py", p)
        return None
    return LocalModel(joblib.load(p))


@lru_cache
def load_model_c():
    """Fine-tuned transformer (Model C) if available and enabled, else None."""
    s = get_settings()
    if s.use_transformer == "false":
        return None
    d = s.models_dir / "model_c"
    if not (d / "meta.json").exists():
        return None
    try:
        from .transformer_clf import TransformerModel  # needs torch + transformers
        return TransformerModel(d)
    except Exception as e:  # torch missing in CPU Docker, etc.
        log.info("Model C unavailable (%s); using Model A", e.__class__.__name__)
        return None


@lru_cache
def best_local_model() -> Optional[LocalModel]:
    """Model C if it exists and was better on validation (meta.json 'use_in_production'), else Model A."""
    c = load_model_c()
    if c is not None:
        meta = json.loads((get_settings().models_dir / "model_c" / "meta.json").read_text(encoding="utf-8"))
        if meta.get("use_in_production", False):
            return c
    return load_model_a()
