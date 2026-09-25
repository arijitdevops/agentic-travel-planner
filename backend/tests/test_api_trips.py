import json

import pytest

from tests.conftest import future

H = {"X-User-Email": "planner@example.com"}


def trip_payload(**overrides):
    body = {
        "origin": "LHR", "destinations": ["CDG", "FCO"], "start_date": str(future(40)), "end_date": str(future(45)),
        "adults": 2, "children": 0, "budget": 6000, "interests": ["Food", "history", "food"], "pace": "balanced",
        "travel_style": "comfort", "dietary_needs": "vegetarian", "notes": "Anniversary trip",
    }
    body.update(overrides)
    return body


@pytest.fixture()
def planned_trip(client):
    r = client.post("/api/trips", headers=H, json=trip_payload())
    assert r.status_code == 202, r.text
    return client.get(f"/api/trips/{r.json()['id']}", headers=H).json()


def test_plan_trip_end_to_end(planned_trip, fake_llm):
    trip = planned_trip
    assert trip["status"] == "completed", trip["error"]
    assert trip["interests"] == ["food", "history"]
    plan = trip["plan"]
    assert trip["title"] == "Food and History Escape"
    assert [leg["origin"] + leg["destination"] for leg in plan["legs"]] == ["LHRCDG", "CDGFCO", "FCOLHR"]
    assert [s["nights"] for s in plan["stays"]] == [3, 2]
    assert len(plan["itinerary"]["days"]) == 6
    # every chosen offer is one of the bookable options for its leg/stay
    for choice, options in zip(plan["flights"]["choices"], plan["flight_options"]):
        assert choice["offer_id"] in {o["id"] for o in options}
    for choice, options in zip(plan["hotels"]["choices"], plan["hotel_options"]):
        assert choice["offer_id"] in {o["id"] for o in options}
    # budget uses real quoted prices, not the LLM's guesses
    lines = {line["category"]: line["amount"] for line in plan["budget"]["lines"]}
    assert lines["Flights"] > 1 and lines["Accommodation"] > 1
    assert plan["budget"]["total"] == pytest.approx(sum(lines.values()), abs=0.01)
    assert [c["role"] for c in fake_llm.calls][:6] == [
        "Traveler Profile Analyst", "Destination Research Specialist", "Flight Booking Specialist",
        "Accommodation Specialist", "Itinerary Architect", "Travel Budget Analyst",
    ]


def test_progress_events_and_sse(client, planned_trip):
    tid = planned_trip["id"]
    events = client.get(f"/api/trips/{tid}/events", headers=H).json()
    kinds = [e["kind"] for e in events]
    assert kinds.count("agent_started") == 6 and kinds.count("agent_completed") == 6 and kinds[-1] == "done"
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    assert client.get(f"/api/trips/{tid}/events", headers=H, params={"after": len(events) - 1}).json()[0]["kind"] == "done"

    with client.stream("GET", f"/api/trips/{tid}/stream", params={"user": "planner@example.com"}) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    progress = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ") and '"seq"' in line]
    assert len(progress) == len(events)
    assert 'event: status\ndata: {"status": "completed"}' in body
    assert client.get(f"/api/trips/{tid}/stream").status_code == 404  # demo user does not own it


def test_list_isolated_per_user(client, planned_trip):
    assert planned_trip["id"] in [t["id"] for t in client.get("/api/trips", headers=H).json()]
    other = {"X-User-Email": "someone@example.com"}
    assert planned_trip["id"] not in [t["id"] for t in client.get("/api/trips", headers=other).json()]
    assert client.get(f"/api/trips/{planned_trip['id']}", headers=other).status_code == 404


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"end_date": str(future(40))}, "end_date must be after"),
        ({"destinations": ["CDG", "FCO", "BCN", "AMS"], "end_date": str(future(42))}, "one night per destination"),
        ({"destinations": ["LHR"]}, "Origin cannot"),
        ({"end_date": str(future(80))}, "30 nights"),
        ({"destinations": ["CDG", "CDG"]}, "unique"),
    ],
)
def test_trip_validation(client, overrides, fragment):
    r = client.post("/api/trips", headers=H, json=trip_payload(**overrides))
    assert r.status_code == 422 and fragment in r.text


def test_unknown_location_rejected(client):
    r = client.post("/api/trips", headers=H, json=trip_payload(destinations=["XYZ"]))
    assert r.status_code == 422 and "XYZ" in r.text


def test_without_gemini_key_planning_fails_gracefully_but_options_remain(client_no_llm):
    r = client_no_llm.post("/api/trips", json=trip_payload(destinations=["HND"], origin="ICN"))
    trip = client_no_llm.get(f"/api/trips/{r.json()['id']}").json()
    assert trip["status"] == "failed" and "GEMINI_API_KEY" in trip["error"]
    assert trip["plan"]["flight_options"][0] and trip["plan"]["hotel_options"][0]
    events = client_no_llm.get(f"/api/trips/{trip['id']}/events").json()
    assert events[-1]["kind"] == "error"
    assert client_no_llm.post(f"/api/trips/{trip['id']}/messages", json={"message": "hi"}).status_code == 409


def test_llm_failure_marks_trip_failed(client, fake_llm):
    fake_llm.fail_on = "Itinerary"
    r = client.post("/api/trips", headers=H, json=trip_payload(destinations=["BCN"]))
    trip = client.get(f"/api/trips/{r.json()['id']}", headers=H).json()
    assert trip["status"] == "failed" and "simulated LLM outage" in trip["error"]


def test_invalid_offer_ids_fall_back_to_real_options(client, fake_llm, monkeypatch):
    original = fake_llm._answer

    def bad_ids(role, prompt):
        ans = original(role, prompt)
        if role in ("Flight Booking Specialist", "Accommodation Specialist"):
            for c in ans["choices"]:
                c["recommended_offer_id"] = "HALLUCINATED-123"
        return ans

    monkeypatch.setattr(fake_llm, "_answer", bad_ids)
    r = client.post("/api/trips", headers=H, json=trip_payload(destinations=["AMS"]))
    plan = client.get(f"/api/trips/{r.json()['id']}", headers=H).json()["plan"]
    for choice, options in zip(plan["flights"]["choices"], plan["flight_options"]):
        assert choice["offer_id"] == options[0]["id"] and "Auto-selected" in choice["reasoning"]
    for choice, options in zip(plan["hotels"]["choices"], plan["hotel_options"]):
        assert choice["offer_id"] == options[0]["id"]


def test_chat_question_does_not_change_plan(client, planned_trip):
    tid = planned_trip["id"]
    r = client.post(f"/api/trips/{tid}/messages", headers=H, json={"message": "Is Rome walkable?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["assistant_message"]["content"].startswith("Sure")
    assert body["trip"]["plan_version"] == planned_trip["plan_version"]
    msgs = client.get(f"/api/trips/{tid}/messages", headers=H).json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]


def test_chat_can_swap_hotel_and_edit_itinerary(client, planned_trip, fake_llm):
    plan = planned_trip["plan"]
    new_hotel = plan["hotel_options"][1][-1]["id"]
    itinerary = json.loads(json.dumps(plan["itinerary"]))
    itinerary["days"][1]["theme"] = "Cooking class day"
    fake_llm.refinement = {
        "reply": "Done - I switched your Rome hotel and added a cooking class.",
        "changes": ["Rome hotel changed", "Day 2 now a cooking class"],
        "updated_itinerary": itinerary,
        "flight_changes": [],
        "hotel_changes": [{"stay_index": 1, "recommended_offer_id": new_hotel, "alternative_offer_ids": [], "reasoning": "Cheaper"}],
    }
    body = client.post(f"/api/trips/{planned_trip['id']}/messages", headers=H, json={"message": "Cheaper hotel in Rome and a cooking class"}).json()
    trip = body["trip"]
    assert trip["plan_version"] == planned_trip["plan_version"] + 1
    assert trip["plan"]["hotels"]["choices"][1]["offer_id"] == new_hotel
    assert trip["plan"]["hotels"]["choices"][0]["offer_id"] == plan["hotels"]["choices"][0]["offer_id"]
    assert trip["plan"]["itinerary"]["days"][1]["theme"] == "Cooking class day"
    assert body["assistant_message"]["changes"] == ["Rome hotel changed", "Day 2 now a cooking class"]
    new_price = next(o["total_price"] for o in trip["plan"]["hotel_options"][1] if o["id"] == new_hotel)
    first_price = next(o["total_price"] for o in trip["plan"]["hotel_options"][0] if o["id"] == plan["hotels"]["choices"][0]["offer_id"])
    acc = next(line["amount"] for line in trip["plan"]["budget"]["lines"] if line["category"] == "Accommodation")
    assert acc == pytest.approx(new_price + first_price, abs=0.01)


def test_chat_without_key_returns_503(client_no_llm, planned_trip):
    # planned_trip belongs to H; create the same state for the demo user via the fake-LLM client is not possible here,
    # so just check the 404/503 surface on a trip that exists for this user.
    r = client_no_llm.post(f"/api/trips/{planned_trip['id']}/messages", headers=H, json={"message": "hello"})
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]


def test_booking_linked_to_trip_and_delete(client, planned_trip):
    tid = planned_trip["id"]
    offer_id = planned_trip["plan"]["flights"]["choices"][0]["offer_id"]
    r = client.post("/api/bookings", headers=H, json={
        "offer_id": offer_id, "trip_id": tid, "contact_email": "p@example.com",
        "travelers": [{"first_name": "A", "last_name": "One"}, {"first_name": "B", "last_name": "Two"}],
    })
    assert r.status_code == 201, r.text
    assert [b["trip_id"] for b in client.get("/api/bookings", headers=H, params={"trip_id": tid}).json()] == [tid]
    assert client.delete(f"/api/trips/{tid}", headers=H).status_code == 204
    assert client.get(f"/api/trips/{tid}", headers=H).status_code == 404
    # booking survives trip deletion, unlinked
    assert client.get(f"/api/bookings/{r.json()['reference']}", headers=H).json()["trip_id"] is None


def test_replan(client, planned_trip):
    r = client.post(f"/api/trips/{planned_trip['id']}/replan", headers=H)
    assert r.status_code == 202
    trip = client.get(f"/api/trips/{planned_trip['id']}", headers=H).json()
    assert trip["status"] == "completed" and trip["plan_version"] == planned_trip["plan_version"] + 1
