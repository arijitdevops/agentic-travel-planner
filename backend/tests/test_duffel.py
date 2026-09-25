from datetime import timedelta

import httpx
import pytest

from app.models import OfferSnapshot, utcnow
from app.providers import OfferNotFound, ProviderError
from app.providers.duffel import DuffelFlightProvider, parse_iso_duration
from tests.conftest import future

SAMPLE = {
    "data": {
        "offers": [
            {
                "id": "off_0000Test1",
                "total_amount": "412.30",
                "total_currency": "GBP",
                "owner": {"name": "Duffel Airways", "iata_code": "ZZ"},
                "conditions": {"refund_before_departure": {"allowed": True}},
                "slices": [
                    {
                        "origin": {"iata_code": "LHR", "city_name": "London"},
                        "destination": {"iata_code": "JFK", "city_name": "New York"},
                        "duration": "PT8H5M",
                        "segments": [
                            {
                                "origin": {"iata_code": "LHR"}, "destination": {"iata_code": "JFK"},
                                "departing_at": "2030-06-01T09:00:00", "arriving_at": "2030-06-01T12:05:00",
                                "duration": "PT8H5M", "marketing_carrier": {"iata_code": "ZZ", "name": "Duffel Airways"},
                                "marketing_carrier_flight_number": "0101", "aircraft": {"name": "Airbus A380"},
                            }
                        ],
                    }
                ],
            }
        ]
    }
}


def _provider(db, handler):
    client = httpx.Client(base_url="https://api.duffel.test", transport=httpx.MockTransport(handler))
    return DuffelFlightProvider(db, access_token="duffel_test_x", client=client)


def test_parse_iso_duration():
    assert parse_iso_duration("PT7H25M") == 445
    assert parse_iso_duration("P1DT2H") == 1560
    assert parse_iso_duration(None) == 0


def test_search_maps_offers_and_snapshots(db):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.read()
        return httpx.Response(201, json=SAMPLE)

    p = _provider(db, handler)
    offers = p.search_flights("LHR", "JFK", future(60), adults=2)
    assert seen["path"] == "/air/offer_requests" and b'"cabin_class":"economy"' in seen["body"].replace(b" ", b"")
    o = offers[0]
    assert (o.id, o.provider, o.airline_name, o.flight_number, o.duration_minutes) == ("off_0000Test1", "duffel", "Duffel Airways", "ZZ0101", 485)
    assert o.total_price == 412.30 and o.currency == "GBP" and o.refundable and o.stops == 0
    assert p.get_flight_offer("off_0000Test1").total_price == 412.30


def test_expired_snapshot_and_http_error(db):
    p = _provider(db, lambda r: httpx.Response(422, json={"errors": [{"message": "bad"}]}))
    with pytest.raises(ProviderError, match="422"):
        p.search_flights("LHR", "JFK", future(60))
    db.merge(OfferSnapshot(id="off_old", kind="flight", provider="duffel", payload={}, expires_at=utcnow() - timedelta(minutes=1)))
    db.commit()
    with pytest.raises(OfferNotFound, match="expired"):
        p.get_flight_offer("off_old")
    with pytest.raises(OfferNotFound):
        p.get_flight_offer("off_missing")
