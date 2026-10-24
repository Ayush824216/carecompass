"""Nearby hospitals (OpenStreetMap, never hand-written) and cited national helplines.

Hospitals come only from data/public/hospitals_ncr.json, created by scripts/fetch_hospitals_osm.py from OSM
(amenity=hospital). Distances are straight-line (haversine); the UI says so and asks people to call before going.
If the file is missing, the list is simply empty: nothing is invented.
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from typing import Optional

from .config import get_settings

ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
NOTE = {"en": "Distance is straight-line; call before going.", "hi": "दूरी सीधी रेखा में है; जाने से पहले फ़ोन करें।",
        "hinglish": "Doori seedhi line mein hai; jaane se pehle phone karein."}


@lru_cache
def _load() -> dict:
    p = get_settings().public_dir / "hospitals_ncr.json"
    if not p.exists():
        return {"hospitals": [], "attribution": ATTRIBUTION, "available": False}
    d = json.loads(p.read_text(encoding="utf-8"))
    d["available"] = True
    return d


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest(lat: float, lng: float, limit: int = 5, lang: str = "en", max_km: float = 50.0) -> dict:
    d = _load()
    rows = []
    for h in d["hospitals"]:
        km = haversine_km(lat, lng, h["lat"], h["lng"])
        if km <= max_km:
            rows.append((km, h))
    rows.sort(key=lambda x: x[0])
    out = []
    for km, h in rows[:max(1, min(limit, 10))]:
        ll = f"{h['lat']},{h['lng']}"
        out.append({
            "name": h["name"],
            "name_hi": h.get("name_hi") if h.get("name_hi") and DEVANAGARI.search(h["name_hi"]) else None,
            "lat": h["lat"], "lng": h["lng"], "address": h.get("address"), "phone": h.get("phone"),
            "distance_km": round(km, 2), "osm_id": h["osm_id"],
            "directions_url": f"https://www.google.com/maps/dir/?api=1&destination={ll}",
            "osm_url": f"https://www.openstreetmap.org/{h['osm_id']}",
        })
    return {"available": d.get("available", False), "attribution": d.get("attribution", ATTRIBUTION),
            "fetched_at": d.get("fetched_at"), "note": NOTE.get(lang, NOTE["en"]), "hospitals": out}


@lru_cache
def helplines() -> dict:
    return json.loads((get_settings().config_dir / "helplines.json").read_text(encoding="utf-8"))


def helplines_for(lang: str = "en", kinds: Optional[list[str]] = None) -> list[dict]:
    out = []
    for h in helplines()["helplines"]:
        if kinds and h["kind"] not in kinds:
            continue
        out.append({"number": h["number"], "kind": h["kind"], "label": h["label"].get(lang) or h["label"]["en"],
                    "desc": h["desc"].get(lang) or h["desc"]["en"], "sources": h["sources"]})
    return out
