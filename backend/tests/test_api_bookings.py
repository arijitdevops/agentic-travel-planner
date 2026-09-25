from tests.conftest import future

H = {"X-User-Email": "alice@example.com"}


def _book(client, offer_id, travelers, headers=H, **extra):
    return client.post("/api/bookings", headers=headers, json={
        "offer_id": offer_id, "contact_email": "alice@example.com", "travelers": travelers, **extra,
    })


def test_book_list_get_cancel_flight(client):
    offer = client.get("/api/flights/search", params={"origin": "YYZ", "destination": "ORD", "departure_date": str(future(33))}).json()[0]
    r = _book(client, offer["id"], [{"first_name": "Alice", "last_name": "Smith"}])
    assert r.status_code == 201, r.text
    booking = r.json()
    assert booking["status"] == "confirmed" and booking["simulated"] is True
    assert booking["details"]["flight_number"] == offer["flight_number"]
    ref = booking["reference"]

    listed = client.get("/api/bookings", headers=H).json()
    assert ref in [b["reference"] for b in listed]
    assert client.get(f"/api/bookings/{ref.lower()}", headers=H).status_code == 200
    # other users cannot see or cancel it
    other = {"X-User-Email": "mallory@example.com"}
    assert client.get(f"/api/bookings/{ref}", headers=other).status_code == 404
    assert client.post(f"/api/bookings/{ref}/cancel", headers=other).status_code == 404

    cancelled = client.post(f"/api/bookings/{ref}/cancel", headers=H).json()
    assert cancelled["status"] == "cancelled" and cancelled["refund_amount"] == booking["total_price"]
    assert client.post(f"/api/bookings/{ref}/cancel", headers=H).status_code == 409
    assert ref in [b["reference"] for b in client.get("/api/bookings", headers=H, params={"status": "cancelled"}).json()]


def test_book_hotel(client):
    offer = client.get("/api/hotels/search", params={"city": "RAK", "check_in": str(future(15)), "check_out": str(future(18)), "guests": 1}).json()[0]
    r = _book(client, offer["id"], [{"first_name": "Alice", "last_name": "Smith"}])
    assert r.status_code == 201
    assert r.json()["kind"] == "hotel" and "Marrakech" in r.json()["summary"]


def test_booking_validation_errors(client):
    assert _book(client, "LF.NOPE.20300101.economy.1.0", [{"first_name": "A", "last_name": "B"}]).status_code == 409
    assert _book(client, "LF.NOPE.20300101.economy.1.0", []).status_code == 422
    offer = client.get("/api/flights/search", params={"origin": "YYZ", "destination": "ORD", "departure_date": str(future(34))}).json()[0]
    assert _book(client, offer["id"], [{"first_name": "A", "last_name": "B"}], trip_id=999999).status_code == 404
