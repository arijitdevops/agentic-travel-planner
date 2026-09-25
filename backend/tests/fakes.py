"""A deterministic stand-in for Gemini.

``FakeLLM`` subclasses CrewAI's ``BaseLLM`` so the real Crew/Agent/Task
machinery runs end to end. It answers based on which agent is calling and on
the prompt text it receives (e.g. it copies offer ids from the prompt), which
lets the tests prove the wiring without any network access.
"""

from __future__ import annotations

import json
import re
from typing import Any

from crewai import BaseLLM


def _text(messages: Any) -> str:
    if isinstance(messages, str):
        return messages
    parts = []
    for m in messages:
        content = m.get("content") if isinstance(m, dict) else str(m)
        if isinstance(content, list):
            content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        parts.append(str(content))
    return "\n".join(parts)


class FakeLLM(BaseLLM):
    calls: list[dict] = []
    refinement: dict | None = None
    fail_on: str | None = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(model=kwargs.pop("model", "fake/gemini-test"), **kwargs)
        self.calls = []

    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return True

    def get_context_window_size(self) -> int:
        return 200_000

    def call(self, messages, tools=None, callbacks=None, available_functions=None, from_task=None,
             from_agent=None, response_model=None):
        role = getattr(from_agent, "role", "") or ""
        prompt = _text(messages)
        self.calls.append({"role": role, "prompt": prompt, "response_model": getattr(response_model, "__name__", None)})
        if self.fail_on and self.fail_on in role:
            raise RuntimeError("simulated LLM outage")
        return json.dumps(self._answer(role, prompt))

    # ------------------------------------------------------------------
    def _answer(self, role: str, prompt: str) -> dict:
        if role == "Traveler Profile Analyst":
            return {
                "summary": "Two adults who love food and history, travelling comfortably.",
                "priorities": ["food", "history", "walkable neighbourhoods"],
                "must_haves": ["vegetarian options"],
                "things_to_avoid": ["red-eye flights"],
                "accommodation_preferences": "Central 3-4 star hotel",
                "flight_preferences": "Nonstop, daytime",
                "daily_rhythm": "Start 9:00, rest mid-afternoon, dinner 19:30",
            }
        if role == "Destination Research Specialist":
            cities = re.findall(r"Stay \d+: ([^(]+) \(", prompt)
            return {
                "destinations": [
                    {
                        "city": c.strip(),
                        "overview": f"{c.strip()} overview",
                        "best_areas_to_stay": ["Centre"],
                        "top_experiences": [{"name": "Old town walk", "description": "Guided walk", "interest": "history", "estimated_cost_per_person": 25}],
                        "food_and_drink": ["Local market"],
                        "local_tips": ["Buy a transit pass"],
                        "weather_and_packing": "Mild, bring layers",
                        "entry_and_safety_notes": "Check entry rules for your passport",
                    }
                    for c in dict.fromkeys(cities)
                ],
                "sources": ["https://example.org/guide"],
            }
        if role == "Flight Booking Specialist":
            choices = []
            for m in re.finditer(r"Leg (\d+): [A-Z]{3} -> [A-Z]{3} on [\d-]+\n(.*?)(?:\n\n|$)", prompt, re.S):
                ids = re.findall(r"(LF\.[A-Z0-9]+\.\d{8}\.[a-z_]+\.\d+\.\d+)", m.group(2))
                choices.append({"leg_index": int(m.group(1)), "recommended_offer_id": ids[-1] if ids else "BOGUS",
                                "alternative_offer_ids": ids[:1], "reasoning": "Good timing and price"})
            return {"choices": choices, "summary": "Daytime nonstop flights where possible."}
        if role == "Accommodation Specialist":
            choices = []
            pattern = r"Stay (\d+): [^\n]+?\([A-Z]{3}\) \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}\n(.*?)(?:\n\n|$)"
            for m in re.finditer(pattern, prompt, re.S):
                ids = re.findall(r"(LH\.[A-Z0-9]+\.[A-Z]{3}\.\d{8}\.\d{8}\.\d+\.\d+)", m.group(2))
                choices.append({"stay_index": int(m.group(1)), "recommended_offer_id": ids[1] if len(ids) > 1 else (ids[0] if ids else "BOGUS"),
                                "alternative_offer_ids": ids[:1], "reasoning": "Great location"})
            return {"choices": choices, "summary": "Central, well-rated hotels."}
        if role == "Itinerary Architect":
            days = re.findall(r"Day (\d+) \((\d{4}-\d{2}-\d{2})\): ([^\n-]+)", prompt)
            return {
                "title": "Food and History Escape",
                "overview": "A relaxed trip.",
                "days": [
                    {"day": int(n), "date": d, "city": c.strip(), "theme": "Explore",
                     "activities": [
                         {"time": "09:00", "title": "Breakfast", "description": "Cafe", "category": "food", "location": "Centre", "estimated_cost": 15},
                         {"time": "10:30", "title": "Museum", "description": "History museum", "category": "culture", "location": "Centre", "estimated_cost": 20},
                     ],
                     "notes": ""}
                    for n, d, c in days
                ],
                "packing_list": ["Walking shoes"],
            }
        if role == "Travel Budget Analyst":
            return {
                "currency": "USD",
                "lines": [
                    {"category": "Flights", "amount": 1.0, "notes": "LLM guess - must be overwritten"},
                    {"category": "Accommodation", "amount": 1.0, "notes": "LLM guess - must be overwritten"},
                    {"category": "Food and drink", "amount": 400, "notes": ""},
                    {"category": "Local transport", "amount": 80, "notes": ""},
                    {"category": "Activities and tickets", "amount": 150, "notes": ""},
                    {"category": "Contingency", "amount": 100, "notes": ""},
                ],
                "total": 999999, "budget": 0, "within_budget": True,
                "savings_tips": ["Eat lunch at markets"], "summary": "Comfortably within budget.",
            }
        if role == "Trip Concierge":
            return self.refinement or {"reply": "Sure - here is my answer.", "changes": [], "updated_itinerary": None,
                                       "flight_changes": [], "hotel_changes": []}
        raise AssertionError(f"unexpected agent role {role!r}")
