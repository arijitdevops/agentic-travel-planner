"""Optional live flight search through the Duffel API (test or live mode).

Enable with ``FLIGHT_PROVIDER=duffel`` and ``DUFFEL_ACCESS_TOKEN``. A test-mode
token (``duffel_test_...``) returns sandbox inventory, so nothing is ever
ticketed. Search results are stored as :class:`~app.models.OfferSnapshot`
rows so they can be booked (simulated) later by id until they expire.

Bookings made in this app are always *simulated*: we never call Duffel's
order-creation endpoint and no payment is taken.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.models import OfferSnapshot, utcnow
from app.providers.base import CabinClass, FlightOffer, FlightProvider, FlightSegment, OfferNotFound, ProviderError

_ISO_DURATION = re.compile(r"P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?)?")


def parse_iso_duration(value: str | None) -> int:
    """``PT7H25M`` -> 445 minutes."""
    if not value:
        return 0
    match = _ISO_DURATION.fullmatch(value)
    if not match:
        return 0
    d, h, m = (int(match.group(k) or 0) for k in ("d", "h", "m"))
    return d * 1440 + h * 60 + m


def _minutes_between(a: str, b: str) -> int:
    try:
        return int((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() // 60)
    except ValueError:
        return 0


class DuffelFlightProvider(FlightProvider):
    name = "duffel"

    def __init__(
        self,
        db: Session,
        access_token: str,
        base_url: str = "https://api.duffel.com",
        ttl_minutes: int = 30,
        client: httpx.Client | None = None,
    ) -> None:
        if not access_token:
            raise ProviderError("DUFFEL_ACCESS_TOKEN is not configured")
        self.db = db
        self.ttl = timedelta(minutes=ttl_minutes)
        self.client = client or httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(45.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Duffel-Version": "v2",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def _to_offer(self, raw: dict, adults: int, children: int, cabin: CabinClass, day: date) -> FlightOffer | None:
        slices = raw.get("slices") or []
        if not slices:
            return None
        first = slices[0]
        segs_raw = first.get("segments") or []
        if not segs_raw:
            return None
        segments = []
        for s in segs_raw:
            carrier = s.get("marketing_carrier") or s.get("operating_carrier") or {}
            code = carrier.get("iata_code") or "??"
            segments.append(
                FlightSegment(
                    flight_number=f"{code}{s.get('marketing_carrier_flight_number') or ''}",
                    airline_code=code,
                    airline_name=carrier.get("name") or code,
                    origin=(s.get("origin") or {}).get("iata_code", ""),
                    destination=(s.get("destination") or {}).get("iata_code", ""),
                    departure=s.get("departing_at", ""),
                    arrival=s.get("arriving_at", ""),
                    duration_minutes=parse_iso_duration(s.get("duration"))
                    or _minutes_between(s.get("departing_at", ""), s.get("arriving_at", "")),
                    aircraft=(s.get("aircraft") or {}).get("name"),
                )
            )
        owner = raw.get("owner") or {}
        total = float(raw.get("total_amount") or 0)
        pax = adults + children * 0.75
        origin = first.get("origin") or {}
        dest = first.get("destination") or {}
        return FlightOffer(
            id=str(raw["id"]),
            provider=self.name,
            origin=origin.get("iata_code", segments[0].origin),
            origin_city=origin.get("city_name") or origin.get("name") or segments[0].origin,
            destination=dest.get("iata_code", segments[-1].destination),
            destination_city=dest.get("city_name") or dest.get("name") or segments[-1].destination,
            departure_date=day,
            departure=segments[0].departure,
            arrival=segments[-1].arrival,
            duration_minutes=parse_iso_duration(first.get("duration"))
            or _minutes_between(segments[0].departure, segments[-1].arrival),
            stops=len(segments) - 1,
            via=segments[0].destination if len(segments) > 1 else None,
            airline_code=owner.get("iata_code") or segments[0].airline_code,
            airline_name=owner.get("name") or segments[0].airline_name,
            flight_number=segments[0].flight_number,
            aircraft=segments[0].aircraft,
            cabin_class=cabin,
            adults=adults,
            children=children,
            price_per_adult=round(total / pax, 2) if pax else total,
            total_price=round(total, 2),
            currency=raw.get("total_currency") or "USD",
            seats_left=None,
            baggage="See airline conditions",
            refundable=bool(((raw.get("conditions") or {}).get("refund_before_departure") or {}).get("allowed")),
            segments=segments,
        )

    def search_flights(self, origin, destination, departure_date, adults=1, children=0, cabin_class="economy", max_results=10):
        passengers = [{"type": "adult"}] * adults + [{"age": 8}] * children
        body = {
            "data": {
                "slices": [{"origin": origin.upper(), "destination": destination.upper(), "departure_date": departure_date.isoformat()}],
                "passengers": passengers,
                "cabin_class": cabin_class,
                "max_connections": 1,
            }
        }
        try:
            resp = self.client.post("/air/offer_requests", params={"return_offers": "true", "supplier_timeout": 20000}, json=body)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Duffel request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise ProviderError(f"Duffel returned HTTP {resp.status_code}: {resp.text[:300]}")
        raw_offers = (resp.json().get("data") or {}).get("offers") or []
        offers = [o for raw in raw_offers if (o := self._to_offer(raw, adults, children, cabin_class, departure_date))]
        offers.sort(key=lambda o: (o.total_price, o.duration_minutes))
        offers = offers[:max_results]
        expires = utcnow() + self.ttl
        for offer in offers:
            self.db.merge(OfferSnapshot(id=offer.id, kind="flight", provider=self.name,
                                        payload=offer.model_dump(mode="json"), expires_at=expires))
        self.db.commit()
        return offers

    def get_flight_offer(self, offer_id: str) -> FlightOffer:
        snap = self.db.get(OfferSnapshot, offer_id)
        if snap is None or snap.provider != self.name:
            raise OfferNotFound(f"Flight offer '{offer_id}' not found - search again")
        if snap.expires_at < utcnow():
            raise OfferNotFound("This fare has expired - please search again for a fresh price")
        return FlightOffer.model_validate(snap.payload)
