"""Simulated booking engine.

Bookings are real rows with real inventory effects (seats and rooms are
consumed and released), but **no payment is taken and nothing is ticketed
with a real airline or hotel**.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, BookingTraveler, FlightSchedule, Hotel, Trip, User, utcnow
from app.providers import FlightOffer, HotelOffer, OfferNotFound, ProviderError, provider_for_offer
from app.schemas import BookingCreate

PNR_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


class BookingError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _new_reference(db: Session, prefix: str = "") -> str:
    for _ in range(20):
        ref = prefix + "".join(secrets.choice(PNR_ALPHABET) for _ in range(6))
        if db.scalar(select(Booking.id).where(Booking.reference == ref)) is None:
            return ref
    raise BookingError("Could not allocate a booking reference", 500)  # pragma: no cover


def _ticket_number() -> str:
    return "999-" + "".join(secrets.choice("0123456789") for _ in range(10))


def _lock_inventory(db: Session, offer_id: str) -> None:
    """Serialise concurrent bookings on the same flight/hotel (MySQL row lock)."""
    parts = offer_id.split(".")
    if offer_id.startswith("LF.") and len(parts) > 1:
        db.execute(select(FlightSchedule.id).where(FlightSchedule.flight_number == parts[1]).with_for_update())
    elif offer_id.startswith("LH.") and len(parts) > 1:
        db.execute(select(Hotel.id).where(Hotel.code == parts[1]).with_for_update())


def create_booking(db: Session, user: User, payload: BookingCreate) -> Booking:
    if payload.trip_id is not None:
        trip = db.get(Trip, payload.trip_id)
        if trip is None or trip.user_id != user.id:
            raise BookingError("Trip not found", 404)

    _lock_inventory(db, payload.offer_id)
    kind, provider = provider_for_offer(db, payload.offer_id)
    try:
        offer = provider.get_flight_offer(payload.offer_id) if kind == "flight" else provider.get_hotel_offer(payload.offer_id)  # type: ignore[union-attr]
    except OfferNotFound as exc:
        raise BookingError(str(exc), 409) from exc
    except ProviderError as exc:
        raise BookingError(str(exc), 502) from exc

    adults = sum(1 for t in payload.travelers if t.traveler_type == "adult")
    children = len(payload.travelers) - adults

    booking = Booking(
        reference="",
        user_id=user.id,
        trip_id=payload.trip_id,
        kind=kind,
        provider=offer.provider,
        status="confirmed",
        offer_id=offer.id,
        details=offer.model_dump(mode="json"),
        total_price=offer.total_price,
        currency=offer.currency,
        contact_email=str(payload.contact_email),
        contact_phone=payload.contact_phone,
    )

    if isinstance(offer, FlightOffer):
        if (adults, children) != (offer.adults, offer.children):
            raise BookingError(
                f"This fare is for {offer.adults} adult(s) and {offer.children} child(ren); "
                f"got {adults} adult(s) and {children} child(ren)"
            )
        booking.reference = _new_reference(db)
        booking.flight_number = offer.flight_number
        booking.travel_date = offer.departure_date
        booking.cabin_class = offer.cabin_class
        booking.seats = offer.travelers
        dep = datetime.fromisoformat(offer.departure)
        booking.summary = (
            f"{offer.airline_name} {offer.flight_number} {offer.origin}->{offer.destination} "
            f"{dep:%d %b %Y %H:%M}, {offer.travelers} pax"
        )
    else:
        assert isinstance(offer, HotelOffer)
        if len(payload.travelers) != offer.guests:
            raise BookingError(f"This rate is for {offer.guests} guest(s); got {len(payload.travelers)}")
        booking.reference = _new_reference(db, prefix="H")
        booking.hotel_code = offer.hotel_code
        booking.room_type = offer.room_type
        booking.check_in = offer.check_in
        booking.check_out = offer.check_out
        booking.rooms = offer.rooms
        booking.summary = (
            f"{offer.name}, {offer.city} - {offer.rooms} x {offer.room_name}, "
            f"{offer.check_in:%d %b} to {offer.check_out:%d %b %Y}"
        )

    for t in payload.travelers:
        booking.travelers.append(
            BookingTraveler(
                first_name=t.first_name.strip(),
                last_name=t.last_name.strip(),
                traveler_type=t.traveler_type,
                date_of_birth=t.date_of_birth,
                ticket_number=_ticket_number() if kind == "flight" else None,
            )
        )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def refund_for(booking: Booking, now: datetime | None = None) -> float:
    """Refund policy (simulated).

    * Flights: full refund within 24h of booking; afterwards business 100%,
      premium economy 50%, economy 0% (taxes are not modelled).
    * Hotels: full refund if the rate has free cancellation and check-in is
      more than 48h away; otherwise the first night is charged.
    """
    now = now or utcnow()
    total = float(booking.total_price)
    if booking.kind == "flight":
        if now - booking.created_at <= timedelta(hours=24):
            return total
        return round(total * {"business": 1.0, "premium_economy": 0.5}.get(booking.cabin_class or "", 0.0), 2)
    details = booking.details or {}
    assert booking.check_in is not None
    check_in_at = datetime.combine(booking.check_in, datetime.min.time()) + timedelta(hours=15)
    if details.get("free_cancellation") and check_in_at - now > timedelta(hours=48):
        return total
    first_night = float(details.get("nightly_rate", 0)) * int(details.get("rooms", 1))
    return round(max(0.0, total - first_night), 2)


def cancel_booking(db: Session, booking: Booking) -> Booking:
    if booking.status == "cancelled":
        raise BookingError("Booking is already cancelled", 409)
    booking.refund_amount = refund_for(booking)
    booking.status = "cancelled"
    booking.cancelled_at = utcnow()
    db.commit()
    db.refresh(booking)
    return booking
