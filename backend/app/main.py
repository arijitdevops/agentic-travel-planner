"""FastAPI application entry point: ``uvicorn app.main:app --reload``."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update

from app import __version__
from app import db as db_module
from app.api import api_router
from app.config import Settings, get_settings
from app.models import Trip

log = logging.getLogger("app")


def _startup(settings: Settings) -> None:
    db_module.init_db()
    with db_module.SessionLocal() as db:
        if settings.seed_on_startup:
            from app.seed import seed_inventory

            counts = seed_inventory(db)
            if any(counts.values()):
                log.info("Seeded mock inventory: %s", counts)
        # Jobs run in-process; anything still "running" was interrupted by a restart.
        db.execute(
            update(Trip)
            .where(Trip.status.in_(["queued", "running"]))
            .values(status="failed", error="Planning was interrupted by a server restart. Use 'Re-plan' to try again.", current_step=None)
        )
        db.commit()
    if not settings.llm_configured:
        log.warning("GEMINI_API_KEY is not set: AI planning is disabled, search and booking still work.")


def create_app(settings: Settings | None = None, llm_factory=None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _startup(settings)
        yield

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Multi-agent (CrewAI + Gemini) travel planner with simulated flight and hotel booking.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.llm_factory = llm_factory  # None -> build Gemini LLM from settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
