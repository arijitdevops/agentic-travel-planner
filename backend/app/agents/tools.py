"""Tools available to the agents.

Each tool gets a :class:`ToolContext` so it can open its own DB session (tools
run in the crew's worker thread), knows the size of the traveling party and
can report progress events to the UI.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Airport
from app.providers import FlightOffer, HotelOffer, ProviderError, get_flight_provider, get_hotel_provider
from app.providers.mock_data import DAILY_COSTS, rooms_needed

log = logging.getLogger(__name__)

EmitFn = Callable[[str | None, str, str], None]


@dataclass
class ToolContext:
    session_factory: Callable[[], Session]
    adults: int = 1
    children: int = 0
    cabin_class: str = "economy"
    emit: EmitFn = field(default=lambda agent, kind, message: None)
    settings: Settings = field(default_factory=get_settings)


# ---------------------------------------------------------------- formatting
def _hm(minutes: int) -> str:
    return f"{minutes // 60}h{minutes % 60:02d}m"


def format_flight(o: FlightOffer) -> str:
    stops = "nonstop" if o.stops == 0 else f"{o.stops} stop via {o.via}"
    return (
        f"{o.id} | {o.airline_name} {o.flight_number} | dep {o.departure[:16].replace('T', ' ')} "
        f"arr {o.arrival[:16].replace('T', ' ')} | {_hm(o.duration_minutes)} | {stops} | "
        f"{o.currency} {o.total_price:,.2f}"
    )


def format_hotel(o: HotelOffer) -> str:
    extras = []
    if o.breakfast_included:
        extras.append("breakfast")
    if o.free_cancellation:
        extras.append("free cancellation")
    if "Wheelchair accessible" in o.amenities:
        extras.append("accessible")
    return (
        f"{o.id} | {o.name} | {o.neighborhood} | {o.stars}* | {o.rating}/10 ({o.review_count} reviews) | "
        f"{o.rooms} x {o.room_name} | {o.currency} {o.total_price:,.2f} for {o.nights} nights"
        + (f" | {', '.join(extras)}" if extras else "")
    )


def _parse_date(value: str) -> date:
    return date.fromisoformat(value.strip()[:10])


# --------------------------------------------------------------------- tools
class _ContextTool(BaseTool):
    _ctx: ToolContext = PrivateAttr()
    _agent_label: str | None = PrivateAttr(default=None)

    def __init__(self, ctx: ToolContext, agent_label: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._ctx = ctx
        self._agent_label = agent_label

    def _emit(self, message: str) -> None:
        try:
            self._ctx.emit(self._agent_label, "tool", message)
        except Exception:  # pragma: no cover - progress must never break a run
            log.exception("progress emit failed")


class SearchFlightsInput(BaseModel):
    origin: str = Field(description="IATA code of the departure airport, e.g. LHR")
    destination: str = Field(description="IATA code of the arrival airport, e.g. CDG")
    departure_date: str = Field(description="Departure date as YYYY-MM-DD")
    cabin_class: str | None = Field(default=None, description="economy, premium_economy or business")


class SearchFlightsTool(_ContextTool):
    name: str = "search_flights"
    description: str = (
        "Search bookable flights for the traveling party on one date. Returns one offer per line: "
        "offer id | carrier and flight | departure and arrival (local) | duration | stops | total price."
    )
    args_schema: type[BaseModel] = SearchFlightsInput

    def _run(self, origin: str, destination: str, departure_date: str, cabin_class: str | None = None) -> str:
        cabin = cabin_class or self._ctx.cabin_class
        self._emit(f"Searching flights {origin.upper()} -> {destination.upper()} on {departure_date}")
        try:
            with self._ctx.session_factory() as db:
                offers = get_flight_provider(db, self._ctx.settings).search_flights(
                    origin, destination, _parse_date(departure_date), self._ctx.adults, self._ctx.children, cabin, 8  # type: ignore[arg-type]
                )
        except (ProviderError, ValueError) as exc:
            return f"Flight search failed: {exc}"
        if not offers:
            return "No flights found for that route and date. Try an adjacent date."
        return "\n".join(format_flight(o) for o in offers)


class SearchHotelsInput(BaseModel):
    city_code: str = Field(description="IATA code of the city, e.g. CDG for Paris")
    check_in: str = Field(description="YYYY-MM-DD")
    check_out: str = Field(description="YYYY-MM-DD")
    min_stars: int | None = Field(default=None, description="Minimum star rating 2-5")
    max_nightly_rate: float | None = Field(default=None, description="Maximum price per night in USD for all rooms")


class SearchHotelsTool(_ContextTool):
    name: str = "search_hotels"
    description: str = (
        "Search bookable hotels in a city for the traveling party. Returns one offer per line: "
        "offer id | hotel | neighbourhood | stars | guest rating | room | total price | perks."
    )
    args_schema: type[BaseModel] = SearchHotelsInput

    def _run(self, city_code: str, check_in: str, check_out: str, min_stars: int | None = None, max_nightly_rate: float | None = None) -> str:
        guests = self._ctx.adults + self._ctx.children
        rooms = rooms_needed(guests)
        self._emit(f"Searching hotels in {city_code.upper()} {check_in} to {check_out}")
        try:
            with self._ctx.session_factory() as db:
                offers = get_hotel_provider(db, self._ctx.settings).search_hotels(
                    city_code, _parse_date(check_in), _parse_date(check_out), guests, rooms, min_stars, max_nightly_rate, 8
                )
        except (ProviderError, ValueError) as exc:
            return f"Hotel search failed: {exc}"
        if not offers:
            return "No hotels matched. Relax the star rating or price filter."
        return "\n".join(format_hotel(o) for o in offers)


class WebSearchInput(BaseModel):
    query: str = Field(description="What to search the web for")


def web_search(query: str, settings: Settings | None = None) -> list[dict[str, str]]:
    """Tavily when ``TAVILY_API_KEY`` is set, otherwise DuckDuckGo (no key needed)."""
    settings = settings or get_settings()
    n = settings.web_search_max_results
    if settings.tavily_api_key:
        from tavily import TavilyClient

        res = TavilyClient(api_key=settings.tavily_api_key).search(query, max_results=n)
        return [{"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")} for r in res.get("results", [])]
    from ddgs import DDGS

    return [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")} for r in DDGS().text(query, max_results=n)]


class WebSearchTool(_ContextTool):
    name: str = "web_search"
    description: str = "Search the web for current travel information. Returns title, URL and snippet per result."
    args_schema: type[BaseModel] = WebSearchInput

    def _run(self, query: str) -> str:
        if not self._ctx.settings.web_search_enabled:
            return "Web search is disabled; rely on your own knowledge and say so."
        self._emit(f"Web search: {query}")
        try:
            results = web_search(query, self._ctx.settings)
        except Exception as exc:  # network errors, rate limits...
            log.warning("web search failed: %s", exc)
            return f"Web search unavailable ({type(exc).__name__}); rely on your own knowledge and say so."
        if not results:
            return "No results."
        return "\n\n".join(f"{r['title']}\n{r['url']}\n{r['snippet']}" for r in results)


class CityCodeInput(BaseModel):
    city_code: str = Field(description="IATA code of the city, e.g. HND for Tokyo")


def _daily_costs(airport: Airport, style: str) -> dict[str, float]:
    base = DAILY_COSTS.get(style, DAILY_COSTS["comfort"])
    return {k: round(v * airport.cost_index, 2) for k, v in base.items()}


class CityGuideTool(_ContextTool):
    name: str = "city_guide"
    description: str = "Local facts for a supported city: country, currency, language, time zone, main neighbourhoods and price level."
    args_schema: type[BaseModel] = CityCodeInput

    def _run(self, city_code: str) -> str:
        with self._ctx.session_factory() as db:
            a = db.get(Airport, city_code.strip().upper())
            if a is None:
                return f"No local data for '{city_code}'."
            level = "very expensive" if a.cost_index >= 1.4 else "expensive" if a.cost_index >= 1.15 else "moderate" if a.cost_index >= 0.8 else "affordable"
            return (
                f"{a.city}, {a.country} ({a.region}). Airport: {a.name} ({a.iata}). Currency: {a.currency}. "
                f"Language: {a.language}. Time zone: {a.timezone}. Price level: {level} (index {a.cost_index}). "
                f"Main neighbourhoods: {', '.join(a.neighborhoods)}."
            )


class DailyCostsInput(BaseModel):
    city_code: str = Field(description="IATA code of the city")
    days: int = Field(description="Number of days spent in the city")
    travelers: int = Field(description="Number of travelers")
    travel_style: str = Field(default="comfort", description="budget, comfort or luxury")


class DailyCostEstimatorTool(_ContextTool):
    name: str = "estimate_daily_costs"
    description: str = "Estimate food, local transport and activity costs in USD for a group staying N days in a city."
    args_schema: type[BaseModel] = DailyCostsInput

    def _run(self, city_code: str, days: int, travelers: int, travel_style: str = "comfort") -> str:
        with self._ctx.session_factory() as db:
            a = db.get(Airport, city_code.strip().upper())
            if a is None:
                return f"No cost data for '{city_code}'."
            per = _daily_costs(a, travel_style)
        lines = [f"{a.city} - {days} day(s), {travelers} traveler(s), {travel_style} style (USD):"]
        total = 0.0
        for cat, amount in per.items():
            subtotal = round(amount * days * travelers, 2)
            total += subtotal
            lines.append(f"- {cat.replace('_', ' ')}: {amount:.2f} per person per day -> {subtotal:,.2f}")
        lines.append(f"Total: {total:,.2f}")
        return "\n".join(lines)


def build_tools(ctx: ToolContext, agent_labels: dict[str, str]) -> dict[str, list[BaseTool]]:
    """Tools per agent key (see agents.yaml)."""
    lbl = agent_labels.get
    return {
        "traveler_profiler": [],
        "destination_researcher": [CityGuideTool(ctx, lbl("destination_researcher")), WebSearchTool(ctx, lbl("destination_researcher"))],
        "flight_specialist": [SearchFlightsTool(ctx, lbl("flight_specialist"))],
        "hotel_specialist": [SearchHotelsTool(ctx, lbl("hotel_specialist"))],
        "itinerary_planner": [CityGuideTool(ctx, lbl("itinerary_planner"))],
        "budget_analyst": [DailyCostEstimatorTool(ctx, lbl("budget_analyst"))],
        "trip_concierge": [
            SearchFlightsTool(ctx, lbl("trip_concierge")),
            SearchHotelsTool(ctx, lbl("trip_concierge")),
            WebSearchTool(ctx, lbl("trip_concierge")),
            DailyCostEstimatorTool(ctx, lbl("trip_concierge")),
        ],
    }
