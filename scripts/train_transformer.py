"""Fine-tune Model C: multilingual encoder (default google/muril-base-cased, fallback xlm-roberta-base) with two heads.

4 GB VRAM budget: fp16 autocast, max_len 128, batch 16 (+grad accumulation on OOM), word embeddings frozen
(MuRIL's 197k-token embedding matrix is ~151M params; freezing it keeps optimizer state small). Weights are saved
in fp16 to keep the model under ~500 MB.

    python scripts/train_transformer.py                 # holdout run: train split only, report val metrics
    python scripts/train_transformer.py --full          # retrain on all data with the same settings (serving)
    python scripts/train_transformer.py --base xlm-roberta-base

Writes models/model_c/{encoder/, tokenizer files, heads.pt, meta.json}. meta.json records holdout metrics for
Model A, Model C and the A+C ensemble, and which one to use in production.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from sklearn.metrics import f1_score  # noqa: E402
from torch import nn  # noqa: E402
from transformers import AutoTokenizer, get_linear_schedule_with_warmup  # noqa: E402

from app import data_adapter, safety  # noqa: E402
from app.schemas import CARE_TYPES, EMERGENCY_CARE_TYPE, MOST_URGENT, URGENCIES  # noqa: E402
from app.textclf import SOURCE_WEIGHT, LocalModel, fit_models, model_input, stratified_split  # noqa: E402
from app.transformer_clf import TwoHeadClassifier  # noqa: E402
from app.triage import decide_from_probs, triage_cfg  # noqa: E402
from train import training_rows  # noqa: E402


def class_weights(labels: list[str], classes: list[str]) -> torch.Tensor:
    counts = np.array([max(1, sum(l == c for l in labels)) for c in classes], dtype=np.float32)
    w = counts.sum() / (len(classes) * counts)
    return torch.tensor(w / w.mean(), dtype=torch.float32)


def encode(tok, rows, max_len):
    return tok([model_input(r["text"]) for r in rows], truncation=True, max_length=max_len, padding="max_length",
               return_tensors="pt")


def evaluate_probs(probs_list, rows, cfg) -> dict:
    pc, pu = [], []
    for p, r in zip(probs_list, rows):
        c, u, _ = decide_from_probs(p, cfg)
        if safety.check([r["text"]]).is_emergency:
            c, u = EMERGENCY_CARE_TYPE, MOST_URGENT
        pc.append(c)
        pu.append(u)
    yc, yu = [r["care_type"] for r in rows], [r["urgency"] for r in rows]
    em = [i for i, r in enumerate(rows) if r["care_type"] == EMERGENCY_CARE_TYPE or r["urgency"] == MOST_URGENT]
    rec = sum(pc[i] == EMERGENCY_CARE_TYPE or pu[i] == MOST_URGENT for i in em) / max(1, len(em))
    return {"care_f1": round(f1_score(yc, pc, average="macro", zero_division=0), 4),
            "urg_f1": round(f1_score(yu, pu, average="macro", zero_division=0), 4), "emerg_recall": round(rec, 4)}


def avg_probs(a, b, wa=0.5):
    return [{t: {k: wa * pa[t].get(k, 0) + (1 - wa) * pb[t].get(k, 0) for k in set(pa[t]) | set(pb[t])} for t in pa}
            for pa, pb in zip(a, b)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="google/muril-base-cased")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--accum", type=int, default=1)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--max-len", type=int, default=128)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print("device:", dev, torch.cuda.get_device_name(0) if dev == "cuda" else "")

    rows = training_rows(holdout=not a.full)
    vig = data_adapter.load_vignettes()
    _, dev_val = stratified_split(vig)
    ktas = [r for r in data_adapter.load_processed_public() if r["source"] == "ktas"]
    _, ktas_val = stratified_split(ktas, key=lambda r: r["urgency"]) if ktas else ([], [])
    care_classes, urg_classes = list(CARE_TYPES), list(URGENCIES)

    tok = AutoTokenizer.from_pretrained(a.base)
    model = TwoHeadClassifier(a.base, len(care_classes), len(urg_classes)).to(dev)
    for p in model.encoder.embeddings.word_embeddings.parameters():
        p.requires_grad = False

    enc = encode(tok, rows, a.max_len)
    yc = torch.tensor([care_classes.index(r["care_type"]) if r.get("care_type") else -100 for r in rows])
    yu = torch.tensor([urg_classes.index(r["urgency"]) if r.get("urgency") else -100 for r in rows])
    sw = torch.tensor([SOURCE_WEIGHT.get(r.get("source", "dev"), 1.0) for r in rows], dtype=torch.float32)
    wc = class_weights([r["care_type"] for r in rows if r.get("care_type")], care_classes).to(dev)
    wu = class_weights([r["urgency"] for r in rows if r.get("urgency")], urg_classes).to(dev)
    ce_c = nn.CrossEntropyLoss(weight=wc, ignore_index=-100, reduction="none")
    ce_u = nn.CrossEntropyLoss(weight=wu, ignore_index=-100, reduction="none")

    params = [
        {"params": [p for p in model.encoder.parameters() if p.requires_grad], "lr": a.lr},
        {"params": list(model.care_head.parameters()) + list(model.urg_head.parameters()), "lr": 1e-3},
    ]
    opt = torch.optim.AdamW(params, weight_decay=0.01)
    n = len(rows)
    steps = (n // (a.bs * a.accum) + 1) * a.epochs
    sched = get_linear_schedule_with_warmup(opt, int(0.06 * steps), steps)
    scaler = torch.cuda.amp.GradScaler(enabled=dev == "cuda")
    t0 = time.time()
    model.train()
    for ep in range(a.epochs):
        perm = torch.randperm(n)
        tot = 0.0
        for bi, i in enumerate(range(0, n, a.bs)):
            idx = perm[i:i + a.bs]
            ids, am = enc["input_ids"][idx].to(dev), enc["attention_mask"][idx].to(dev)
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=dev == "cuda"):
                lc, lu = model(ids, am)
            w = sw[idx].to(dev)
            tc, tu = yc[idx].to(dev), yu[idx].to(dev)
            l1 = (ce_c(lc.float(), tc) * w * (tc != -100)).sum() / max(1, int((tc != -100).sum()))
            l2 = (ce_u(lu.float(), tu) * w * (tu != -100)).sum() / max(1, int((tu != -100).sum()))
            loss = (l1 + l2) / a.accum
            scaler.scale(loss).backward()
            if (bi + 1) % a.accum == 0:
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(opt); scaler.update(); opt.zero_grad(); sched.step()
            tot += loss.item() * a.accum
        print(f"epoch {ep + 1}/{a.epochs} loss={tot / (bi + 1):.4f} elapsed={time.time() - t0:.0f}s"
              + (f" peak_vram={torch.cuda.max_memory_allocated() / 2**30:.2f}GB" if dev == "cuda" else ""))

    out = ROOT / "models" / "model_c"
    out.mkdir(parents=True, exist_ok=True)
    model.eval()
    model.encoder.half().save_pretrained(out / "encoder", safe_serialization=True)
    tok.save_pretrained(out)
    torch.save({"care_head": model.care_head.state_dict(), "urg_head": model.urg_head.state_dict()}, out / "heads.pt")
    meta = {"base_model": a.base, "care_classes": care_classes, "urgency_classes": urg_classes, "max_len": a.max_len,
            "epochs": a.epochs, "trained_on": "all" if a.full else "train_split", "train_rows": n,
            "train_seconds": round(time.time() - t0, 1)}

    meta_path = out / "meta.json"
    old = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    if not a.full:
        from app.transformer_clf import TransformerModel
        (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        mc = TransformerModel(out)
        cfg = triage_cfg()
        ma = LocalModel(fit_models(rows))
        res = {}
        for name, rows_v in (("dev_val", dev_val), ("ktas_val", ktas_val)):
            if not rows_v:
                continue
            pa = ma.predict_proba_batch([r["text"] for r in rows_v])
            t1 = time.perf_counter()
            pcm = mc.predict_proba_batch([r["text"] for r in rows_v])
            ms = (time.perf_counter() - t1) * 1000 / len(rows_v)
            pe = avg_probs(pa, pcm)
            if name == "dev_val":
                res[name] = {"model_a": evaluate_probs(pa, rows_v, cfg), "model_c": evaluate_probs(pcm, rows_v, cfg),
                             "ensemble": evaluate_probs(pe, rows_v, cfg), "model_c_ms_per_text": round(ms, 1)}
            else:
                def urg(pl):
                    pu = [decide_from_probs(p, cfg)[1] for p in pl]
                    k12 = [i for i, r in enumerate(rows_v) if r["ktas_expert"] <= 2]
                    return {"urg_f1": round(f1_score([r["urgency"] for r in rows_v], pu, average="macro"), 4),
                            "ktas12_recall": round(sum(pu[i] == MOST_URGENT for i in k12) / len(k12), 4)}
                res[name] = {"model_a": urg(pa), "model_c": urg(pcm), "ensemble": urg(pe)}
        meta["holdout_metrics"] = res
        d = res["dev_val"]
        score = {k: d[k]["care_f1"] + d[k]["urg_f1"] for k in ("model_a", "model_c", "ensemble")}
        ok = {k: d[k]["emerg_recall"] >= d["model_a"]["emerg_recall"] for k in score}
        best = max((k for k in score if ok[k]), key=lambda k: score[k])
        meta["production"] = best
        print(json.dumps(res, indent=1))
        print("production choice:", best)
    else:
        meta["holdout_metrics"] = old.get("holdout_metrics")
        meta["production"] = old.get("production", "model_c")
    meta["use_in_production"] = meta.get("production") in ("model_c", "ensemble")
    meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) / 2**20
    print(f"saved {out} ({size:.0f} MB)")


if __name__ == "__main__":
    main()
