"""Location lookup plus direct flight and hotel search (no AI involved)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.providers import (
    FlightOffer,
    HotelOffer,
    OfferNotFound,
    ProviderError,
    get_flight_provider,
    get_hotel_provider,
    provider_for_offer,
)
from app.providers.base import CabinClass, Location
from app.providers.local import list_locations

router = APIRouter(tags=["inventory"])


@router.get("/locations", response_model=list[Location])
def locations(q: str | None = Query(default=None, max_length=60), db: Session = Depends(get_db)) -> list[Location]:
    return list_locations(db, q)


@router.get("/flights/search", response_model=list[FlightOffer])
def search_flights(
    origin: str = Query(min_length=3, max_length=3),
    destination: str = Query(min_length=3, max_length=3),
    departure_date: date = Query(),
    adults: int = Query(default=1, ge=1, le=9),
    children: int = Query(default=0, ge=0, le=8),
    cabin_class: CabinClass = Query(default="economy"),
    max_results: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[FlightOffer]:
    try:
        return get_flight_provider(db).search_flights(origin, destination, departure_date, adults, children, cabin_class, max_results)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/flights/offers/{offer_id}", response_model=FlightOffer)
def get_flight_offer(offer_id: str, db: Session = Depends(get_db)) -> FlightOffer:
    kind, provider = provider_for_offer(db, offer_id)
    if kind != "flight":
        raise HTTPException(status_code=404, detail="Not a flight offer")
    try:
        return provider.get_flight_offer(offer_id)  # type: ignore[union-attr]
    except OfferNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/hotels/search", response_model=list[HotelOffer])
def search_hotels(
    city: str = Query(min_length=3, max_length=3, description="City IATA code"),
    check_in: date = Query(),
    check_out: date = Query(),
    guests: int = Query(default=1, ge=1, le=16),
    rooms: int = Query(default=1, ge=1, le=8),
    min_stars: int | None = Query(default=None, ge=2, le=5),
    max_nightly_rate: float | None = Query(default=None, gt=0),
    max_results: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[HotelOffer]:
    try:
        return get_hotel_provider(db).search_hotels(city, check_in, check_out, guests, rooms, min_stars, max_nightly_rate, max_results)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/hotels/offers/{offer_id}", response_model=HotelOffer)
def get_hotel_offer(offer_id: str, db: Session = Depends(get_db)) -> HotelOffer:
    kind, provider = provider_for_offer(db, offer_id)
    if kind != "hotel":
        raise HTTPException(status_code=404, detail="Not a hotel offer")
    try:
        return provider.get_hotel_offer(offer_id)  # type: ignore[union-attr]
    except OfferNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
