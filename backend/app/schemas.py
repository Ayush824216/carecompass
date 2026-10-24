"""Pydantic request/response models. Indicative contract; align with the official schema when released."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

CareType = Literal["paramedic_home_visit", "nurse_home_visit", "gp_teleconsult",
                   "specialist_referral", "emergency_referral"]
Urgency = Literal["routine", "same_day", "immediate"]
LanguageIn = Literal["auto", "en", "hi", "hinglish"]

CARE_TYPES: tuple[str, ...] = CareType.__args__  # type: ignore[attr-defined]
URGENCIES: tuple[str, ...] = Urgency.__args__  # type: ignore[attr-defined]
EMERGENCY_CARE_TYPE = "emergency_referral"
MOST_URGENT = "immediate"
URGENCY_RANK = {"routine": 0, "same_day": 1, "immediate": 2}


class Location(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class Turn(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str = ""


class TriageRequest(BaseModel):
    user_input: str = Field(..., max_length=4000)
    language: LanguageIn = "auto"
    location: Optional[Location] = None
    conversation_history: list[Turn] = Field(default_factory=list)

    model_config = {"json_schema_extra": {"examples": [{
        "user_input": "papa ko do din se bukhar hai aur khansi bhi",
        "language": "auto",
        "location": {"lat": 28.54, "lng": 77.27},
        "conversation_history": [],
    }]}}


class MatchedCaregiver(BaseModel):
    caregiver_id: str
    score: float = Field(..., ge=0, le=1)
    reason: str


class TriageResponse(BaseModel):
    follow_up_question: Optional[str] = None
    care_type: Optional[CareType] = None
    urgency: Optional[Urgency] = None
    red_flags: list[str] = Field(default_factory=list)
    reasoning: str = ""
    matched_caregivers: list[MatchedCaregiver] = Field(default_factory=list)


class Caregiver(BaseModel):
    caregiver_id: str
    name: str
    role: str
    skills: list[str] = Field(default_factory=list)
    lat: float
    lng: float
    availability_slots: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    rating: float = 0.0


class BookingRequest(BaseModel):
    caregiver_id: str
    slot: Optional[str] = None
    care_type: Optional[CareType] = None
    urgency: Optional[Urgency] = None
    patient_name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[Location] = None


class BookingResponse(BaseModel):
    booking_id: str
    status: Literal["confirmed", "rejected"]
    caregiver_id: str
    caregiver_name: Optional[str] = None
    slot: Optional[str] = None
    message: str
