"""Single adapter layer for every data source.

All loaders resolve paths from Settings and map external column names / label strings
to internal ones via config/label_map.json. Swap in the official files by dropping them
into OFFICIAL_DIR: they take precedence over dev_data automatically.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from .config import get_settings

IST = timezone(timedelta(hours=5, minutes=30))


@lru_cache
def label_map() -> dict:
    return json.loads((get_settings().config_dir / "label_map.json").read_text(encoding="utf-8"))


def norm_label(kind: str, value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return None
    return label_map()[kind].get(s.lower(), label_map()[kind].get(s, s))


def _first(*paths: Path) -> Optional[Path]:
    return next((p for p in paths if p and p.exists()), None)


def _find_official(stem_keywords: tuple[str, ...], exts: tuple[str, ...]) -> Optional[Path]:
    d = get_settings().official_dir
    if not d.exists():
        return None
    for p in sorted(d.rglob("*")):
        if p.suffix.lower() in exts and any(k in p.stem.lower() for k in stem_keywords):
            return p
    return None


def _map_columns(row: dict) -> dict:
    cols = label_map()["columns"]
    lower = {k.strip().lower(): v for k, v in row.items() if k is not None}
    out = {}
    for internal, candidates in cols.items():
        for c in candidates:
            if c in lower:
                out[internal] = lower[c]
                break
    return out


def read_vignette_file(path: Path) -> list[dict]:
    """Read a vignette CSV/JSON(L) into internal rows: id, text, language, care_type, urgency."""
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as f:
            raw = list(csv.DictReader(f))
    elif path.suffix.lower() == ".jsonl":
        raw = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data if isinstance(data, list) else next(v for v in data.values() if isinstance(v, list))
    rows = []
    for i, r in enumerate(raw):
        m = _map_columns(r)
        if not m.get("text"):
            continue
        rows.append({
            "id": m.get("id") or f"ROW_{i:05d}",
            "text": str(m["text"]),
            "language": m.get("language") or None,
            "care_type": norm_label("care_type", m.get("care_type")),
            "urgency": norm_label("urgency", m.get("urgency")),
        })
    return rows


def vignettes_path() -> Path:
    s = get_settings()
    off = _find_official(("train", "vignette"), (".csv", ".json", ".jsonl"))
    return off or s.dev_data_dir / "vignettes.csv"


def load_vignettes() -> list[dict]:
    return read_vignette_file(vignettes_path())


def load_processed_public() -> list[dict]:
    """Rows produced by scripts/prepare_public_data.py (may be empty if not prepared)."""
    p = get_settings().processed_dir / "public_train.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


@lru_cache
def load_taxonomy() -> dict:
    s = get_settings()
    p = _find_official(("taxonomy",), (".json",)) or s.dev_data_dir / "taxonomy.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _parse_dt(s: str) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=IST)
    except ValueError:
        return None


@lru_cache
def load_caregivers() -> list[dict]:
    s = get_settings()
    off = _find_official(("caregiver",), (".json", ".csv"))
    p = off or s.dev_data_dir / "caregivers.json"
    if p.suffix.lower() == ".csv":
        with open(p, encoding="utf-8-sig", newline="") as f:
            raw = list(csv.DictReader(f))
        for r in raw:
            for k in ("skills", "languages", "availability_slots"):
                v = r.get(k) or ""
                r[k] = json.loads(v) if v.startswith("[") else [x.strip() for x in v.replace(";", ",").split(",") if x.strip()]
            for k in ("lat", "lng", "rating"):
                r[k] = float(r.get(k) or 0)
    else:
        data = json.loads(p.read_text(encoding="utf-8"))
        raw = data if isinstance(data, list) else next(v for v in data.values() if isinstance(v, list))
    if off is None:
        raw = _shift_stale_dev_slots(raw)
    return raw


def _shift_stale_dev_slots(cgs: list[dict]) -> list[dict]:
    """Dev data only: if the generated slots are in the past, shift them so day 1 is today."""
    all_dt = [d for c in cgs for d in map(_parse_dt, c.get("availability_slots", [])) if d]
    if not all_dt:
        return cgs
    today = datetime.now(IST).date()
    first = min(all_dt).astimezone(IST).date()
    delta = (today - first).days
    if delta <= 0:
        return cgs
    out = []
    for c in cgs:
        c = dict(c)
        c["availability_slots"] = [(d + timedelta(days=delta)).isoformat()
                                   for d in map(_parse_dt, c.get("availability_slots", [])) if d]
        out.append(c)
    return out


def caregiver_by_id(cid: str) -> Optional[dict]:
    return next((c for c in load_caregivers() if c["caregiver_id"] == cid), None)


def parse_slot(s: str) -> Optional[datetime]:
    return _parse_dt(s)
