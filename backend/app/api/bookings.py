"""Simulated bookings. No payment is taken; nothing is ticketed for real."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import Booking, User
from app.schemas import BookingCreate, BookingOut
from app.services.booking import BookingError, cancel_booking, create_booking

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _get_owned(db: Session, user: User, reference: str) -> Booking:
    booking = db.scalar(select(Booking).where(Booking.reference == reference.upper(), Booking.user_id == user.id))
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("", response_model=BookingOut, status_code=201)
def book(payload: BookingCreate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Booking:
    try:
        return create_booking(db, user, payload)
    except BookingError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("", response_model=list[BookingOut])
def list_bookings(
    status: str | None = Query(default=None, pattern="^(confirmed|cancelled)$"),
    trip_id: int | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[Booking]:
    stmt = select(Booking).where(Booking.user_id == user.id).order_by(Booking.created_at.desc(), Booking.id.desc())
    if status:
        stmt = stmt.where(Booking.status == status)
    if trip_id is not None:
        stmt = stmt.where(Booking.trip_id == trip_id)
    return list(db.scalars(stmt).all())


@router.get("/{reference}", response_model=BookingOut)
def get_booking(reference: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Booking:
    return _get_owned(db, user, reference)


@router.post("/{reference}/cancel", response_model=BookingOut)
def cancel(reference: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Booking:
    booking = _get_owned(db, user, reference)
    try:
        return cancel_booking(db, booking)
    except BookingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
