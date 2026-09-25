"""Crew wiring tests - the real CrewAI classes with a fake LLM (Gemini is never called)."""

import re
from datetime import date

import pytest
from crewai import Process
from crewai.tasks.task_output import TaskOutput

from app import db as db_module
from app.agents.crew import PLANNING_STEPS, RefinementCrew, TravelPlanningCrew, coerce_output, load_config
from app.agents.llm import LLMNotConfigured, build_llm
from app.agents.schemas import BudgetBreakdown, BudgetLine, TravelerProfile
from app.agents.tools import ToolContext
from app.config import Settings
from app.models import Trip
from app.services.planner import build_inputs, build_legs_and_stays, day_skeleton, reconcile_budget, split_nights
from tests.fakes import FakeLLM


def _ctx():
    return ToolContext(session_factory=db_module.SessionLocal, adults=2)


def test_planning_crew_structure():
    crew = TravelPlanningCrew(FakeLLM(), _ctx())
    assert crew.crew.process == Process.sequential
    assert [t.name for t in crew.crew.tasks] == [s.task_key for s in PLANNING_STEPS]
    roles = [a.role for a in crew.crew.agents]
    assert roles == ["Traveler Profile Analyst", "Destination Research Specialist", "Flight Booking Specialist",
                     "Accommodation Specialist", "Itinerary Architect", "Travel Budget Analyst"]
    tools = {a.role: sorted(t.name for t in a.tools) for a in crew.crew.agents}
    assert tools["Destination Research Specialist"] == ["city_guide", "web_search"]
    assert tools["Flight Booking Specialist"] == ["search_flights"]
    assert tools["Accommodation Specialist"] == ["search_hotels"]
    assert tools["Travel Budget Analyst"] == ["estimate_daily_costs"]
    itinerary = crew.tasks["itinerary_task"]
    assert [t.name for t in itinerary.context] == ["profile_task", "research_task", "flight_task", "hotel_task"]
    assert all(not a.allow_delegation for a in crew.crew.agents)


def test_refinement_crew_structure():
    crew = RefinementCrew(FakeLLM(), _ctx())
    assert crew.agent.role == "Trip Concierge"
    assert sorted(t.name for t in crew.agent.tools) == ["estimate_daily_costs", "search_flights", "search_hotels", "web_search"]


def _trip(**kw) -> Trip:
    base = dict(id=1, user_id=1, title="t", origin="LHR", destinations=["CDG", "FCO"], start_date=date(2030, 5, 1),
                end_date=date(2030, 5, 8), adults=2, children=1, budget=5000, currency="USD", cabin_class="economy",
                hotel_min_stars=3, pace="relaxed", travel_style="comfort", interests=["art"], dietary_needs=None,
                accessibility_needs="step-free access", notes=None)
    base.update(kw)
    return Trip(**base)


def test_every_task_placeholder_is_provided():
    trip = _trip()
    legs, stays = build_legs_and_stays(trip, {})
    plan = {"legs": legs, "stays": stays, "day_skeleton": day_skeleton(trip, legs, stays),
            "flight_options": [[] for _ in legs], "hotel_options": [[] for _ in stays]}
    inputs = build_inputs(trip, plan, {})
    _, tasks = load_config()
    for key, cfg in tasks.items():
        if key == "refine_task":
            continue
        for name in re.findall(r"\{(\w+)\}", cfg["description"] + cfg["expected_output"]):
            assert name in inputs, f"{key} uses {{{name}}} which build_inputs does not provide"
    assert "step-free access" in inputs["trip_brief"]
    assert "2 adults and 1 child" == inputs["travelers_text"]


def test_legs_stays_and_skeleton():
    trip = _trip()
    legs, stays = build_legs_and_stays(trip, {})
    assert [(l["origin"], l["destination"], l["date"]) for l in legs] == [
        ("LHR", "CDG", "2030-05-01"), ("CDG", "FCO", "2030-05-05"), ("FCO", "LHR", "2030-05-08")]
    assert [(s["check_in"], s["check_out"], s["nights"]) for s in stays] == [
        ("2030-05-01", "2030-05-05", 4), ("2030-05-05", "2030-05-08", 3)]
    days = day_skeleton(trip, legs, stays)
    assert len(days) == 8 and days[0]["travel"] and days[4]["city"] == "FCO" and days[-1]["travel"]
    assert split_nights(7, 3) == [3, 2, 2]


def test_reconcile_budget_overrides_transport_and_lodging():
    plan = {
        "legs": [{}], "stays": [{}],
        "flights": {"choices": [{"offer_id": "f1"}]}, "hotels": {"choices": [{"offer_id": "h1"}]},
        "flight_options": [[{"id": "f1", "total_price": 800.0}]], "hotel_options": [[{"id": "h1", "total_price": 900.0}]],
    }
    agent = BudgetBreakdown(lines=[BudgetLine(category="Flights", amount=1), BudgetLine(category="Hotel", amount=1),
                                   BudgetLine(category="Food and drink", amount=300)], savings_tips=["x"])
    out = reconcile_budget(plan, 1500, "USD", agent)
    assert [(l["category"], l["amount"]) for l in out["lines"]] == [("Flights", 800), ("Accommodation", 900), ("Food and drink", 300)]
    assert out["total"] == 2000 and out["within_budget"] is False and out["savings_tips"] == ["x"]


def test_coerce_output_parses_fenced_json():
    raw = '```json\n{"summary": "s", "priorities": ["a"]}\n```'
    out = coerce_output(TaskOutput(description="d", raw=raw, agent="x"), TravelerProfile)
    assert isinstance(out, TravelerProfile) and out.priorities == ["a"]
    with pytest.raises(ValueError):
        coerce_output(TaskOutput(description="d", raw="no json here", agent="x"), TravelerProfile)


def test_build_llm_requires_key_and_targets_gemini():
    with pytest.raises(LLMNotConfigured):
        build_llm(Settings(gemini_api_key=None))
    llm = build_llm(Settings(gemini_api_key="test-key", gemini_model="gemini-2.5-flash"))
    assert llm.model == "gemini-2.5-flash" and llm.provider == "gemini"
