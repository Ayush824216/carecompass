"""Pydantic request/response models. Indicative contract; align with the official schema when released."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

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


ROLE_ALIASES = {"user": "user", "human": "user", "patient": "user", "client": "user",
                "assistant": "assistant", "bot": "assistant", "ai": "assistant", "model": "assistant", "system": "system"}
LANG_ALIASES = {"auto": "auto", "en": "en", "english": "en", "hi": "hi", "hindi": "hi", "hinglish": "hinglish",
                "hi-latn": "hinglish", "hien": "hinglish", "en-in": "en", "hi-in": "hi"}
MAX_INPUT = 4000


class Turn(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, v: Any) -> Any:
        """Accept {role, content} plus common variants ({speaker, text}, {sender, message}) and plain strings."""
        if isinstance(v, str):
            return {"role": "user", "content": v}
        if isinstance(v, dict):
            role = str(v.get("role") or v.get("speaker") or v.get("sender") or v.get("from") or "user").lower()
            content = v.get("content", v.get("text", v.get("message", v.get("utterance", ""))))
            return {"role": ROLE_ALIASES.get(role, "user"), "content": "" if content is None else str(content)[:MAX_INPUT]}
        return v


class TriageRequest(BaseModel):
    user_input: str = ""
    language: LanguageIn = "auto"
    location: Optional[Location] = None
    conversation_history: list[Turn] = Field(default_factory=list)
    debug: bool = Field(False, description="Optional. If true, the response gains an extra `debug` object (decision trace). "
                                           "Without it the response is exactly the official schema.")

    @field_validator("debug", mode="before")
    @classmethod
    def _debug(cls, v: Any) -> bool:
        return str(v).strip().lower() in ("1", "true", "yes", "on")

    @field_validator("user_input", mode="before")
    @classmethod
    def _input(cls, v: Any) -> str:
        return "" if v is None else str(v)[:MAX_INPUT]

    @field_validator("language", mode="before")
    @classmethod
    def _lang(cls, v: Any) -> str:
        return LANG_ALIASES.get(str(v or "auto").strip().lower(), "auto")

    @field_validator("conversation_history", mode="before")
    @classmethod
    def _hist(cls, v: Any) -> Any:
        return [] if v is None else v

    @field_validator("location", mode="before")
    @classmethod
    def _loc(cls, v: Any) -> Any:
        if isinstance(v, dict) and "lat" not in v and ("latitude" in v or "lon" in v or "longitude" in v):
            return {"lat": v.get("latitude", v.get("lat")), "lng": v.get("longitude", v.get("lon", v.get("lng")))}
        return v

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
    specialty: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    qualification: Optional[str] = None
    years_experience: Optional[int] = None
    locality: Optional[str] = None
    consultation_modes: list[str] = Field(default_factory=list)
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
