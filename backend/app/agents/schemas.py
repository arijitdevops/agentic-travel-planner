"""Structured outputs produced by the agents (CrewAI ``output_pydantic``).

Kept deliberately flat (no dicts, no unions beyond ``None``) so they map cleanly
onto Gemini's structured-output schema.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TravelerProfile(BaseModel):
    summary: str = Field(description="Two or three sentences describing this traveler party and what they want")
    priorities: list[str] = Field(description="Ranked priorities for the trip")
    must_haves: list[str] = Field(default_factory=list, description="Non-negotiable requirements (dietary, accessibility, etc.)")
    things_to_avoid: list[str] = Field(default_factory=list)
    accommodation_preferences: str = ""
    flight_preferences: str = ""
    daily_rhythm: str = Field(default="", description="How full each day should be, start/end times, rest breaks")


class Experience(BaseModel):
    name: str
    description: str
    interest: str = Field(description="Which traveler interest this serves")
    estimated_cost_per_person: float = Field(default=0, description="USD, 0 if free")


class DestinationInsight(BaseModel):
    city: str
    overview: str
    best_areas_to_stay: list[str] = Field(default_factory=list)
    top_experiences: list[Experience] = Field(default_factory=list)
    food_and_drink: list[str] = Field(default_factory=list)
    local_tips: list[str] = Field(default_factory=list)
    weather_and_packing: str = ""
    entry_and_safety_notes: str = ""


class DestinationResearch(BaseModel):
    destinations: list[DestinationInsight]
    sources: list[str] = Field(default_factory=list, description="URLs consulted")


class FlightChoice(BaseModel):
    leg_index: int
    recommended_offer_id: str
    alternative_offer_ids: list[str] = Field(default_factory=list)
    reasoning: str = ""


class FlightSelection(BaseModel):
    choices: list[FlightChoice]
    summary: str = ""


class HotelChoice(BaseModel):
    stay_index: int
    recommended_offer_id: str
    alternative_offer_ids: list[str] = Field(default_factory=list)
    reasoning: str = ""


class HotelSelection(BaseModel):
    choices: list[HotelChoice]
    summary: str = ""


class Activity(BaseModel):
    time: str = Field(description="e.g. 09:00 or Morning")
    title: str
    description: str = ""
    category: str = Field(default="sightseeing", description="sightseeing|food|culture|nature|shopping|nightlife|transport|rest|other")
    location: str = ""
    estimated_cost: float = Field(default=0, description="USD per person")


class DayPlan(BaseModel):
    day: int
    date: str
    city: str
    theme: str
    activities: list[Activity]
    notes: str = ""


class Itinerary(BaseModel):
    title: str
    overview: str
    days: list[DayPlan]
    packing_list: list[str] = Field(default_factory=list)


class BudgetLine(BaseModel):
    category: str
    amount: float = Field(description="USD for the whole party")
    notes: str = ""


class BudgetBreakdown(BaseModel):
    currency: str = "USD"
    lines: list[BudgetLine]
    total: float = 0
    budget: float = 0
    within_budget: bool = True
    savings_tips: list[str] = Field(default_factory=list)
    summary: str = ""


class RefinementResult(BaseModel):
    reply: str = Field(description="Friendly answer to the traveler, in markdown")
    changes: list[str] = Field(default_factory=list, description="Short bullet list of what changed in the plan")
    updated_itinerary: Itinerary | None = Field(default=None, description="Full revised itinerary, or null if unchanged")
    flight_changes: list[FlightChoice] = Field(default_factory=list)
    hotel_changes: list[HotelChoice] = Field(default_factory=list)
