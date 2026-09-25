"""ORM models.

Two groups of tables live here:

* **Inventory** (``airports``, ``airlines``, ``flight_schedules``, ``hotels``) -
  the local mock supply that the default provider searches. Seeded by
  ``python -m app.seed``.
* **Application data** (``users``, ``trips``, ``trip_events``, ``trip_messages``,
  ``bookings``, ``booking_travelers``, ``offer_snapshots``).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
class Airport(Base):
    __tablename__ = "airports"

    iata: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80), index=True)
    country: Mapped[str] = mapped_column(String(80))
    country_code: Mapped[str] = mapped_column(String(2))
    region: Mapped[str] = mapped_column(String(40))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(3))
    language: Mapped[str] = mapped_column(String(60))
    cost_index: Mapped[float] = mapped_column(Float, default=1.0)
    neighborhoods: Mapped[list[str]] = mapped_column(JSON, default=list)


class Airline(Base):
    __tablename__ = "airlines"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    hub: Mapped[str] = mapped_column(String(3))
    rating: Mapped[float] = mapped_column(Float, default=4.0)


class FlightSchedule(Base):
    __tablename__ = "flight_schedules"
    __table_args__ = (Index("ix_schedule_route", "origin", "destination"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_number: Mapped[str] = mapped_column(String(8), unique=True)
    airline_code: Mapped[str] = mapped_column(ForeignKey("airlines.code"))
    origin: Mapped[str] = mapped_column(ForeignKey("airports.iata"))
    destination: Mapped[str] = mapped_column(ForeignKey("airports.iata"))
    departure_time: Mapped[str] = mapped_column(String(5))  # local HH:MM
    duration_minutes: Mapped[int] = mapped_column(Integer)
    stops: Mapped[int] = mapped_column(Integer, default=0)
    via: Mapped[str | None] = mapped_column(String(3), nullable=True)
    aircraft: Mapped[str] = mapped_column(String(40))
    days_of_week: Mapped[str] = mapped_column(String(7), default="1234567")  # ISO weekdays
    base_fare: Mapped[float] = mapped_column(Numeric(10, 2))
    seats_economy: Mapped[int] = mapped_column(Integer)
    seats_premium_economy: Mapped[int] = mapped_column(Integer)
    seats_business: Mapped[int] = mapped_column(Integer)

    airline: Mapped[Airline] = relationship(lazy="joined")


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    city_code: Mapped[str] = mapped_column(ForeignKey("airports.iata"), index=True)
    neighborhood: Mapped[str] = mapped_column(String(80))
    address: Mapped[str] = mapped_column(String(200))
    stars: Mapped[int] = mapped_column(Integer)
    rating: Mapped[float] = mapped_column(Float)
    review_count: Mapped[int] = mapped_column(Integer)
    base_rate: Mapped[float] = mapped_column(Numeric(10, 2))
    amenities: Mapped[list[str]] = mapped_column(JSON, default=list)
    room_types: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text)
    free_cancellation: Mapped[bool] = mapped_column(Boolean, default=True)
    breakfast_included: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------------------
# Application data
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(190), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    origin: Mapped[str] = mapped_column(String(3))
    destinations: Mapped[list[str]] = mapped_column(JSON)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    adults: Mapped[int] = mapped_column(Integer, default=1)
    children: Mapped[int] = mapped_column(Integer, default=0)
    budget: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    cabin_class: Mapped[str] = mapped_column(String(20), default="economy")
    hotel_min_stars: Mapped[int] = mapped_column(Integer, default=3)
    pace: Mapped[str] = mapped_column(String(20), default="balanced")
    travel_style: Mapped[str] = mapped_column(String(30), default="comfort")
    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    dietary_needs: Mapped[str | None] = mapped_column(String(300), nullable=True)
    accessibility_needs: Mapped[str | None] = mapped_column(String(300), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    current_step: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    plan_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    events: Mapped[list[TripEvent]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", order_by="TripEvent.seq"
    )
    messages: Mapped[list[TripMessage]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", order_by="TripMessage.id"
    )


class TripEvent(Base):
    __tablename__ = "trip_events"
    __table_args__ = (UniqueConstraint("trip_id", "seq", name="uq_trip_event_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    agent: Mapped[str | None] = mapped_column(String(60), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    trip: Mapped[Trip] = relationship(back_populates="events")


class TripMessage(Base):
    __tablename__ = "trip_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    changes: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    trip: Mapped[Trip] = relationship(back_populates="messages")


class OfferSnapshot(Base):
    """Price-locked copy of an offer from a remote provider (e.g. Duffel)."""

    __tablename__ = "offer_snapshots"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    provider: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        Index("ix_booking_flight_inventory", "flight_number", "travel_date", "cabin_class", "status"),
        Index("ix_booking_hotel_inventory", "hotel_code", "room_type", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(String(12), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(10))  # flight | hotel
    provider: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    offer_id: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(String(255))
    details: Mapped[dict[str, Any]] = mapped_column(JSON)
    total_price: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    refund_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(190))
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # inventory keys (flights)
    flight_number: Mapped[str | None] = mapped_column(String(8), nullable=True)
    travel_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cabin_class: Mapped[str | None] = mapped_column(String(20), nullable=True)
    seats: Mapped[int] = mapped_column(Integer, default=0)
    # inventory keys (hotels)
    hotel_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    room_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    check_in: Mapped[date | None] = mapped_column(Date, nullable=True)
    check_out: Mapped[date | None] = mapped_column(Date, nullable=True)
    rooms: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    travelers: Mapped[list[BookingTraveler]] = relationship(
        back_populates="booking", cascade="all, delete-orphan", order_by="BookingTraveler.id"
    )


class BookingTraveler(Base):
    __tablename__ = "booking_travelers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    traveler_type: Mapped[str] = mapped_column(String(10), default="adult")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    ticket_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    booking: Mapped[Booking] = relationship(back_populates="travelers")
