"""Travel supply providers.

``get_flight_provider`` / ``get_hotel_provider`` pick an implementation based on
settings. The local mock inventory is always the hotel provider and the default
flight provider; Duffel can be switched on for flights.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.providers.base import (
    FlightOffer,
    FlightProvider,
    HotelOffer,
    HotelProvider,
    OfferNotFound,
    ProviderError,
)
from app.providers.local import LocalInventoryProvider


def get_flight_provider(db: Session, settings: Settings | None = None) -> FlightProvider:
    settings = settings or get_settings()
    if settings.flight_provider == "duffel":
        from app.providers.duffel import DuffelFlightProvider

        return DuffelFlightProvider(
            db,
            access_token=settings.duffel_access_token or "",
            base_url=settings.duffel_base_url,
            ttl_minutes=settings.offer_ttl_minutes,
        )
    return LocalInventoryProvider(db, currency=settings.currency)


def get_hotel_provider(db: Session, settings: Settings | None = None) -> HotelProvider:
    settings = settings or get_settings()
    return LocalInventoryProvider(db, currency=settings.currency)


def provider_for_offer(db: Session, offer_id: str, settings: Settings | None = None) -> tuple[str, FlightProvider | HotelProvider]:
    """Return ``(kind, provider)`` able to resolve ``offer_id``."""
    if offer_id.startswith("LH."):
        return "hotel", get_hotel_provider(db, settings)
    if offer_id.startswith("LF."):
        return "flight", LocalInventoryProvider(db, currency=(settings or get_settings()).currency)
    return "flight", get_flight_provider(db, settings)


__all__ = [
    "FlightOffer",
    "FlightProvider",
    "HotelOffer",
    "HotelProvider",
    "LocalInventoryProvider",
    "OfferNotFound",
    "ProviderError",
    "get_flight_provider",
    "get_hotel_provider",
    "provider_for_offer",
]
