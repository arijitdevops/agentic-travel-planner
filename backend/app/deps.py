"""Request dependencies: DB session and the current user.

Authentication is intentionally lightweight for a sample app: the client
sends ``X-User-Email`` (and optionally ``X-User-Name``). Missing header ->
the configured demo user. EventSource cannot send headers, so the SSE route
also accepts ``?user=<email>``.
"""

from __future__ import annotations

from email_validator import EmailNotValidError, validate_email
from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User


def get_or_create_user(db: Session, email: str, name: str | None = None) -> User:
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(email=email, name=name or email.split("@")[0].replace(".", " ").title())
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # created concurrently
        db.rollback()
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
    return user


def current_user(
    db: Session = Depends(get_db),
    x_user_email: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    user: str | None = Query(default=None, include_in_schema=False),
) -> User:
    settings = get_settings()
    email = x_user_email or user
    if not email:
        return get_or_create_user(db, settings.demo_user_email, settings.demo_user_name)
    try:
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid X-User-Email: {exc}") from exc
    return get_or_create_user(db, email, x_user_name)
