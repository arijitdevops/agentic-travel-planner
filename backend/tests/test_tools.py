from app import db as db_module
from app.agents.tools import (
    CityGuideTool,
    DailyCostEstimatorTool,
    SearchFlightsTool,
    SearchHotelsTool,
    ToolContext,
    WebSearchTool,
)
from app.config import Settings
from tests.conftest import future


def _ctx(events=None, **settings):
    return ToolContext(
        session_factory=db_module.SessionLocal, adults=2, children=1,
        emit=(lambda a, k, m: events.append((a, k, m))) if events is not None else (lambda *a: None),
        settings=Settings(**settings) if settings else Settings(web_search_enabled=False),
    )


def test_search_flights_tool_lists_offer_ids_and_emits():
    events = []
    out = SearchFlightsTool(_ctx(events), "Flight Booking Specialist").run(origin="BCN", destination="LIS", departure_date=str(future(30)))
    assert out.count("LF.") >= 2 and ".2.1 |" in out
    assert events and events[0][0] == "Flight Booking Specialist" and events[0][1] == "tool"


def test_search_tools_report_errors_as_text():
    assert "failed" in SearchFlightsTool(_ctx()).run(origin="XXX", destination="LIS", departure_date=str(future(30)))
    assert "failed" in SearchHotelsTool(_ctx()).run(city_code="LIS", check_in=str(future(5)), check_out=str(future(4)))


def test_search_hotels_tool():
    out = SearchHotelsTool(_ctx()).run(city_code="ATH", check_in=str(future(30)), check_out=str(future(33)), min_stars=4)
    assert "LH.ATH" in out and ("4*" in out or "5*" in out)


def test_city_guide_and_costs():
    assert "Kyoto" not in CityGuideTool(_ctx()).run(city_code="KIX")
    assert "Osaka, Japan" in CityGuideTool(_ctx()).run(city_code="KIX")
    assert "No local data" in CityGuideTool(_ctx()).run(city_code="QQQ")
    out = DailyCostEstimatorTool(_ctx()).run(city_code="ZRH", days=2, travelers=2, travel_style="budget")
    # budget food 35 * cost index 1.6 = 56/person/day -> 224 for 2 people x 2 days
    assert "56.00 per person per day -> 224.00" in out


def test_web_search_disabled_and_failure(monkeypatch):
    assert "disabled" in WebSearchTool(_ctx()).run(query="Paris weather")

    def boom(*a, **k):
        raise ConnectionError("offline")

    monkeypatch.setattr("app.agents.tools.web_search", boom)
    out = WebSearchTool(_ctx(web_search_enabled=True)).run(query="Paris weather")
    assert "unavailable" in out
