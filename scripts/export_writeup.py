"""Export docs/WRITEUP.md to docs/WRITEUP.pdf (A4) and report the page count; the write-up must fit 2 pages.

Dev-only tools: pip install markdown playwright && python -m playwright install chromium
Run:  python scripts/export_writeup.py [--max-pages 2]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "WRITEUP.md"
OUT = ROOT / "docs" / "WRITEUP.pdf"
CSS = """
@page { size: A4; margin: 11mm 12mm; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 8.6pt; line-height: 1.28; color: #111; }
h1 { font-size: 13pt; margin: 0 0 3pt; } h2 { font-size: 10pt; margin: 6pt 0 2pt; } h3 { font-size: 9pt; margin: 5pt 0 2pt; }
p, ul, ol { margin: 0 0 3pt; } ul, ol { padding-left: 13pt; } li { margin: 0 0 1pt; }
table { border-collapse: collapse; width: 100%; margin: 2pt 0 4pt; font-size: 8pt; }
th, td { border: 1px solid #bbb; padding: 1.5pt 3pt; text-align: left; vertical-align: top; }
code { font-family: Consolas, monospace; font-size: 7.8pt; }
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=2)
    a = ap.parse_args()
    import markdown
    from playwright.sync_api import sync_playwright
    html = markdown.markdown(SRC.read_text(encoding="utf-8"), extensions=["tables"])
    doc = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html}</body></html>"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content(doc, wait_until="load")
        pg.pdf(path=str(OUT), format="A4", print_background=True, prefer_css_page_size=True)
        b.close()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", OUT.read_bytes()))
    print(f"wrote {OUT.relative_to(ROOT)}: {pages} page(s)")
    return 0 if pages <= a.max_pages else 1


if __name__ == "__main__":
    sys.exit(main())
