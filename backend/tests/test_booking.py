from datetime import timedelta

import pytest

from app.deps import get_or_create_user
from app.models import utcnow
from app.providers import LocalInventoryProvider
from app.schemas import BookingCreate, TravelerIn
from app.services.booking import BookingError, cancel_booking, create_booking, refund_for
from tests.conftest import future

ADULT = TravelerIn(first_name="Ada", last_name="Lovelace")
CHILD = TravelerIn(first_name="Byron", last_name="Lovelace", traveler_type="child")


def _payload(offer_id, travelers):
    return BookingCreate(offer_id=offer_id, contact_email="ada@example.com", travelers=travelers)


def test_flight_booking_consumes_seats_and_issues_tickets(db):
    user = get_or_create_user(db, "booker@example.com")
    p = LocalInventoryProvider(db)
    offer = p.search_flights("AMS", "BER", future(25), adults=1, children=1)[0]
    booking = create_booking(db, user, _payload(offer.id, [ADULT, CHILD]))
    assert booking.status == "confirmed" and booking.kind == "flight"
    assert len(booking.reference) == 6 and booking.reference.isalnum()
    assert booking.seats == 2 and all(t.ticket_number for t in booking.travelers)
    assert float(booking.total_price) == offer.total_price
    assert p.get_flight_offer(offer.id).seats_left == offer.seats_left - 2


def test_traveler_mix_must_match_fare(db):
    user = get_or_create_user(db, "booker@example.com")
    offer = LocalInventoryProvider(db).search_flights("AMS", "BER", future(26), adults=2)[0]
    with pytest.raises(BookingError, match="2 adult"):
        create_booking(db, user, _payload(offer.id, [ADULT]))


def test_hotel_booking_consumes_rooms(db):
    user = get_or_create_user(db, "booker@example.com")
    p = LocalInventoryProvider(db)
    offer = p.search_hotels("LIS", future(40), future(43), guests=2)[0]
    booking = create_booking(db, user, _payload(offer.id, [ADULT, TravelerIn(first_name="Bo", last_name="B")]))
    assert booking.reference.startswith("H") and booking.kind == "hotel" and booking.rooms == 1
    assert p.get_hotel_offer(offer.id).rooms_left == offer.rooms_left - 1


def test_guest_count_must_match_rate(db):
    user = get_or_create_user(db, "booker@example.com")
    offer = LocalInventoryProvider(db).search_hotels("LIS", future(40), future(41), guests=2)[0]
    with pytest.raises(BookingError, match="2 guest"):
        create_booking(db, user, _payload(offer.id, [ADULT]))


def test_sold_out_flight_is_rejected(db):
    user = get_or_create_user(db, "bulk@example.com")
    p = LocalInventoryProvider(db)
    day = future(50)
    offer = p.search_flights("PRG", "ATH", day, adults=9, cabin_class="business")[0]
    adults = [TravelerIn(first_name=f"P{i}", last_name="X") for i in range(9)]
    create_booking(db, user, _payload(offer.id, adults))  # 12 business seats -> 3 left
    with pytest.raises(BookingError) as exc:
        create_booking(db, user, _payload(offer.id, adults))
    assert exc.value.status_code == 409


def test_cancel_within_24h_is_full_refund(db):
    user = get_or_create_user(db, "booker@example.com")
    offer = LocalInventoryProvider(db).search_flights("DXB", "BOM", future(30))[0]
    booking = create_booking(db, user, _payload(offer.id, [ADULT]))
    cancelled = cancel_booking(db, booking)
    assert cancelled.status == "cancelled" and float(cancelled.refund_amount) == float(booking.total_price)
    with pytest.raises(BookingError):
        cancel_booking(db, cancelled)


def test_refund_policies(db):
    user = get_or_create_user(db, "booker@example.com")
    p = LocalInventoryProvider(db)
    eco = create_booking(db, user, _payload(p.search_flights("SIN", "BKK", future(30))[0].id, [ADULT]))
    eco.created_at = utcnow() - timedelta(days=3)
    assert refund_for(eco) == 0.0
    hotel_offer = p.search_hotels("SIN", future(30), future(32), guests=1, min_stars=4)[0]
    hotel = create_booking(db, user, _payload(hotel_offer.id, [ADULT]))
    expected = float(hotel.total_price) if hotel_offer.free_cancellation else float(hotel.total_price) - hotel_offer.nightly_rate
    assert refund_for(hotel) == pytest.approx(expected, abs=0.02)
