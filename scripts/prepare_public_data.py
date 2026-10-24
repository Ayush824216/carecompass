"""Convert the public datasets in PUBLIC_DIR into internal rows in PROCESSED_DIR/public_train.jsonl.

Internal format: {text, language, care_type, urgency, source}; a label is null when unavailable.
  * KTAS (urgency only, from KTAS_expert): 1-2 immediate, 3 same_day, 4-5 routine.
    Only triage-time fields are used (chief complaint, age, mental state, pain); never outcome columns.
  * symptoms_to_diseases + symptom_severity/dataset.csv: diseases -> care_type/urgency via
    config/disease_to_care_type.json (INTERNAL ONLY), turned into English symptom sentences.
  * Symptom-severity.csv -> PROCESSED_DIR/severity_lexicon.json (used to expand the red-flag lexicon).

    python scripts/prepare_public_data.py [--per-disease 20] [--seed 13]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import get_settings  # noqa: E402

KTAS_MAP = {1: "immediate", 2: "immediate", 3: "same_day", 4: "routine", 5: "routine"}
MENTAL = {2: "responds to voice only", 3: "responds to pain only", 4: "unresponsive"}


def read_csv_any(path: Path, **kw) -> pd.DataFrame:
    for enc in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc, **kw)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"cannot decode {path}")


def disease_map(cfg_dir: Path) -> dict[str, tuple[str, str]]:
    m = json.loads((cfg_dir / "disease_to_care_type.json").read_text(encoding="utf-8"))["groups"]
    return {d.strip().lower(): (ct, urg) for ct, by_u in m.items() for urg, ds in by_u.items() for d in ds}


def age_words(age: int) -> str:
    if age >= 65:
        return f"elderly patient aged {age}"
    return f"adult aged {age}"


def ktas_rows(pub: Path) -> list[dict]:
    p = pub / "ktas" / "data.csv"
    if not p.exists():
        return []
    df = read_csv_any(p, sep=";")
    rows = []
    for _, r in df.iterrows():
        cc = str(r["Chief_complain"]).strip()
        if not cc or cc.lower() == "nan":
            continue
        parts = [cc, age_words(int(r["Age"]))]
        if int(r["Mental"]) in MENTAL:
            parts.append(MENTAL[int(r["Mental"])])
        if int(r["Injury"]) == 2:
            parts.append("after an injury")
        rows.append({"text": ", ".join(parts), "language": "en", "care_type": None,
                     "urgency": KTAS_MAP[int(r["KTAS_expert"])], "source": "ktas",
                     "ktas_expert": int(r["KTAS_expert"])})
    return rows


def symptom_sentence(symptoms: list[str], rng: random.Random) -> str:
    syms = [s.replace("_", " ").strip() for s in symptoms if s and s.strip()]
    rng.shuffle(syms)
    syms = syms[: rng.randint(2, 5)] if len(syms) > 2 else syms
    lead = rng.choice(["I have", "My father has", "My mother has", "Patient has", "Having", "Suffering from"])
    return f"{lead} {', '.join(syms[:-1])} and {syms[-1]}" if len(syms) > 1 else f"{lead} {syms[0]}"


def disease_rows(pub: Path, dmap: dict, per_disease: int, rng: random.Random) -> tuple[list[dict], Counter]:
    rows, unmapped = [], Counter()
    p = pub / "symptoms_to_diseases" / "final_symptoms_to_disease.csv"
    if p.exists():
        df = read_csv_any(p, usecols=["diseases", "symptom_text"])
        df["d"] = df["diseases"].astype(str).str.strip().str.lower()
        df = df.groupby("d", group_keys=False).apply(
            lambda g: g.sample(min(len(g), per_disease), random_state=rng.randint(0, 10**6)))
        for _, r in df.iterrows():
            if r["d"] not in dmap:
                unmapped[r["d"]] += 1
                continue
            ct, urg = dmap[r["d"]]
            rows.append({"text": symptom_sentence(str(r["symptom_text"]).split(","), rng), "language": "en",
                         "care_type": ct, "urgency": urg, "source": "symptoms_to_diseases"})
    p = pub / "symptom_severity" / "dataset.csv"
    if p.exists():
        df = read_csv_any(p)
        df["d"] = df["Disease"].astype(str).str.strip().str.lower()
        sym_cols = [c for c in df.columns if c.startswith("Symptom")]
        df = df.drop_duplicates(subset=sym_cols + ["d"])
        df = df.groupby("d", group_keys=False).apply(
            lambda g: g.sample(min(len(g), per_disease), random_state=rng.randint(0, 10**6)))
        for _, r in df.iterrows():
            if r["d"] not in dmap:
                unmapped[r["d"]] += 1
                continue
            syms = [str(r[c]) for c in sym_cols if str(r[c]) != "nan"]
            ct, urg = dmap[r["d"]]
            rows.append({"text": symptom_sentence(syms, rng), "language": "en",
                         "care_type": ct, "urgency": urg, "source": "symptom_severity"})
    return rows, unmapped


def severity_lexicon(pub: Path) -> dict[str, int]:
    p = pub / "symptom_severity" / "Symptom-severity.csv"
    if not p.exists():
        return {}
    df = read_csv_any(p)
    return {str(s).strip().replace("_", " "): int(w) for s, w in zip(df["Symptom"], df["weight"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-disease", type=int, default=20)
    ap.add_argument("--seed", type=int, default=13)
    a = ap.parse_args()
    s = get_settings()
    rng = random.Random(a.seed)
    s.processed_dir.mkdir(parents=True, exist_ok=True)

    k = ktas_rows(s.public_dir)
    d, unmapped = disease_rows(s.public_dir, disease_map(s.config_dir), a.per_disease, rng)
    rows = k + d
    with open(s.processed_dir / "public_train.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    lex = severity_lexicon(s.public_dir)
    (s.processed_dir / "severity_lexicon.json").write_text(json.dumps(lex, indent=1), encoding="utf-8")

    print(f"ktas={len(k)} disease_rows={len(d)} lexicon={len(lex)} -> {s.processed_dir}")
    print("ktas urgency", dict(Counter(r["urgency"] for r in k)))
    print("disease care_type", dict(Counter(r["care_type"] for r in d)))
    print("disease urgency", dict(Counter(r["urgency"] for r in d)))
    if unmapped:
        print("UNMAPPED diseases (skipped):", sorted(unmapped))


if __name__ == "__main__":
    main()
