"""Pydantic request/response models for the HTTP API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Pace = Literal["relaxed", "balanced", "packed"]
TravelStyle = Literal["budget", "comfort", "luxury"]
Cabin = Literal["economy", "premium_economy", "business"]

INTERESTS = [
    "culture", "history", "food", "nightlife", "nature", "beaches", "adventure",
    "shopping", "art", "museums", "architecture", "photography", "wellness", "family", "sports",
]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str


class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


# --------------------------------------------------------------------- trips
class TripCreate(BaseModel):
    origin: str = Field(min_length=3, max_length=3, description="IATA code of the departure city")
    destinations: list[str] = Field(min_length=1, max_length=4, description="1-4 IATA codes, visited in order")
    start_date: date
    end_date: date
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=8)
    budget: float = Field(gt=0, le=1_000_000, description="Total budget for the whole party")
    cabin_class: Cabin = "economy"
    hotel_min_stars: int = Field(default=3, ge=2, le=5)
    pace: Pace = "balanced"
    travel_style: TravelStyle = "comfort"
    interests: list[str] = Field(default_factory=list, max_length=10)
    dietary_needs: str | None = Field(default=None, max_length=300)
    accessibility_needs: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)
    title: str | None = Field(default=None, max_length=200)

    @field_validator("origin")
    @classmethod
    def _upper_origin(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("destinations")
    @classmethod
    def _upper_dest(cls, v: list[str]) -> list[str]:
        return [d.strip().upper() for d in v]

    @field_validator("interests")
    @classmethod
    def _clean_interests(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(i.strip().lower() for i in v if i.strip()))

    @model_validator(mode="after")
    def _check(self) -> TripCreate:
        nights = (self.end_date - self.start_date).days
        if nights < 1:
            raise ValueError("end_date must be after start_date")
        if nights > 30:
            raise ValueError("Trips longer than 30 nights are not supported")
        if nights < len(self.destinations):
            raise ValueError("Need at least one night per destination")
        if self.origin in self.destinations:
            raise ValueError("Origin cannot also be a destination")
        if len(set(self.destinations)) != len(self.destinations):
            raise ValueError("Destinations must be unique")
        return self


class TripEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    seq: int
    agent: str | None
    kind: str
    message: str
    created_at: datetime


class TripSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    origin: str
    destinations: list[str]
    start_date: date
    end_date: date
    adults: int
    children: int
    budget: float
    currency: str
    status: str
    current_step: str | None
    created_at: datetime
    completed_at: datetime | None


class TripOut(TripSummary):
    cabin_class: str
    hotel_min_stars: int
    pace: str
    travel_style: str
    interests: list[str]
    dietary_needs: str | None
    accessibility_needs: str | None
    notes: str | None
    error: str | None
    plan: dict[str, Any] | None
    plan_version: int


class MessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    changes: list[str] = Field(default_factory=list)
    created_at: datetime


class ChatResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
    trip: TripOut


# ------------------------------------------------------------------ bookings
class TravelerIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    traveler_type: Literal["adult", "child"] = "adult"
    date_of_birth: date | None = None


class BookingCreate(BaseModel):
    offer_id: str = Field(min_length=3, max_length=100)
    trip_id: int | None = None
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=40)
    travelers: list[TravelerIn] = Field(min_length=1, max_length=17)


class TravelerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    first_name: str
    last_name: str
    traveler_type: str
    date_of_birth: date | None
    ticket_number: str | None


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reference: str
    kind: str
    provider: str
    status: str
    offer_id: str
    trip_id: int | None
    summary: str
    details: dict[str, Any]
    total_price: float
    currency: str
    refund_amount: float | None
    contact_email: str
    contact_phone: str | None
    created_at: datetime
    cancelled_at: datetime | None
    travelers: list[TravelerOut]
    simulated: bool = True


class HealthOut(BaseModel):
    status: str
    version: str
    llm_configured: bool
    llm_model: str
    flight_provider: str
    hotel_provider: str
    web_search: str
    database: str
