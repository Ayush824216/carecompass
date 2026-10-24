"""Model C: multilingual transformer encoder (MuRIL / XLM-R) with two classification heads.

Imported lazily; requires torch + transformers (requirements-gpu.txt). Runs on GPU if available, else CPU.
"""
from __future__ import annotations

import json
from pathlib import Path

import torch
from torch import nn
from transformers import AutoModel, AutoTokenizer

from .textclf import model_input


class TwoHeadClassifier(nn.Module):
    def __init__(self, encoder_name_or_path: str, n_care: int, n_urg: int, dropout: float = 0.1):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(encoder_name_or_path)
        h = self.encoder.config.hidden_size
        self.drop = nn.Dropout(dropout)
        self.care_head = nn.Linear(h, n_care)
        self.urg_head = nn.Linear(h, n_urg)

    def forward(self, input_ids, attention_mask):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        mask = attention_mask.unsqueeze(-1).to(out.dtype)
        pooled = (out * mask).sum(1) / mask.sum(1).clamp(min=1e-6)  # mean pooling
        pooled = self.drop(pooled)
        return self.care_head(pooled), self.urg_head(pooled)


class TransformerModel:
    name = "transformer"

    def __init__(self, d: Path, device: str | None = None):
        meta = json.loads((Path(d) / "meta.json").read_text(encoding="utf-8"))
        self.care_classes = meta["care_classes"]
        self.urg_classes = meta["urgency_classes"]
        self.max_len = meta.get("max_len", 128)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tok = AutoTokenizer.from_pretrained(str(d))
        self.model = TwoHeadClassifier(str(d / "encoder"), len(self.care_classes), len(self.urg_classes))
        heads = torch.load(d / "heads.pt", map_location="cpu")
        self.model.care_head.load_state_dict(heads["care_head"])
        self.model.urg_head.load_state_dict(heads["urg_head"])
        self.model.float().to(self.device).eval()
        if self.device == "cuda":
            self.model.half()
        self.name = meta.get("base_model", "transformer").split("/")[-1]

    @torch.no_grad()
    def predict_proba_batch(self, texts: list[str], bs: int = 32) -> list[dict[str, dict[str, float]]]:
        out = []
        for i in range(0, len(texts), bs):
            enc = self.tok([model_input(t) for t in texts[i:i + bs]], truncation=True, max_length=self.max_len,
                           padding=True, return_tensors="pt").to(self.device)
            lc, lu = self.model(enc["input_ids"], enc["attention_mask"])
            pc, pu = lc.float().softmax(-1).cpu().tolist(), lu.float().softmax(-1).cpu().tolist()
            for a, b in zip(pc, pu):
                out.append({"care_type": dict(zip(self.care_classes, a)), "urgency": dict(zip(self.urg_classes, b))})
        return out

    def predict_proba(self, text: str) -> dict[str, dict[str, float]]:
        return self.predict_proba_batch([text])[0]
