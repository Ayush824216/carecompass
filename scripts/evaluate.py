"""Evaluate routing on held-out splits and write summary metrics (no raw data) to docs/EVAL.md.

Reports, separately for the dev/official vignettes and KTAS:
  macro-F1 (care_type, urgency), per-class reports, confusion matrices, emergency recall, under-triage rate,
  plus average follow-up count and p50/p95 latency of the full pipeline.

    python scripts/evaluate.py [--no-write] [--sweep]
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from sklearn.metrics import classification_report, confusion_matrix, f1_score  # noqa: E402

from app import data_adapter, safety  # noqa: E402
from app.schemas import CARE_TYPES, EMERGENCY_CARE_TYPE, MOST_URGENT, URGENCIES, URGENCY_RANK  # noqa: E402
from app.textclf import LocalModel, fit_models, stratified_split  # noqa: E402
from app.triage import decide_from_probs, triage_cfg  # noqa: E402
from train import training_rows  # noqa: E402


def is_emerg(care: str | None, urg: str | None) -> bool:
    return care == EMERGENCY_CARE_TYPE or urg == MOST_URGENT


def metrics(y_care, p_care, y_urg, p_urg) -> dict:
    m = {}
    if y_care:
        m["care_f1"] = f1_score(y_care, p_care, average="macro", labels=sorted(set(y_care)), zero_division=0)
    m["urg_f1"] = f1_score(y_urg, p_urg, average="macro", labels=sorted(set(y_urg)), zero_division=0)
    yc = y_care or [None] * len(y_urg)
    pc = p_care or [None] * len(p_urg)
    em_true = [i for i in range(len(y_urg)) if is_emerg(yc[i], y_urg[i])]
    m["emerg_recall"] = (sum(is_emerg(pc[i], p_urg[i]) for i in em_true) / len(em_true)) if em_true else float("nan")
    m["n_emerg"] = len(em_true)
    non = [i for i in range(len(y_urg)) if i not in set(em_true)]
    m["emerg_fpr"] = (sum(is_emerg(pc[i], p_urg[i]) for i in non) / len(non)) if non else float("nan")
    m["under_triage"] = sum(URGENCY_RANK[p] < URGENCY_RANK[t] for t, p in zip(y_urg, p_urg)) / len(y_urg)
    m["n"] = len(y_urg)
    return m


def predict_rows(model: LocalModel, rows: list[dict], cfg: dict, use_rules: bool, use_pipeline: bool = False):
    probs = model.predict_proba_batch([r["text"] for r in rows])
    out, lat = [], []
    for r, p in zip(rows, probs):
        t0 = time.perf_counter()
        if use_pipeline:
            from app import pipeline
            d = pipeline.final_decision(r["text"], model=model, cfg=cfg)
            care, urg = d["care_type"], d["urgency"]
        else:
            care, urg, _ = decide_from_probs(p, cfg)
            if use_rules and safety.check([r["text"]]).is_emergency:
                care, urg = EMERGENCY_CARE_TYPE, MOST_URGENT
        lat.append((time.perf_counter() - t0) * 1000)
        out.append((care, urg))
    return out, lat


def fmt(m: dict) -> str:
    keys = [("care_f1", "care_type macro-F1"), ("urg_f1", "urgency macro-F1"), ("emerg_recall", "emergency recall"),
            ("emerg_fpr", "emergency false-positive rate"), ("under_triage", "under-triage rate")]
    return " | ".join(f"{label}: {m[k]:.3f}" for k, label in keys if k in m)


def cm_md(y, p, labels) -> str:
    cm = confusion_matrix(y, p, labels=labels)
    short = [l.split("_")[0][:9] for l in labels]
    lines = ["| true \\ pred | " + " | ".join(short) + " |", "|---" * (len(labels) + 1) + "|"]
    for l, row in zip(short, cm):
        lines.append(f"| {l} | " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--sweep", action="store_true", help="sweep decision thresholds on the dev split")
    a = ap.parse_args()
    cfg = dict(triage_cfg())

    vig_all = data_adapter.load_vignettes()
    is_official = "official" in str(data_adapter.vignettes_path())
    _, dev_val = stratified_split(vig_all)
    pub = data_adapter.load_processed_public()
    ktas = [r for r in pub if r["source"] == "ktas"]
    _, ktas_val = stratified_split(ktas, key=lambda r: r["urgency"]) if ktas else ([], [])

    t0 = time.time()
    model = LocalModel(fit_models(training_rows(holdout=True)))
    train_s = time.time() - t0

    if a.sweep:
        print("emergency_threshold same_day_threshold -> care_f1 urg_f1 recall")
        best = None
        for et in (0.2, 0.25, 0.3, 0.35, 0.4, 0.5):
            for st in (0.3, 0.35, 0.4, 0.45, 0.5, 0.55):
                c = dict(cfg, emergency_threshold=et, same_day_threshold=st)
                pr, _ = predict_rows(model, dev_val, c, use_rules=True)
                m = metrics([r["care_type"] for r in dev_val], [x[0] for x in pr],
                            [r["urgency"] for r in dev_val], [x[1] for x in pr])
                score = m["care_f1"] + m["urg_f1"] + 2 * m["emerg_recall"]
                print(f"{et:.2f} {st:.2f} -> {m['care_f1']:.3f} {m['urg_f1']:.3f} {m['emerg_recall']:.3f}")
                if best is None or score > best[0]:
                    best = (score, et, st)
        print("best", best)

    report = []
    results = {}
    variants = [("Model A only", False, False), ("Rules + Model A", True, False)]
    try:
        from app import pipeline  # noqa: F401
        if hasattr(pipeline, "final_decision"):
            variants.append(("Full pipeline", True, True))
    except Exception:
        pass
    lat_all: list[float] = []
    for name, rules, pipe in variants:
        pr, lat = predict_rows(model, dev_val, cfg, use_rules=rules, use_pipeline=pipe)
        yc, yu = [r["care_type"] for r in dev_val], [r["urgency"] for r in dev_val]
        pc, pu = [x[0] for x in pr], [x[1] for x in pr]
        m = metrics(yc, pc, yu, pu)
        results[name] = (m, yc, pc, yu, pu)
        if pipe:
            lat_all = lat
        print(f"[{'official' if is_official else 'dev'} val n={m['n']}] {name}: {fmt(m)}")

    k_res = {}
    if ktas_val:
        for name, rules, pipe in variants[:2]:
            pr, _ = predict_rows(model, ktas_val, cfg, use_rules=rules)
            yu, pu = [r["urgency"] for r in ktas_val], [x[1] for x in pr]
            m = metrics([], [], yu, pu)
            k12 = [i for i, r in enumerate(ktas_val) if r["ktas_expert"] <= 2]
            m["ktas12_recall"] = sum(pu[i] == MOST_URGENT for i in k12) / len(k12)
            k_res[name] = (m, yu, pu)
            print(f"[KTAS val n={m['n']}] {name}: {fmt(m)} | KTAS 1-2 recall: {m['ktas12_recall']:.3f}")

    # follow-ups: how many questions the intake policy asks on the first turn (0 = decided immediately)
    fu_avg = None
    try:
        from app import intake
        fu = [intake.count_initial_followups(r["text"]) for r in dev_val]
        fu_avg = sum(fu) / len(fu)
        print(f"avg follow-ups needed (dev val, simulated): {fu_avg:.2f}")
    except Exception as e:  # intake not built yet
        print("follow-up simulation skipped:", e.__class__.__name__)

    # API latency through the real endpoint
    api_lat = []
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        for r in dev_val[:60]:
            t0 = time.perf_counter()
            client.post("/api/v1/triage", json={"user_input": r["text"], "language": "auto",
                                                "location": {"lat": 28.6, "lng": 77.2}, "conversation_history": []})
            api_lat.append((time.perf_counter() - t0) * 1000)
    except Exception as e:
        print("API latency skipped:", e)
    if api_lat:
        q = statistics.quantiles(api_lat, n=20)
        print(f"API /triage latency ms: p50={statistics.median(api_lat):.1f} p95={q[18]:.1f}")

    if a.no_write:
        return
    src = "official data" if is_official else "dev data (synthetic, self-generated)"
    report.append(f"# Evaluation\n\nGenerated by `scripts/evaluate.py` on {datetime.now():%Y-%m-%d %H:%M}. "
                  f"Vignettes: **{src}**. Summary metrics only.\n")
    report.append(f"Model A trained on the train split + processed public data in {train_s:.1f}s. "
                  f"Decision config: emergency_threshold={cfg['emergency_threshold']}, "
                  f"same_day_threshold={cfg['same_day_threshold']}.\n")
    report.append(f"## Vignettes, validation split (n={len(dev_val)})\n")
    report.append("| Variant | care_type macro-F1 | urgency macro-F1 | emergency recall | emergency FPR | under-triage |")
    report.append("|---|---|---|---|---|---|")
    for name, (m, *_rest) in results.items():
        report.append(f"| {name} | {m['care_f1']:.3f} | {m['urg_f1']:.3f} | {m['emerg_recall']:.3f} | "
                      f"{m['emerg_fpr']:.3f} | {m['under_triage']:.3f} |")
    best_name = list(results)[-1]
    m, yc, pc, yu, pu = results[best_name]
    report.append(f"\n### Per-class ({best_name})\n\n```\n"
                  + classification_report(yc, pc, labels=list(CARE_TYPES), zero_division=0)
                  + "\n" + classification_report(yu, pu, labels=list(URGENCIES), zero_division=0) + "```\n")
    report.append("Care type confusion:\n\n" + cm_md(yc, pc, list(CARE_TYPES)) + "\n")
    report.append("\nUrgency confusion:\n\n" + cm_md(yu, pu, list(URGENCIES)) + "\n")
    if k_res:
        report.append(f"\n## KTAS validation split (urgency only, n={len(ktas_val)})\n")
        report.append("| Variant | urgency macro-F1 | KTAS 1-2 → immediate recall | under-triage |")
        report.append("|---|---|---|---|")
        for name, (m, *_r) in k_res.items():
            report.append(f"| {name} | {m['urg_f1']:.3f} | {m['ktas12_recall']:.3f} | {m['under_triage']:.3f} |")
        report.append("\nKTAS is Korean ED data triaged largely on vital signs, which a text-only router cannot see. "
                      "It is used as extra urgency signal, not as the target distribution.\n")
    report.append("\n## Interaction and latency\n")
    if fu_avg is not None:
        report.append(f"- Average follow-up questions on the first turn (dev val, simulated): **{fu_avg:.2f}** (max 4)")
    if api_lat:
        q = statistics.quantiles(api_lat, n=20)
        report.append(f"- `/api/v1/triage` latency (in-process, {len(api_lat)} calls, no LLM): "
                      f"p50 **{statistics.median(api_lat):.1f} ms**, p95 **{q[18]:.1f} ms**")
    report.append("\n> Dev data is template-generated, so these validation scores are optimistic. "
                  "Treat them as a regression check, not as the expected hidden-test score.\n")
    (ROOT / "docs" / "EVAL.md").write_text("\n".join(report), encoding="utf-8")
    print("wrote docs/EVAL.md")


if __name__ == "__main__":
    main()
