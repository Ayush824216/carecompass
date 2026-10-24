"""CareCompass REST API."""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import time

from . import cache, data_adapter, intake, pathways, pipeline, privacy
from .config import get_settings
from .schemas import BookingRequest, BookingResponse, Caregiver, TriageRequest, TriageResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("carecompass")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    from .textclf import best_local_model
    m = best_local_model()  # warm up so the first request is fast
    data_adapter.load_caregivers()
    log.info("startup: local model=%s %s", getattr(m, "name", None), get_settings())
    yield


app = FastAPI(
    lifespan=lifespan,
    title="SwasthMitra API",
    version="0.1.0",
    description="Care routing support (care type, urgency, caregiver match). Does not diagnose or prescribe.",
)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "caregivers": len(data_adapter.load_caregivers())}


@app.post("/api/v1/triage", response_model=TriageResponse, response_model_exclude_none=False)
def triage(req: TriageRequest, debug: bool = Query(False, description="Add a `debug` decision trace to the response"),
           x_incognito: str = Header("", description="`1`: incognito. Nothing cached, counted or logged; local models only")):
    """Stateless: send the full conversation_history each turn. Returns a follow-up question OR a decision.

    The response is exactly the official schema unless `debug` is true (body field or `?debug=true`),
    in which case one extra key, `debug`, is added. Nothing is stored on the server (see docs/PRIVACY.md).
    """
    want_debug = bool(debug or req.debug)
    inc = x_incognito.strip().lower() in ("1", "true", "yes", "on")
    with privacy.request_mode(inc):
        t0 = time.perf_counter()
        rc, k = cache.response_cache(), cache.key(req, want_debug)
        hit = None if inc else rc.get(k)
        if hit is not None:  # same request -> identical answer (see app/cache.py)
            return JSONResponse(hit)
        trace: dict = {}
        body = jsonable_encoder(pipeline.run(req, use_llm=not privacy.local_only(), trace=trace))
        trace["processing"] = {"local": privacy.local_only() or not trace.get("llm", {}).get("used", False),
                               "incognito": inc, "llm_used": bool(trace.get("llm", {}).get("used"))}
        if want_debug:
            trace["cache"] = {"key": k[:12], "version": cache.version(), "skipped": inc}
            body["debug"] = jsonable_encoder(trace)
        privacy.record(body, trace, (time.perf_counter() - t0) * 1000)
        if not inc and not trace.get("error"):  # never pin a fallback produced by an internal error
            rc.put(k, body)
    return JSONResponse(body)


@app.get("/metrics")
def metrics() -> dict:
    """Anonymised counters only (decision labels, stages, latency buckets): no text, no per-user data."""
    return privacy.metrics()


@app.get("/api/v1/localities")
def localities() -> list[dict]:
    """Delhi NCR localities with coordinates (for location pickers)."""
    import json
    p = get_settings().config_dir / "localities.json"
    return json.loads(p.read_text(encoding="utf-8"))["localities"]


@app.get("/api/v1/caregivers", response_model=list[Caregiver])
def list_caregivers() -> list[Caregiver]:
    """All caregivers in the network (for directory views)."""
    return [Caregiver(**{k: cg.get(k) for k in Caregiver.model_fields if k in cg}) for cg in data_adapter.load_caregivers()]


@app.get("/api/v1/questions")
def questions() -> dict:
    """Follow-up question bank with quick-reply options (lets clients render one-tap chips)."""
    bank = {qid: {"en": q["en"], "hi": q["hi"], "hinglish": q["hinglish"], "multi": False,
                  "options": [{"value": v, "en": e, "hi": h, "hinglish": g} for v, e, h, g in q["options"]]}
            for qid, q in intake.QUESTIONS.items()}
    _, pws, _ = pathways.load()
    for p in pws.values():  # clinical pathway questions: multi-select chips with a "None of these" option
        for q in p.cfg["questions"]:
            opts = {lang: pathways.chip_options(q, lang) for lang in ("en", "hi", "hinglish")}
            bank[q["id"]] = {**q["text"], "multi": True, "pathway": p.id,
                             "options": [{"value": o["id"], "exclusive": o.get("exclusive", False),
                                          **{lang: opts[lang][i]["label"] for lang in opts}} for i, o in enumerate(opts["en"])]}
    return bank


@app.get("/api/v1/caregivers/{caregiver_id}", response_model=Caregiver)
def get_caregiver(caregiver_id: str) -> Caregiver:
    cg = data_adapter.caregiver_by_id(caregiver_id)
    if not cg:
        raise HTTPException(status_code=404, detail="caregiver not found")
    return Caregiver(**{k: cg.get(k) for k in Caregiver.model_fields if k in cg})


@app.post("/api/v1/book", response_model=BookingResponse)
def book(req: BookingRequest) -> BookingResponse:
    if req.care_type == "emergency_referral" or req.urgency == "immediate":
        return BookingResponse(booking_id="", status="rejected", caregiver_id=req.caregiver_id,
                               message="This is an emergency. Call 112 or ambulance 108 now.")
    cg = data_adapter.caregiver_by_id(req.caregiver_id)
    if not cg:
        raise HTTPException(status_code=404, detail="caregiver not found")
    slot = req.slot or next(iter(cg.get("availability_slots") or []), None)
    return BookingResponse(booking_id=f"BK-{uuid.uuid4().hex[:8].upper()}", status="confirmed",
                           caregiver_id=cg["caregiver_id"], caregiver_name=cg.get("name"), slot=slot,
                           message=f"Booked {cg.get('name')} ({cg.get('role')}) for {slot}.")
