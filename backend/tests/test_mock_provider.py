from datetime import date, timedelta

import pytest

from app.providers import LocalInventoryProvider, OfferNotFound, ProviderError
from app.providers.mock_data import CITIES, generate_hotels, generate_schedules, rooms_needed
from tests.conftest import future


def test_generation_is_deterministic():
    assert generate_schedules() == generate_schedules()
    assert generate_hotels() == generate_hotels()


def test_inventory_covers_every_city():
    schedules = generate_schedules()
    hotels = generate_hotels()
    codes = {c.iata for c in CITIES}
    assert len(codes) >= 30
    assert {h["city_code"] for h in hotels} == codes
    pairs = {(s["origin"], s["destination"]) for s in schedules}
    assert len(pairs) == len(codes) * (len(codes) - 1)
    assert len({s["flight_number"] for s in schedules}) == len(schedules)


def test_ultra_long_haul_has_a_stop():
    lhr_syd = [s for s in generate_schedules() if s["origin"] == "LHR" and s["destination"] == "SYD"]
    assert lhr_syd and all(s["stops"] == 1 and s["via"] for s in lhr_syd)


def test_search_flights_sorted_and_priced(db):
    p = LocalInventoryProvider(db)
    offers = p.search_flights("LHR", "CDG", future(30), adults=2, children=1)
    assert offers
    assert offers == sorted(offers, key=lambda o: (o.total_price, o.duration_minutes))
    o = offers[0]
    assert o.origin == "LHR" and o.destination == "CDG" and o.origin_city == "London"
    assert o.total_price == pytest.approx(o.price_per_adult * 2 + o.price_per_adult * 0.75, abs=0.02)
    assert o.segments and o.segments[0].origin == "LHR"


def test_business_costs_more_than_economy(db):
    p = LocalInventoryProvider(db)
    d = future(45)
    eco = {o.flight_number: o.total_price for o in p.search_flights("JFK", "LAX", d)}
    biz = {o.flight_number: o.total_price for o in p.search_flights("JFK", "LAX", d, cabin_class="business")}
    assert eco and set(eco) == set(biz)
    assert all(biz[k] > eco[k] * 3 for k in eco)


def test_short_haul_has_no_premium_economy(db):
    assert LocalInventoryProvider(db).search_flights("LHR", "CDG", future(30), cabin_class="premium_economy") == []


def test_flight_offer_roundtrip(db):
    p = LocalInventoryProvider(db)
    offer = p.search_flights("HND", "ICN", future(20))[0]
    again = p.get_flight_offer(offer.id)
    assert again.id == offer.id and again.total_price == offer.total_price


@pytest.mark.parametrize("bad", ["nonsense", "LF.XX1.20300101.economy.1.0", "LF.MR100.notadate.economy.1.0", "LH.CDG01"])
def test_bad_offer_ids(db, bad):
    p = LocalInventoryProvider(db)
    with pytest.raises(OfferNotFound):
        p.get_hotel_offer(bad) if bad.startswith("LH") else p.get_flight_offer(bad)


def test_one_stop_offer_has_two_segments(db):
    offers = LocalInventoryProvider(db).search_flights("LHR", "SYD", future(60))
    assert offers and all(len(o.segments) == 2 and o.segments[0].destination == o.via for o in offers)


def test_unknown_airport_and_past_date(db):
    p = LocalInventoryProvider(db)
    with pytest.raises(ProviderError):
        p.search_flights("XXX", "CDG", future(10))
    with pytest.raises(ProviderError):
        p.search_flights("LHR", "CDG", date.today() - timedelta(days=1))


def test_search_hotels_filters(db):
    p = LocalInventoryProvider(db)
    ci, co = future(30), future(33)
    offers = p.search_hotels("FCO", ci, co, guests=2, min_stars=4)
    assert offers and all(o.stars >= 4 and o.nights == 3 and o.city == "Rome" for o in offers)
    assert all(o.total_price == pytest.approx(o.nightly_rate * 3, abs=0.02) for o in offers)
    cheap = p.search_hotels("FCO", ci, co, guests=2, max_nightly_rate=120)
    assert all(o.nightly_rate <= 120 for o in cheap)


def test_family_gets_family_room(db):
    offers = LocalInventoryProvider(db).search_hotels("BCN", future(30), future(32), guests=4, rooms=rooms_needed(4))
    assert offers and all(o.room_type == "FAM" for o in offers)


def test_hotel_validation(db):
    p = LocalInventoryProvider(db)
    with pytest.raises(ProviderError):
        p.search_hotels("CDG", future(10), future(10))
    with pytest.raises(ProviderError):
        p.search_hotels("CDG", future(10), future(12), guests=9, rooms=2)
