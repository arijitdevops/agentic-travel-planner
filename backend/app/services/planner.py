"""Trip-planning orchestration around the CrewAI crews.

``run_trip_planning`` is executed as a background job:

1. derive flight legs and hotel stays from the request,
2. pre-fetch real, bookable offers from the providers (so recommendations are
   grounded in inventory, and the user can book even if the LLM is unavailable),
3. run the six-agent crew, reporting progress to ``trip_events``,
4. validate every offer id the agents chose (falling back to the best
   pre-fetched option), overwrite flight/hotel costs in the budget with the
   real quoted prices, and store the assembled plan.

``run_refinement`` handles chat follow-ups with the concierge agent.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from crewai import BaseLLM
from crewai.tasks.task_output import TaskOutput
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db as db_module
from app.agents.crew import PLANNING_STEPS, RefinementCrew, TravelPlanningCrew, agent_labels
from app.agents.llm import LLMNotConfigured, build_llm
from app.agents.schemas import (
    BudgetBreakdown,
    BudgetLine,
    FlightChoice,
    FlightSelection,
    HotelChoice,
    HotelSelection,
    Itinerary,
)
from app.agents.tools import ToolContext, format_flight, format_hotel
from app.config import get_settings
from app.models import Airport, Trip, TripMessage, utcnow
from app.providers import (
    FlightOffer,
    HotelOffer,
    OfferNotFound,
    ProviderError,
    get_flight_provider,
    get_hotel_provider,
    provider_for_offer,
)
from app.providers.mock_data import rooms_needed
from app.services.events import emit_event

log = logging.getLogger(__name__)

LLMFactory = Callable[[], BaseLLM]
ORCHESTRATOR = "Orchestrator"


# --------------------------------------------------------------------------
# Trip geometry
# --------------------------------------------------------------------------
def split_nights(total_nights: int, n_destinations: int) -> list[int]:
    base, extra = divmod(total_nights, n_destinations)
    return [base + (1 if i < extra else 0) for i in range(n_destinations)]


def build_legs_and_stays(trip: Trip, cities: dict[str, Airport]) -> tuple[list[dict], list[dict]]:
    nights = split_nights((trip.end_date - trip.start_date).days, len(trip.destinations))
    legs: list[dict] = []
    stays: list[dict] = []
    cursor = trip.start_date
    prev = trip.origin
    for i, (dest, n) in enumerate(zip(trip.destinations, nights, strict=True)):
        legs.append(_leg(i, prev, dest, cursor, cities))
        stays.append({
            "index": i, "city_code": dest, "city": cities[dest].city if dest in cities else dest,
            "check_in": cursor.isoformat(), "check_out": (cursor + timedelta(days=n)).isoformat(), "nights": n,
        })
        cursor += timedelta(days=n)
        prev = dest
    legs.append(_leg(len(legs), prev, trip.origin, trip.end_date, cities))
    return legs, stays


def _leg(index: int, origin: str, dest: str, day: date, cities: dict[str, Airport]) -> dict:
    return {
        "index": index, "origin": origin, "destination": dest, "date": day.isoformat(),
        "origin_city": cities[origin].city if origin in cities else origin,
        "destination_city": cities[dest].city if dest in cities else dest,
    }


def day_skeleton(trip: Trip, legs: list[dict], stays: list[dict]) -> list[dict]:
    days = []
    total_days = (trip.end_date - trip.start_date).days + 1
    leg_by_date = {leg["date"]: leg for leg in legs}
    for n in range(total_days):
        d = trip.start_date + timedelta(days=n)
        iso = d.isoformat()
        stay = next((s for s in stays if s["check_in"] <= iso < s["check_out"]), stays[-1])
        leg = leg_by_date.get(iso)
        travel = f"travel {leg['origin_city']} to {leg['destination_city']}" if leg else None
        days.append({"day": n + 1, "date": iso, "city": stay["city"], "travel": travel})
    return days


# --------------------------------------------------------------------------
# Prompt inputs
# --------------------------------------------------------------------------
def travelers_text(trip: Trip) -> str:
    t = f"{trip.adults} adult{'s' if trip.adults != 1 else ''}"
    if trip.children:
        t += f" and {trip.children} child{'ren' if trip.children != 1 else ''}"
    return t


def trip_brief(trip: Trip, cities: dict[str, Airport]) -> str:
    def name(code: str) -> str:
        return f"{cities[code].city} ({code})" if code in cities else code

    lines = [
        f"From: {name(trip.origin)}",
        f"Destinations in order: {', '.join(name(d) for d in trip.destinations)}",
        f"Dates: {trip.start_date.isoformat()} to {trip.end_date.isoformat()} ({(trip.end_date - trip.start_date).days} nights)",
        f"Travelers: {travelers_text(trip)}",
        f"Total budget: {float(trip.budget):,.0f} {trip.currency} for everything",
        f"Travel style: {trip.travel_style}; pace: {trip.pace}; flights: {trip.cabin_class.replace('_', ' ')}; hotels: {trip.hotel_min_stars}+ stars",
        f"Interests: {', '.join(trip.interests) if trip.interests else 'not specified'}",
        f"Dietary needs: {trip.dietary_needs or 'none'}",
        f"Accessibility needs: {trip.accessibility_needs or 'none'}",
    ]
    if trip.notes:
        lines.append(f"Traveler notes: {trip.notes}")
    return "\n".join(lines)


def build_inputs(trip: Trip, plan: dict[str, Any], cities: dict[str, Airport]) -> dict[str, str]:
    legs, stays = plan["legs"], plan["stays"]
    flight_blocks = []
    for leg, offers in zip(legs, plan["flight_options"], strict=True):
        header = f"Leg {leg['index']}: {leg['origin']} -> {leg['destination']} on {leg['date']}"
        body = "\n".join(format_flight(FlightOffer.model_validate(o)) for o in offers) or "(no offers found - use search_flights)"
        flight_blocks.append(f"{header}\n{body}")
    hotel_blocks = []
    for stay, offers in zip(stays, plan["hotel_options"], strict=True):
        header = f"Stay {stay['index']}: {stay['city']} ({stay['city_code']}) {stay['check_in']} to {stay['check_out']}"
        body = "\n".join(format_hotel(HotelOffer.model_validate(o)) for o in offers) or "(no offers found - use search_hotels)"
        hotel_blocks.append(f"{header}\n{body}")
    skeleton = plan["day_skeleton"]
    return {
        "trip_brief": trip_brief(trip, cities),
        "today": date.today().isoformat(),
        "legs_text": "\n".join(f"Leg {l['index']}: {l['origin_city']} ({l['origin']}) -> {l['destination_city']} ({l['destination']}) on {l['date']}" for l in legs),
        "stays_text": "\n".join(f"Stay {s['index']}: {s['city']} ({s['city_code']}), check-in {s['check_in']}, check-out {s['check_out']}, {s['nights']} nights" for s in stays),
        "flight_options": "\n\n".join(flight_blocks),
        "hotel_options": "\n\n".join(hotel_blocks),
        "day_skeleton": "\n".join(
            f"Day {d['day']} ({d['date']}): {d['city']}" + (f" - {d['travel']}" if d["travel"] else "") for d in skeleton
        ),
        "day_count": str(len(skeleton)),
        "nights": str((trip.end_date - trip.start_date).days),
        "travelers_text": travelers_text(trip),
        "budget": f"{float(trip.budget):,.0f}",
        "currency": trip.currency,
        "cabin_class": trip.cabin_class.replace("_", " "),
        "travel_style": trip.travel_style,
        "hotel_min_stars": str(trip.hotel_min_stars),
        "pace": trip.pace,
    }


# --------------------------------------------------------------------------
# Offer pre-fetch and validation
# --------------------------------------------------------------------------
def _flight_rank(o: FlightOffer) -> float:
    """Lower is better: price with penalties for stops, long trips and red-eyes."""
    hour = int(o.departure[11:13]) if len(o.departure) >= 13 else 12
    penalty = o.stops * 0.18 + (0.12 if hour < 6 or hour >= 22 else 0) + o.duration_minutes / 6000
    return o.total_price * (1 + penalty)


def prefetch_offers(db: Session, trip: Trip, legs: list[dict], stays: list[dict]) -> tuple[list[list[dict]], list[list[dict]]]:
    fp = get_flight_provider(db)
    hp = get_hotel_provider(db)
    guests = trip.adults + trip.children
    flights: list[list[dict]] = []
    for leg in legs:
        try:
            offers = fp.search_flights(leg["origin"], leg["destination"], date.fromisoformat(leg["date"]),
                                       trip.adults, trip.children, trip.cabin_class, 8)  # type: ignore[arg-type]
        except ProviderError as exc:
            log.warning("flight prefetch failed for leg %s: %s", leg["index"], exc)
            offers = []
        offers.sort(key=_flight_rank)
        flights.append([o.model_dump(mode="json") for o in offers[:6]])
    hotels: list[list[dict]] = []
    for stay in stays:
        try:
            offers = hp.search_hotels(stay["city_code"], date.fromisoformat(stay["check_in"]), date.fromisoformat(stay["check_out"]),
                                      guests, rooms_needed(guests), trip.hotel_min_stars, None, 8)
        except ProviderError as exc:
            log.warning("hotel prefetch failed for stay %s: %s", stay["index"], exc)
            offers = []
        hotels.append([o.model_dump(mode="json") for o in offers])
    return flights, hotels


def _resolve(db: Session, offer_id: str) -> dict | None:
    kind, provider = provider_for_offer(db, offer_id)
    try:
        offer = provider.get_flight_offer(offer_id) if kind == "flight" else provider.get_hotel_offer(offer_id)  # type: ignore[union-attr]
    except (OfferNotFound, ProviderError):
        return None
    return offer.model_dump(mode="json")


def validate_flight_choices(db: Session, plan: dict, selection: FlightSelection | None) -> list[dict]:
    """One validated choice per leg; ensures the chosen offer is in that leg's options."""
    by_leg = {c.leg_index: c for c in (selection.choices if selection else [])}
    result = []
    for leg, options in zip(plan["legs"], plan["flight_options"], strict=True):
        choice = by_leg.get(leg["index"]) or FlightChoice(leg_index=leg["index"], recommended_offer_id="")
        known = {o["id"]: o for o in options}
        offer = known.get(choice.recommended_offer_id) or (_resolve(db, choice.recommended_offer_id) if choice.recommended_offer_id else None)
        if offer and (offer.get("origin"), offer.get("destination")) != (leg["origin"], leg["destination"]):
            offer = None
        reasoning = choice.reasoning
        if offer is None and options:
            offer = options[0]
            reasoning = (reasoning + " " if reasoning else "") + "(Auto-selected best-ranked option.)"
        if offer and offer["id"] not in known:
            options.insert(0, offer)
        alts = [a for a in choice.alternative_offer_ids if a in {o["id"] for o in options} and (not offer or a != offer["id"])]
        result.append({"leg_index": leg["index"], "offer_id": offer["id"] if offer else None,
                       "alternative_offer_ids": alts[:2], "reasoning": reasoning.strip()})
    return result


def validate_hotel_choices(db: Session, plan: dict, selection: HotelSelection | None) -> list[dict]:
    by_stay = {c.stay_index: c for c in (selection.choices if selection else [])}
    result = []
    for stay, options in zip(plan["stays"], plan["hotel_options"], strict=True):
        choice = by_stay.get(stay["index"]) or HotelChoice(stay_index=stay["index"], recommended_offer_id="")
        known = {o["id"]: o for o in options}
        offer = known.get(choice.recommended_offer_id) or (_resolve(db, choice.recommended_offer_id) if choice.recommended_offer_id else None)
        if offer and (offer.get("city_code"), offer.get("check_in"), offer.get("check_out")) != (stay["city_code"], stay["check_in"], stay["check_out"]):
            offer = None
        reasoning = choice.reasoning
        if offer is None and options:
            offer = options[0]
            reasoning = (reasoning + " " if reasoning else "") + "(Auto-selected top-rated option.)"
        if offer and offer["id"] not in known:
            options.insert(0, offer)
        alts = [a for a in choice.alternative_offer_ids if a in {o["id"] for o in options} and (not offer or a != offer["id"])]
        result.append({"stay_index": stay["index"], "offer_id": offer["id"] if offer else None,
                       "alternative_offer_ids": alts[:2], "reasoning": reasoning.strip()})
    return result


def selected_offer(plan: dict, kind: str, index: int) -> dict | None:
    choices = plan.get("flights" if kind == "flight" else "hotels", {}).get("choices", [])
    options = plan.get("flight_options" if kind == "flight" else "hotel_options", [])
    if index >= len(choices) or index >= len(options):
        return None
    oid = choices[index].get("offer_id")
    return next((o for o in options[index] if o["id"] == oid), None)


def reconcile_budget(plan: dict, budget: float, currency: str, agent_budget: BudgetBreakdown | None) -> dict:
    """Replace flight/hotel lines with real quoted prices and recompute totals."""
    flights_total = round(sum(o["total_price"] for i in range(len(plan["legs"])) if (o := selected_offer(plan, "flight", i))), 2)
    hotels_total = round(sum(o["total_price"] for i in range(len(plan["stays"])) if (o := selected_offer(plan, "hotel", i))), 2)
    lines = [
        BudgetLine(category="Flights", amount=flights_total, notes=f"{len(plan['legs'])} legs, quoted fares"),
        BudgetLine(category="Accommodation", amount=hotels_total, notes=f"{len(plan['stays'])} stays, quoted rates"),
    ]
    tips: list[str] = []
    summary = ""
    if agent_budget:
        for line in agent_budget.lines:
            cat = line.category.lower()
            if "flight" in cat or "accommodation" in cat or "hotel" in cat or "lodging" in cat:
                continue
            lines.append(BudgetLine(category=line.category, amount=round(max(0.0, line.amount), 2), notes=line.notes))
        tips, summary = agent_budget.savings_tips, agent_budget.summary
    total = round(sum(line.amount for line in lines), 2)
    return BudgetBreakdown(
        currency=currency, lines=lines, total=total, budget=budget, within_budget=total <= budget,
        savings_tips=tips, summary=summary,
    ).model_dump(mode="json")


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------
class _Progress:
    """Maps sequential task completions to started/completed events."""

    def __init__(self, trip_id: int) -> None:
        self.trip_id = trip_id
        self.labels = agent_labels()
        self.index = 0

    def start(self) -> None:
        if self.index < len(PLANNING_STEPS):
            step = PLANNING_STEPS[self.index]
            label = self.labels[step.agent_key]
            emit_event(self.trip_id, label, "agent_started", step.start_message, current_step=label)

    def on_task_complete(self, output: TaskOutput) -> None:
        if self.index < len(PLANNING_STEPS):
            step = PLANNING_STEPS[self.index]
            emit_event(self.trip_id, self.labels[step.agent_key], "agent_completed", step.done_message)
        self.index += 1
        self.start()


def _load_cities(db: Session, codes: list[str]) -> dict[str, Airport]:
    return {a.iata: a for a in db.scalars(select(Airport).where(Airport.iata.in_(codes))).all()}


def run_trip_planning(trip_id: int, llm_factory: LLMFactory | None = None) -> None:
    """Background job entry point. Never raises; failures are stored on the trip."""
    settings = get_settings()
    SessionLocal = db_module.SessionLocal
    try:
        with SessionLocal() as db:
            trip = db.get(Trip, trip_id)
            if trip is None:
                return
            trip.status, trip.error, trip.current_step = "running", None, ORCHESTRATOR
            db.commit()
            emit_event(trip_id, ORCHESTRATOR, "info", "Planning started")

            cities = _load_cities(db, [trip.origin, *trip.destinations])
            legs, stays = build_legs_and_stays(trip, cities)
            emit_event(trip_id, ORCHESTRATOR, "info", f"Searching live inventory for {len(legs)} flight legs and {len(stays)} hotel stays")
            flight_opts, hotel_opts = prefetch_offers(db, trip, legs, stays)
            plan: dict[str, Any] = {
                "legs": legs, "stays": stays, "day_skeleton": day_skeleton(trip, legs, stays),
                "flight_options": flight_opts, "hotel_options": hotel_opts,
            }
            trip.plan = plan
            db.commit()
            emit_event(trip_id, ORCHESTRATOR, "info",
                       f"Found {sum(map(len, flight_opts))} flight offers and {sum(map(len, hotel_opts))} hotel offers")
            inputs = build_inputs(trip, plan, cities)
            budget, currency = float(trip.budget), trip.currency
            adults, children, cabin = trip.adults, trip.children, trip.cabin_class

        llm = (llm_factory or build_llm)()
        progress = _Progress(trip_id)
        ctx = ToolContext(session_factory=SessionLocal, adults=adults, children=children, cabin_class=cabin,
                          emit=lambda agent, kind, msg: emit_event(trip_id, agent, kind, msg), settings=settings)
        crew = TravelPlanningCrew(llm, ctx, task_callback=progress.on_task_complete,
                                  max_iter=settings.agent_max_iter, verbose=settings.crew_verbose)
        progress.start()
        outputs = crew.run(inputs)

        with SessionLocal() as db:
            trip = db.get(Trip, trip_id)
            assert trip is not None
            plan = dict(trip.plan or plan)
            flights_sel = outputs["flight_task"]
            hotels_sel = outputs["hotel_task"]
            plan["profile"] = outputs["profile_task"].model_dump(mode="json")
            plan["research"] = outputs["research_task"].model_dump(mode="json")
            plan["flights"] = {"summary": getattr(flights_sel, "summary", ""),
                               "choices": validate_flight_choices(db, plan, flights_sel)}  # type: ignore[arg-type]
            plan["hotels"] = {"summary": getattr(hotels_sel, "summary", ""),
                              "choices": validate_hotel_choices(db, plan, hotels_sel)}  # type: ignore[arg-type]
            plan["itinerary"] = outputs["itinerary_task"].model_dump(mode="json")
            plan["budget"] = reconcile_budget(plan, budget, currency, outputs["budget_task"])  # type: ignore[arg-type]
            plan["generated_at"] = utcnow().isoformat()
            plan["model"] = getattr(llm, "model", "unknown")
            trip.plan = plan
            trip.plan_version += 1
            trip.status, trip.current_step, trip.completed_at = "completed", None, utcnow()
            if not trip.title or trip.title.startswith("Trip to"):
                trip.title = plan["itinerary"].get("title") or trip.title
            db.commit()
        emit_event(trip_id, ORCHESTRATOR, "done", "Your trip plan is ready")
    except LLMNotConfigured as exc:
        _fail(trip_id, str(exc))
    except Exception as exc:  # noqa: BLE001 - any agent/LLM failure must end the job cleanly
        log.exception("trip %s planning failed", trip_id)
        _fail(trip_id, f"Planning failed: {type(exc).__name__}: {exc}")


def _fail(trip_id: int, message: str) -> None:
    with db_module.SessionLocal() as db:
        trip = db.get(Trip, trip_id)
        if trip is not None:
            trip.status, trip.error, trip.current_step = "failed", message[:4000], None
            db.commit()
    emit_event(trip_id, ORCHESTRATOR, "error", message)


# --------------------------------------------------------------------------
# Chat refinement
# --------------------------------------------------------------------------
def plan_text(plan: dict) -> str:
    """Compact, LLM-friendly rendering of the current plan."""
    parts = []
    for i, leg in enumerate(plan.get("legs", [])):
        o = selected_offer(plan, "flight", i)
        parts.append(f"Leg {i} {leg['origin']}->{leg['destination']} {leg['date']}: " + (format_flight(FlightOffer.model_validate(o)) if o else "no flight selected"))
    for i, stay in enumerate(plan.get("stays", [])):
        o = selected_offer(plan, "hotel", i)
        parts.append(f"Stay {i} {stay['city']} {stay['check_in']}->{stay['check_out']}: " + (format_hotel(HotelOffer.model_validate(o)) if o else "no hotel selected"))
    if plan.get("itinerary"):
        parts.append("ITINERARY JSON: " + json.dumps(plan["itinerary"], ensure_ascii=False))
    if plan.get("budget"):
        b = plan["budget"]
        parts.append(f"BUDGET: total {b['total']} of {b['budget']} {b['currency']}; " + "; ".join(f"{l['category']} {l['amount']}" for l in b["lines"]))
    return "\n".join(parts)


class RefinementError(Exception):
    pass


def run_refinement(db: Session, trip: Trip, message: str, llm_factory: LLMFactory | None = None) -> TripMessage:
    settings = get_settings()
    if trip.status != "completed" or not trip.plan or "itinerary" not in trip.plan:
        raise RefinementError("The trip plan is not ready yet")
    llm = (llm_factory or build_llm)()

    history = "\n".join(f"{m.role}: {m.content}" for m in trip.messages[-6:]) or "(none)"
    cities = _load_cities(db, [trip.origin, *trip.destinations])
    user_msg = TripMessage(trip_id=trip.id, role="user", content=message)
    db.add(user_msg)
    db.commit()

    ctx = ToolContext(session_factory=db_module.SessionLocal, adults=trip.adults, children=trip.children,
                      cabin_class=trip.cabin_class, settings=settings)
    result = RefinementCrew(llm, ctx, max_iter=settings.agent_max_iter, verbose=settings.crew_verbose).run({
        "trip_brief": trip_brief(trip, cities),
        "plan_text": plan_text(trip.plan),
        "history": history,
        "message": message,
    })

    plan = json.loads(json.dumps(trip.plan))  # deep copy so SQLAlchemy sees a new value
    changes = list(result.changes)
    changed = False
    if result.updated_itinerary and result.updated_itinerary.days:
        if len(result.updated_itinerary.days) == len(plan["itinerary"]["days"]):
            plan["itinerary"] = result.updated_itinerary.model_dump(mode="json")
            changed = True
        else:
            changes.append("Itinerary change skipped: it did not keep the same number of days.")
    if result.flight_changes:
        current_f = {c["leg_index"]: c for c in plan["flights"]["choices"]}
        requested_f = {fc.leg_index: fc for fc in result.flight_changes}
        plan["flights"]["choices"] = validate_flight_choices(db, plan, FlightSelection(choices=[
            requested_f.get(i) or FlightChoice(leg_index=i, recommended_offer_id=c["offer_id"] or "", reasoning=c["reasoning"], alternative_offer_ids=c["alternative_offer_ids"])
            for i, c in current_f.items()
        ]))
        changed = True
    if result.hotel_changes:
        current_h = {c["stay_index"]: c for c in plan["hotels"]["choices"]}
        requested = {hc.stay_index: hc for hc in result.hotel_changes}
        plan["hotels"]["choices"] = validate_hotel_choices(db, plan, HotelSelection(choices=[
            requested.get(i) or HotelChoice(stay_index=i, recommended_offer_id=c["offer_id"] or "", reasoning=c["reasoning"], alternative_offer_ids=c["alternative_offer_ids"])
            for i, c in current_h.items()
        ]))
        changed = True
    if changed:
        old = plan.get("budget") or {}
        agent_lines = BudgetBreakdown(
            lines=[BudgetLine(**l) for l in old.get("lines", [])],
            savings_tips=old.get("savings_tips", []), summary=old.get("summary", ""),
        )
        plan["budget"] = reconcile_budget(plan, float(trip.budget), trip.currency, agent_lines)
        trip.plan = plan
        trip.plan_version += 1

    reply = TripMessage(trip_id=trip.id, role="assistant", content=result.reply, changes=changes if changed or changes else [])
    db.add(reply)
    db.commit()
    db.refresh(trip)
    return reply
