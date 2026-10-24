"""Learned input-type classifier (backup to the domain-guard rules): health | greeting_smalltalk | off_topic |
gibberish | math_or_code. Trained by scripts/train_input_type.py into models/input_type.joblib.

It never opens clinical questioning by itself (that needs an evidence span, see app.evidence); it only picks a more
specific non-health reply. Without the model file the rules work alone. Simple gibberish features (lexicon share,
vowel pattern, repeated syllables) back it up and need no model.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Optional

from .config import get_settings
from .lang import clean

log = logging.getLogger("carecompass.input_type")

CLASSES = ("health", "greeting_smalltalk", "off_topic", "gibberish", "math_or_code")
MIN_CONF = 0.6
WORD = re.compile(r"[a-zऀ-ॿ]+", re.I)


def build_pipeline(seed: int = 7):
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline
    feats = FeatureUnion([
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=2, lowercase=True)),
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True, min_df=1, lowercase=True,
                                 token_pattern=r"(?u)\b\w+\b")),
    ])
    lr = LogisticRegression(C=4.0, max_iter=3000, class_weight="balanced", random_state=seed)
    return Pipeline([("feats", feats), ("clf", CalibratedClassifierCV(lr, cv=3, method="sigmoid"))])


@lru_cache
def _model():
    p = get_settings().models_dir / "input_type.joblib"
    if not p.exists():
        log.warning("input_type.joblib not found at %s; run scripts/train_input_type.py (rules still work)", p)
        return None
    import joblib
    return joblib.load(p)


def proba(text: str) -> Optional[dict[str, float]]:
    m = _model()
    if m is None or not (text or "").strip():
        return None
    p = m.predict_proba([clean(text)])[0]
    return {c: float(v) for c, v in zip(m.classes_, p)}


# guard class names for the classifier's labels
TO_GUARD = {"greeting_smalltalk": "greeting_smalltalk", "off_topic": "off_topic", "gibberish": "unclear_or_gibberish",
            "math_or_code": "math_or_code", "health": "health_request"}


def predict(text: str, min_conf: float = MIN_CONF) -> Optional[str]:
    """Guard class name when the classifier is confident, else None."""
    p = proba(text)
    if not p:
        return None
    best = max(sorted(p), key=lambda c: p[c])  # sorted first: a tie always resolves the same way
    return TO_GUARD[best] if p[best] >= min_conf else None


# ---------------------------------------------------------------- simple gibberish features (no model needed)
@lru_cache
def lexicon() -> frozenset[str]:
    """Words we know: our vignettes, question bank, greetings and the language rules."""
    import json
    words: set[str] = set()
    s = get_settings()
    for p in list(s.dev_data_dir.glob("*.csv")) + list(s.config_dir.rglob("*.json")):
        try:
            words |= {w.lower() for w in WORD.findall(p.read_text(encoding="utf-8"))}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
    from . import domain_guard
    words |= domain_guard.GREET_FILLER
    return frozenset(w for w in words if len(w) > 1)


def lexicon_share(text: str) -> float:
    toks = [w.lower() for w in WORD.findall(clean(text))]
    return sum(t in lexicon() for t in toks) / len(toks) if toks else 0.0


def repeated_syllables(text: str) -> bool:
    """'abba dabba jabba', 'lala lala': tokens that rhyme on the same ending, or one syllable repeated."""
    toks = [w.lower() for w in WORD.findall(clean(text))]
    if len(toks) >= 2:
        ends = [t[-3:] for t in toks if len(t) >= 3]
        if ends and max(ends.count(e) for e in set(ends)) >= 2 and len(set(toks)) >= 2:
            return True
    return any(re.fullmatch(r"(\w{1,3})\1{2,}", t) for t in toks)


def vowel_odd(text: str) -> bool:
    latin = [w for w in WORD.findall(clean(text)) if re.match(r"[a-z]", w, re.I)]
    return bool(latin) and all((len(w) >= 4 and not re.search(r"[aeiouy]", w, re.I)) or re.search(r"[^aeiouy\W\d]{4,}", w, re.I)
                               for w in latin)


def gibberish_features(text: str) -> dict:
    return {"lexicon_share": round(lexicon_share(text), 3), "repeated_syllables": repeated_syllables(text),
            "vowel_odd": vowel_odd(text)}


def looks_gibberish(text: str) -> bool:
    """Backup rule: mostly unknown words that rhyme / repeat or have no vowel pattern."""
    f = gibberish_features(text)
    return f["lexicon_share"] < 0.5 and (f["repeated_syllables"] or f["vowel_odd"] or f["lexicon_share"] == 0.0)
