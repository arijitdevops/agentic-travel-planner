"""Trip planning: create a plan (background multi-agent job), follow its progress
(polling or Server-Sent Events), refine it by chat, list and delete trips."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db as db_module
from app.agents.llm import LLMNotConfigured
from app.db import get_db
from app.deps import current_user
from app.models import Airport, Trip, User
from app.schemas import ChatResponse, MessageIn, MessageOut, TripCreate, TripEventOut, TripOut, TripSummary
from app.services.events import events_after
from app.services.planner import RefinementError, run_refinement, run_trip_planning

router = APIRouter(prefix="/trips", tags=["trips"])

TERMINAL = {"completed", "failed"}


def _get_owned(db: Session, user: User, trip_id: int) -> Trip:
    trip = db.get(Trip, trip_id)
    if trip is None or trip.user_id != user.id:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.post("", response_model=TripOut, status_code=202)
def create_trip(
    payload: TripCreate,
    request: Request,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Trip:
    codes = [payload.origin, *payload.destinations]
    known = {a.iata: a for a in db.scalars(select(Airport).where(Airport.iata.in_(codes))).all()}
    missing = [c for c in codes if c not in known]
    if missing:
        raise HTTPException(status_code=422, detail=f"Unsupported location code(s): {', '.join(missing)}")
    title = payload.title or f"Trip to {', '.join(known[d].city for d in payload.destinations)}"
    trip = Trip(
        user_id=user.id,
        title=title,
        origin=payload.origin,
        destinations=payload.destinations,
        start_date=payload.start_date,
        end_date=payload.end_date,
        adults=payload.adults,
        children=payload.children,
        budget=payload.budget,
        currency=request.app.state.settings.currency,
        cabin_class=payload.cabin_class,
        hotel_min_stars=payload.hotel_min_stars,
        pace=payload.pace,
        travel_style=payload.travel_style,
        interests=payload.interests,
        dietary_needs=payload.dietary_needs,
        accessibility_needs=payload.accessibility_needs,
        notes=payload.notes,
        status="queued",
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    background.add_task(run_trip_planning, trip.id, request.app.state.llm_factory)
    return trip


@router.get("", response_model=list[TripSummary])
def list_trips(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Trip]:
    return list(db.scalars(select(Trip).where(Trip.user_id == user.id).order_by(Trip.created_at.desc(), Trip.id.desc())).all())


@router.get("/{trip_id}", response_model=TripOut)
def get_trip(trip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Trip:
    return _get_owned(db, user, trip_id)


@router.delete("/{trip_id}", status_code=204)
def delete_trip(trip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    trip = _get_owned(db, user, trip_id)
    if trip.status in ("queued", "running"):
        raise HTTPException(status_code=409, detail="Wait for planning to finish before deleting this trip")
    db.delete(trip)
    db.commit()


@router.post("/{trip_id}/replan", response_model=TripOut, status_code=202)
def replan(trip_id: int, request: Request, background: BackgroundTasks, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Trip:
    trip = _get_owned(db, user, trip_id)
    if trip.status in ("queued", "running"):
        raise HTTPException(status_code=409, detail="Planning is already in progress")
    trip.status, trip.error, trip.plan = "queued", None, None
    db.commit()
    background.add_task(run_trip_planning, trip.id, request.app.state.llm_factory)
    return trip


@router.get("/{trip_id}/events", response_model=list[TripEventOut])
def list_events(trip_id: int, after: int = Query(default=0, ge=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    _get_owned(db, user, trip_id)
    return events_after(db, trip_id, after)


@router.get("/{trip_id}/stream")
async def stream_events(trip_id: int, request: Request, after: int = Query(default=0, ge=0), user: User = Depends(current_user)):
    """Server-Sent Events: ``progress`` per agent event, then one ``status`` event."""

    def _check() -> None:
        with db_module.SessionLocal() as db:
            _get_owned(db, user, trip_id)

    await run_in_threadpool(_check)
    last_id = request.headers.get("last-event-id")
    cursor = int(last_id) if last_id and last_id.isdigit() else after

    def _poll(since: int) -> tuple[list[dict], str]:
        with db_module.SessionLocal() as db:
            trip = db.get(Trip, trip_id)
            events = [TripEventOut.model_validate(e).model_dump(mode="json") for e in events_after(db, trip_id, since)]
            return events, trip.status if trip else "failed"

    async def gen() -> AsyncIterator[str]:
        nonlocal cursor
        yield "retry: 3000\n\n"
        idle = 0
        while True:
            if await request.is_disconnected():
                break
            events, status = await run_in_threadpool(_poll, cursor)
            for ev in events:
                cursor = ev["seq"]
                yield f"id: {ev['seq']}\nevent: progress\ndata: {json.dumps(ev)}\n\n"
            if status in TERMINAL and not events:
                yield f"event: status\ndata: {json.dumps({'status': status})}\n\n"
                break
            idle = 0 if events else idle + 1
            if idle and idle % 30 == 0:
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{trip_id}/messages", response_model=list[MessageOut])
def list_messages(trip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _get_owned(db, user, trip_id).messages


@router.post("/{trip_id}/messages", response_model=ChatResponse)
def send_message(trip_id: int, payload: MessageIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    trip = _get_owned(db, user, trip_id)
    try:
        reply = run_refinement(db, trip, payload.message.strip(), request.app.state.llm_factory)
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RefinementError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # LLM/network failure
        db.rollback()
        raise HTTPException(status_code=502, detail=f"The concierge agent failed: {type(exc).__name__}: {exc}") from exc
    user_msg = next(m for m in reversed(trip.messages) if m.role == "user")
    return ChatResponse(
        user_message=MessageOut.model_validate(user_msg),
        assistant_message=MessageOut.model_validate(reply),
        trip=TripOut.model_validate(trip),
    )
