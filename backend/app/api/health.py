from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_settings
from app.db import get_db
from app.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:  # pragma: no cover
        database = f"error: {type(exc).__name__}"
    return HealthOut(
        status="ok" if database == "ok" else "degraded",
        version=__version__,
        llm_configured=settings.llm_configured,
        llm_model=settings.gemini_model,
        flight_provider=settings.flight_provider,
        hotel_provider="local",
        web_search=("disabled" if not settings.web_search_enabled else "tavily" if settings.tavily_api_key else "duckduckgo"),
        database=database,
    )
