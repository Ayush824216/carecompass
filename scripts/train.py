"""Train Model A (TF-IDF + LogisticRegression) on dev/official vignettes + processed public data.

    python scripts/train.py            # train on ALL labelled data, save models/model_a.joblib (serving)
    python scripts/train.py --holdout  # train on the train split only (what evaluate.py measures)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app import data_adapter  # noqa: E402
from app.textclf import fit_models, save_model_a, stratified_split  # noqa: E402


def training_rows(holdout: bool) -> list[dict]:
    vig = data_adapter.load_vignettes()
    src = "official" if "official" in str(data_adapter.vignettes_path()) else "dev"
    for r in vig:
        r["source"] = src
    if holdout:
        vig, _ = stratified_split(vig)
    pub = data_adapter.load_processed_public()
    if holdout:  # keep the KTAS validation split out of training too
        k = [r for r in pub if r["source"] == "ktas"]
        k_tr, _ = stratified_split(k, key=lambda r: r["urgency"])
        pub = [r for r in pub if r["source"] != "ktas"] + k_tr
    return vig + pub


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--C", type=float, default=4.0)
    a = ap.parse_args()
    rows = training_rows(a.holdout)
    t0 = time.time()
    models = fit_models(rows, C=a.C)
    p = save_model_a(models)
    print(f"trained on {len(rows)} rows in {time.time() - t0:.1f}s -> {p}")


if __name__ == "__main__":
    main()
