"""Progress events for a trip-planning run, persisted in ``trip_events``.

Stored in the database (not in memory) so that the SSE stream works across
multiple API workers and survives page reloads.
"""

from __future__ import annotations

import threading

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import db as db_module
from app.models import Trip, TripEvent

_lock = threading.Lock()


def emit_event(trip_id: int, agent: str | None, kind: str, message: str, current_step: str | None = None) -> None:
    with _lock, db_module.SessionLocal() as db:
        seq = (db.scalar(select(func.max(TripEvent.seq)).where(TripEvent.trip_id == trip_id)) or 0) + 1
        db.add(TripEvent(trip_id=trip_id, seq=seq, agent=agent, kind=kind, message=message[:2000]))
        if current_step is not None:
            trip = db.get(Trip, trip_id)
            if trip is not None:
                trip.current_step = current_step[:80]
        db.commit()


def events_after(db: Session, trip_id: int, after: int = 0) -> list[TripEvent]:
    return list(
        db.scalars(select(TripEvent).where(TripEvent.trip_id == trip_id, TripEvent.seq > after).order_by(TripEvent.seq)).all()
    )
