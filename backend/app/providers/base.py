"""Provider interfaces and the offer models they return."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

CabinClass = Literal["economy", "premium_economy", "business"]


class ProviderError(Exception):
    """Raised when a provider cannot fulfil a request."""


class OfferNotFound(ProviderError):
    pass


class FlightSegment(BaseModel):
    flight_number: str
    airline_code: str
    airline_name: str
    origin: str
    destination: str
    departure: str  # ISO local datetime
    arrival: str  # ISO local datetime
    duration_minutes: int
    aircraft: str | None = None


class FlightOffer(BaseModel):
    id: str
    provider: str
    origin: str
    origin_city: str
    destination: str
    destination_city: str
    departure_date: date
    departure: str
    arrival: str
    duration_minutes: int
    stops: int
    via: str | None = None
    airline_code: str
    airline_name: str
    flight_number: str
    aircraft: str | None = None
    cabin_class: CabinClass
    adults: int
    children: int = 0
    price_per_adult: float
    total_price: float
    currency: str = "USD"
    seats_left: int | None = None
    baggage: str = "1 cabin bag"
    refundable: bool = False
    segments: list[FlightSegment] = Field(default_factory=list)

    @property
    def travelers(self) -> int:
        return self.adults + self.children


class HotelOffer(BaseModel):
    id: str
    provider: str
    hotel_code: str
    name: str
    city_code: str
    city: str
    neighborhood: str
    address: str
    stars: int
    rating: float
    review_count: int
    amenities: list[str]
    description: str
    room_type: str
    room_name: str
    bed: str
    check_in: date
    check_out: date
    nights: int
    rooms: int
    guests: int
    nightly_rate: float
    total_price: float
    currency: str = "USD"
    rooms_left: int | None = None
    free_cancellation: bool = True
    breakfast_included: bool = False


class Location(BaseModel):
    iata: str
    city: str
    airport: str
    country: str
    region: str
    has_hotels: bool = True


class FlightProvider(ABC):
    name: str = "base"

    @abstractmethod
    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        adults: int = 1,
        children: int = 0,
        cabin_class: CabinClass = "economy",
        max_results: int = 10,
    ) -> list[FlightOffer]: ...

    @abstractmethod
    def get_flight_offer(self, offer_id: str) -> FlightOffer:
        """Re-price / re-validate an offer by id. Raises ``OfferNotFound``."""


class HotelProvider(ABC):
    name: str = "base"

    @abstractmethod
    def search_hotels(
        self,
        city_code: str,
        check_in: date,
        check_out: date,
        guests: int = 1,
        rooms: int = 1,
        min_stars: int | None = None,
        max_nightly_rate: float | None = None,
        max_results: int = 10,
    ) -> list[HotelOffer]: ...

    @abstractmethod
    def get_hotel_offer(self, offer_id: str) -> HotelOffer: ...
