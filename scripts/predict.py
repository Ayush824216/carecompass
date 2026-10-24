"""Run the pipeline over a test file and write a predictions CSV to outputs/.

Offline there is no one to answer follow-ups, so every row gets a final single-shot decision
(rules -> local model [+ LLM if --use-llm] -> asymmetric-safety combine).

    python scripts/predict.py data/official/test.csv [--out outputs/predictions.csv] [--use-llm]
        [--columns id,care_type,urgency]

NOTE: the official predictions format has not been published yet. Default columns are
id,care_type,urgency; adjust --columns (available: id, care_type, urgency, red_flags, reasoning, source)
to match the official spec once released.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import data_adapter, pipeline  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="test file (.csv / .json / .jsonl) with an id and a text column")
    ap.add_argument("--out", default=str(ROOT / "outputs" / "predictions.csv"))
    ap.add_argument("--use-llm", action="store_true")
    ap.add_argument("--columns", default="id,care_type,urgency")
    a = ap.parse_args()
    logging.getLogger("carecompass").setLevel(logging.WARNING)

    rows = data_adapter.read_vignette_file(Path(a.input))
    if not rows:
        sys.exit(f"no rows with a text column found in {a.input}")
    cols = [c.strip() for c in a.columns.split(",") if c.strip()]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            lang = r.get("language") if r.get("language") in ("en", "hi", "hinglish") else None
            try:
                d = pipeline.final_decision(r["text"], use_llm=a.use_llm, lang=lang)
            except Exception as e:  # never drop a row: fall back to the safest non-crash default
                logging.exception("row %s failed: %s", r["id"], e)
                d = {"care_type": "gp_teleconsult", "urgency": "same_day", "red_flags": [], "reasoning": "", "source": "error"}
            rec = {"id": r["id"], **d, "red_flags": json.dumps(d.get("red_flags", []))}
            w.writerow([rec.get(c, "") for c in cols])
    print(f"wrote {len(rows)} predictions to {out} in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
