from tests.conftest import future


def test_health_reports_degraded_llm(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["database"] == "ok"
    assert body["llm_configured"] is False
    assert body["flight_provider"] == "local"


def test_me_defaults_to_demo_user_and_can_be_renamed(client):
    assert client.get("/api/me").json()["email"] == "demo@travelplanner.local"
    h = {"X-User-Email": "Sam@Example.com"}
    assert client.get("/api/me", headers=h).json()["email"] == "sam@example.com"
    assert client.put("/api/me", headers=h, json={"name": "Sam Traveler"}).json()["name"] == "Sam Traveler"
    assert client.get("/api/me", headers={"X-User-Email": "not-an-email"}).status_code == 400


def test_locations(client):
    all_locs = client.get("/api/locations").json()
    assert len(all_locs) >= 30 and all(loc["has_hotels"] for loc in all_locs)
    tokyo = client.get("/api/locations", params={"q": "tok"}).json()
    assert [loc["iata"] for loc in tokyo] == ["HND"]


def test_flight_search_and_offer_lookup(client):
    r = client.get("/api/flights/search", params={"origin": "JFK", "destination": "MIA", "departure_date": str(future(20)), "adults": 2})
    assert r.status_code == 200
    offers = r.json()
    assert offers and offers[0]["adults"] == 2
    one = client.get(f"/api/flights/offers/{offers[0]['id']}").json()
    assert one["total_price"] == offers[0]["total_price"]
    assert client.get("/api/flights/offers/LF.NOPE.20300101.economy.1.0").status_code == 404
    assert client.get("/api/flights/search", params={"origin": "ZZZ", "destination": "MIA", "departure_date": str(future(5))}).status_code == 400


def test_hotel_search_and_offer_lookup(client):
    r = client.get("/api/hotels/search", params={"city": "CPT", "check_in": str(future(10)), "check_out": str(future(14)), "guests": 2, "min_stars": 3})
    offers = r.json()
    assert r.status_code == 200 and offers and all(o["stars"] >= 3 for o in offers)
    assert client.get(f"/api/hotels/offers/{offers[0]['id']}").json()["hotel_code"] == offers[0]["hotel_code"]
    assert client.get(f"/api/flights/offers/{offers[0]['id']}").status_code == 404
