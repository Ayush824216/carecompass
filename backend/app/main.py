"""CareCompass REST API."""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import data_adapter
from .config import get_settings
from .schemas import BookingRequest, BookingResponse, Caregiver, TriageRequest, TriageResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("carecompass")

app = FastAPI(
    title="CareCompass API",
    version="0.1.0",
    description="Care routing support (care type, urgency, caregiver match). Does not diagnose or prescribe.",
)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "caregivers": len(data_adapter.load_caregivers())}


@app.post("/api/v1/triage", response_model=TriageResponse, response_model_exclude_none=False)
def triage(req: TriageRequest) -> TriageResponse:
    t0 = time.perf_counter()
    resp = TriageResponse(follow_up_question=None, care_type="gp_teleconsult", urgency="routine",
                          red_flags=[], reasoning="Stub response.", matched_caregivers=[])
    log.info("triage total_ms=%.1f", (time.perf_counter() - t0) * 1000)
    return resp


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
