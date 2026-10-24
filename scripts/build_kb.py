"""Build kb/chunks.jsonl from our curated docs and configs (see backend/app/kb.py).

    python scripts/build_kb.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import kb  # noqa: E402

if __name__ == "__main__":
    cs = kb.build_chunks()
    kb.KB_FILE.parent.mkdir(exist_ok=True)
    kb.KB_FILE.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cs), encoding="utf-8")
    print(f"wrote {len(cs)} chunks -> {kb.KB_FILE}", file=sys.stderr)
