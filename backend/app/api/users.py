from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import User
from app.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/me", tags=["users"])


@router.get("", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.put("", response_model=UserOut)
def update_me(payload: UserUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
    user = db.merge(user)
    user.name = payload.name.strip()
    db.commit()
    return user
