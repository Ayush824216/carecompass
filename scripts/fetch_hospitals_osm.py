"""One-time download of hospitals in Delhi NCR from OpenStreetMap (Overpass API) into data/public/hospitals_ncr.json.

    python scripts/fetch_hospitals_osm.py [--out data/public/hospitals_ncr.json]

Nothing is written by hand: every record is an OSM element with amenity=hospital (name, coordinates, address tags
when present, OSM id). Data (c) OpenStreetMap contributors, available under the Open Database Licence (ODbL),
https://www.openstreetmap.org/copyright. The file lives under data/ and is not committed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
# Delhi NCR (Delhi, Gurugram, Faridabad, Noida, Greater Noida, Ghaziabad): south, west, north, east
BBOX = (28.20, 76.80, 28.95, 77.65)
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
QUERY = """[out:json][timeout:90];
(
  node["amenity"="hospital"]({s},{w},{n},{e});
  way["amenity"="hospital"]({s},{w},{n},{e});
  relation["amenity"="hospital"]({s},{w},{n},{e});
);
out center tags;"""
ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"


def address(tags: dict) -> str | None:
    if tags.get("addr:full"):
        return tags["addr:full"]
    parts = [tags.get(k) for k in ("addr:housenumber", "addr:street", "addr:suburb", "addr:city", "addr:postcode")]
    parts = [p for p in parts if p]
    return ", ".join(parts) or None


def fetch() -> list[dict]:
    q = QUERY.format(s=BBOX[0], w=BBOX[1], n=BBOX[2], e=BBOX[3])
    last = None
    for url in ENDPOINTS:
        try:
            r = httpx.post(url, data={"data": q}, timeout=httpx.Timeout(150, connect=15), headers={"User-Agent": "CareCompass-hackathon/1.0 (one-time fetch)"})
            r.raise_for_status()
            return r.json()["elements"]
        except Exception as e:  # try the next mirror
            last = e
    raise SystemExit(f"Overpass request failed ({last}). If the network is blocked, download the file manually.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "public" / "hospitals_ncr.json"))
    a = ap.parse_args()
    out = []
    for el in fetch():
        tags = el.get("tags", {})
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lng = el.get("lon", el.get("center", {}).get("lon"))
        name = tags.get("name") or tags.get("name:en")
        if lat is None or lng is None or not name:
            continue  # unnamed or unplaced elements are skipped, never filled in
        out.append({"name": name, "name_hi": tags.get("name:hi"), "lat": lat, "lng": lng, "address": address(tags),
                    "phone": tags.get("phone") or tags.get("contact:phone"), "emergency": tags.get("emergency"),
                    "osm_id": f"{el['type']}/{el['id']}", "source": ATTRIBUTION})
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    doc = {"source": "OpenStreetMap via Overpass API", "attribution": ATTRIBUTION, "licence": "ODbL 1.0",
           "licence_url": "https://www.openstreetmap.org/copyright", "bbox_s_w_n_e": BBOX,
           "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "count": len(out), "hospitals": out}
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(out)} hospitals -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
