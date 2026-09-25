"""Local mock inventory provider (default).

Searches the seeded ``flight_schedules`` / ``hotels`` tables and prices offers
with a deterministic model (distance, cabin, season, weekday, advance purchase,
load factor). Availability is real: confirmed bookings consume seats and rooms.
Offer ids encode everything needed to re-price, so they never expire.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Airport, Booking, FlightSchedule, Hotel
from app.providers.base import (
    CabinClass,
    FlightOffer,
    FlightProvider,
    FlightSegment,
    HotelOffer,
    HotelProvider,
    Location,
    OfferNotFound,
    ProviderError,
)
from app.providers.mock_data import (
    CABIN_MULTIPLIER,
    CHILD_FARE_FACTOR,
    advance_purchase_factor,
    seasonal_factor,
    stable_unit,
    weekday_factor,
)

CABIN_SEAT_COLUMN = {
    "economy": "seats_economy",
    "premium_economy": "seats_premium_economy",
    "business": "seats_business",
}


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _baggage(cabin: str, duration: int) -> str:
    if cabin == "business":
        return "2 checked bags (32 kg) + lounge access"
    if cabin == "premium_economy":
        return "2 checked bags (23 kg)"
    return "1 cabin bag + 1 checked bag (23 kg)" if duration > 300 else "1 cabin bag (checked bag extra)"


class LocalInventoryProvider(FlightProvider, HotelProvider):
    name = "local"

    def __init__(self, db: Session, today: date | None = None, currency: str = "USD") -> None:
        self.db = db
        self.today = today or _utc_today()
        self.currency = currency

    # ------------------------------------------------------------------ helpers
    def _airport(self, iata: str) -> Airport:
        airport = self.db.get(Airport, iata.upper())
        if airport is None:
            raise ProviderError(f"Unknown airport/city code '{iata}'")
        return airport

    def booked_seats(self, flight_number: str, travel_date: date, cabin: str) -> int:
        stmt = select(func.coalesce(func.sum(Booking.seats), 0)).where(
            Booking.flight_number == flight_number,
            Booking.travel_date == travel_date,
            Booking.cabin_class == cabin,
            Booking.status == "confirmed",
        )
        return int(self.db.scalar(stmt) or 0)

    def booked_rooms(self, hotel_code: str, room_type: str, check_in: date, check_out: date) -> int:
        stmt = select(func.coalesce(func.sum(Booking.rooms), 0)).where(
            Booking.hotel_code == hotel_code,
            Booking.room_type == room_type,
            Booking.status == "confirmed",
            Booking.check_in < check_out,
            Booking.check_out > check_in,
        )
        return int(self.db.scalar(stmt) or 0)

    # ------------------------------------------------------------------ flights
    def _price_flight(self, sched: FlightSchedule, day: date, cabin: str, load: float) -> float:
        days_ahead = (day - self.today).days
        price = (
            float(sched.base_fare)
            * CABIN_MULTIPLIER[cabin]
            * seasonal_factor(day)
            * weekday_factor(day)
            * advance_purchase_factor(days_ahead)
            * (0.93 + 0.14 * stable_unit(sched.flight_number, day.isoformat()))
            * (1 + 0.25 * load)
        )
        return round(price, 2)

    def _build_flight_offer(
        self, sched: FlightSchedule, day: date, cabin: CabinClass, adults: int, children: int
    ) -> FlightOffer | None:
        capacity = getattr(sched, CABIN_SEAT_COLUMN[cabin])
        if capacity <= 0:
            return None
        booked = self.booked_seats(sched.flight_number, day, cabin)
        seats_left = capacity - booked
        if seats_left < adults + children:
            return None
        per_adult = self._price_flight(sched, day, cabin, booked / capacity)
        total = round(per_adult * adults + per_adult * CHILD_FARE_FACTOR * children, 2)

        origin = self._airport(sched.origin)
        dest = self._airport(sched.destination)
        hh, mm = (int(x) for x in sched.departure_time.split(":"))
        dep_local = datetime(day.year, day.month, day.day, hh, mm, tzinfo=ZoneInfo(origin.timezone))
        arr_local = (dep_local + timedelta(minutes=sched.duration_minutes)).astimezone(ZoneInfo(dest.timezone))

        segments: list[FlightSegment] = []
        if sched.stops and sched.via:
            via = self._airport(sched.via)
            first = int(sched.duration_minutes * 0.45)
            layover = 95
            mid_arr = (dep_local + timedelta(minutes=first)).astimezone(ZoneInfo(via.timezone))
            mid_dep = mid_arr + timedelta(minutes=layover)
            second_no = f"{sched.airline_code}{int(sched.flight_number[len(sched.airline_code):]) + 500}"
            segments = [
                FlightSegment(flight_number=sched.flight_number, airline_code=sched.airline_code, airline_name=sched.airline.name,
                              origin=origin.iata, destination=via.iata, departure=dep_local.replace(tzinfo=None).isoformat(),
                              arrival=mid_arr.replace(tzinfo=None).isoformat(), duration_minutes=first, aircraft=sched.aircraft),
                FlightSegment(flight_number=second_no, airline_code=sched.airline_code, airline_name=sched.airline.name,
                              origin=via.iata, destination=dest.iata, departure=mid_dep.replace(tzinfo=None).isoformat(),
                              arrival=arr_local.replace(tzinfo=None).isoformat(),
                              duration_minutes=sched.duration_minutes - first - layover, aircraft=sched.aircraft),
            ]
        else:
            segments = [
                FlightSegment(flight_number=sched.flight_number, airline_code=sched.airline_code, airline_name=sched.airline.name,
                              origin=origin.iata, destination=dest.iata, departure=dep_local.replace(tzinfo=None).isoformat(),
                              arrival=arr_local.replace(tzinfo=None).isoformat(), duration_minutes=sched.duration_minutes,
                              aircraft=sched.aircraft)
            ]

        return FlightOffer(
            id=f"LF.{sched.flight_number}.{day:%Y%m%d}.{cabin}.{adults}.{children}",
            provider=self.name,
            origin=origin.iata,
            origin_city=origin.city,
            destination=dest.iata,
            destination_city=dest.city,
            departure_date=day,
            departure=dep_local.replace(tzinfo=None).isoformat(),
            arrival=arr_local.replace(tzinfo=None).isoformat(),
            duration_minutes=sched.duration_minutes,
            stops=sched.stops,
            via=sched.via,
            airline_code=sched.airline_code,
            airline_name=sched.airline.name,
            flight_number=sched.flight_number,
            aircraft=sched.aircraft,
            cabin_class=cabin,
            adults=adults,
            children=children,
            price_per_adult=per_adult,
            total_price=total,
            currency=self.currency,
            seats_left=seats_left,
            baggage=_baggage(cabin, sched.duration_minutes),
            refundable=cabin == "business",
            segments=segments,
        )

    def search_flights(self, origin, destination, departure_date, adults=1, children=0, cabin_class="economy", max_results=10):
        if adults < 1:
            raise ProviderError("At least one adult is required")
        if departure_date < self.today:
            raise ProviderError("Departure date is in the past")
        if cabin_class not in CABIN_MULTIPLIER:
            raise ProviderError(f"Unsupported cabin class '{cabin_class}'")
        self._airport(origin)
        self._airport(destination)
        weekday = str(departure_date.isoweekday())
        schedules = self.db.scalars(
            select(FlightSchedule).where(
                FlightSchedule.origin == origin.upper(), FlightSchedule.destination == destination.upper()
            )
        ).all()
        offers = [
            offer
            for sched in schedules
            if weekday in sched.days_of_week
            and (offer := self._build_flight_offer(sched, departure_date, cabin_class, adults, children)) is not None
        ]
        offers.sort(key=lambda o: (o.total_price, o.duration_minutes))
        return offers[:max_results]

    def get_flight_offer(self, offer_id: str) -> FlightOffer:
        try:
            prefix, flight_number, day_s, cabin, adults_s, children_s = offer_id.split(".")
            if prefix != "LF":
                raise ValueError
            day = datetime.strptime(day_s, "%Y%m%d").date()
            adults, children = int(adults_s), int(children_s)
        except ValueError as exc:
            raise OfferNotFound(f"Malformed flight offer id '{offer_id}'") from exc
        sched = self.db.scalar(select(FlightSchedule).where(FlightSchedule.flight_number == flight_number))
        if sched is None or cabin not in CABIN_MULTIPLIER or str(day.isoweekday()) not in sched.days_of_week:
            raise OfferNotFound(f"Flight offer '{offer_id}' does not exist")
        if day < self.today:
            raise OfferNotFound("This flight has already departed")
        offer = self._build_flight_offer(sched, day, cabin, adults, children)  # type: ignore[arg-type]
        if offer is None:
            raise OfferNotFound("Not enough seats left on this flight")
        return offer

    # ------------------------------------------------------------------- hotels
    def _nightly_rate(self, hotel: Hotel, room: dict, check_in: date, nights: int, occupancy: float) -> float:
        factors = []
        for n in range(nights):
            d = check_in + timedelta(days=n)
            weekend = 1.15 if d.weekday() in (4, 5) else 1.0
            factors.append(seasonal_factor(d) * weekend)
        avg = sum(factors) / len(factors)
        rate = (
            float(hotel.base_rate)
            * float(room["multiplier"])
            * avg
            * (0.94 + 0.12 * stable_unit(hotel.code, check_in.isoformat()))
            * (1 + 0.2 * occupancy)
        )
        return round(rate, 2)

    def _build_hotel_offer(self, hotel: Hotel, room: dict, check_in: date, check_out: date, rooms: int, guests: int) -> HotelOffer | None:
        if math.ceil(guests / rooms) > room["max_guests"]:
            return None
        booked = self.booked_rooms(hotel.code, room["code"], check_in, check_out)
        left = int(room["count"]) - booked
        if left < rooms:
            return None
        nights = (check_out - check_in).days
        nightly = self._nightly_rate(hotel, room, check_in, nights, booked / int(room["count"]))
        city = self._airport(hotel.city_code)
        return HotelOffer(
            id=f"LH.{hotel.code}.{room['code']}.{check_in:%Y%m%d}.{check_out:%Y%m%d}.{rooms}.{guests}",
            provider=self.name,
            hotel_code=hotel.code,
            name=hotel.name,
            city_code=hotel.city_code,
            city=city.city,
            neighborhood=hotel.neighborhood,
            address=hotel.address,
            stars=hotel.stars,
            rating=hotel.rating,
            review_count=hotel.review_count,
            amenities=list(hotel.amenities),
            description=hotel.description,
            room_type=room["code"],
            room_name=room["name"],
            bed=room.get("bed", ""),
            check_in=check_in,
            check_out=check_out,
            nights=nights,
            rooms=rooms,
            guests=guests,
            nightly_rate=nightly,
            total_price=round(nightly * nights * rooms, 2),
            currency=self.currency,
            rooms_left=left,
            free_cancellation=hotel.free_cancellation,
            breakfast_included=hotel.breakfast_included,
        )

    @staticmethod
    def _validate_stay(check_in: date, check_out: date, guests: int, rooms: int) -> None:
        if check_out <= check_in:
            raise ProviderError("check_out must be after check_in")
        if (check_out - check_in).days > 30:
            raise ProviderError("Stays longer than 30 nights are not supported")
        if rooms < 1 or guests < 1:
            raise ProviderError("guests and rooms must be at least 1")
        if guests > rooms * 4:
            raise ProviderError("Too many guests for the number of rooms (max 4 per room)")

    def search_hotels(self, city_code, check_in, check_out, guests=1, rooms=1, min_stars=None, max_nightly_rate=None, max_results=10):
        self._validate_stay(check_in, check_out, guests, rooms)
        if check_in < self.today:
            raise ProviderError("Check-in date is in the past")
        self._airport(city_code)
        stmt = select(Hotel).where(Hotel.city_code == city_code.upper())
        if min_stars:
            stmt = stmt.where(Hotel.stars >= min_stars)
        offers: list[HotelOffer] = []
        for hotel in self.db.scalars(stmt).all():
            # Smallest room type that fits the party.
            for room in sorted(hotel.room_types, key=lambda r: r["multiplier"]):
                offer = self._build_hotel_offer(hotel, room, check_in, check_out, rooms, guests)
                if offer is not None:
                    if max_nightly_rate is None or offer.nightly_rate * rooms <= max_nightly_rate:
                        offers.append(offer)
                    break
        offers.sort(key=lambda o: (-o.rating, o.total_price))
        return offers[:max_results]

    def get_hotel_offer(self, offer_id: str) -> HotelOffer:
        try:
            prefix, code, room_code, ci, co, rooms_s, guests_s = offer_id.split(".")
            if prefix != "LH":
                raise ValueError
            check_in = datetime.strptime(ci, "%Y%m%d").date()
            check_out = datetime.strptime(co, "%Y%m%d").date()
            rooms, guests = int(rooms_s), int(guests_s)
            self._validate_stay(check_in, check_out, guests, rooms)
        except (ValueError, ProviderError) as exc:
            raise OfferNotFound(f"Malformed hotel offer id '{offer_id}'") from exc
        hotel = self.db.scalar(select(Hotel).where(Hotel.code == code))
        room = next((r for r in (hotel.room_types if hotel else []) if r["code"] == room_code), None)
        if hotel is None or room is None:
            raise OfferNotFound(f"Hotel offer '{offer_id}' does not exist")
        if check_in < self.today:
            raise OfferNotFound("Check-in date is in the past")
        offer = self._build_hotel_offer(hotel, room, check_in, check_out, rooms, guests)
        if offer is None:
            raise OfferNotFound("This room type is no longer available for those dates")
        return offer


def list_locations(db: Session, query: str | None = None, limit: int = 50) -> list[Location]:
    stmt = select(Airport).order_by(Airport.city)
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(or_(Airport.city.ilike(like), Airport.iata.ilike(like), Airport.country.ilike(like)))
    with_hotels = set(db.scalars(select(Hotel.city_code).distinct()).all())
    return [
        Location(iata=a.iata, city=a.city, airport=a.name, country=a.country, region=a.region, has_hotels=a.iata in with_hotels)
        for a in db.scalars(stmt.limit(limit)).all()
    ]
