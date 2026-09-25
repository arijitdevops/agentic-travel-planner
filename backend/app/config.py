"""Application settings, loaded from environment variables and ``.env``."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App -----------------------------------------------------------------
    app_name: str = "Agentic Travel Planner"
    environment: Literal["development", "production", "test"] = "development"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])
    demo_user_email: str = "demo@travelplanner.local"
    demo_user_name: str = "Demo Traveler"

    # --- Database ------------------------------------------------------------
    database_url: str = "mysql+pymysql://travel:travel@localhost:3306/travel_planner?charset=utf8mb4"
    db_echo: bool = False
    seed_on_startup: bool = True

    # --- LLM (Gemini via CrewAI) ---------------------------------------------
    gemini_api_key: str | None = None
    gemini_model: str = "gemini/gemini-2.5-flash"
    llm_temperature: float = 0.4
    agent_max_iter: int = 8
    crew_verbose: bool = False

    # --- Web search ----------------------------------------------------------
    tavily_api_key: str | None = None
    web_search_max_results: int = 5
    web_search_enabled: bool = True

    # --- Travel providers ----------------------------------------------------
    flight_provider: Literal["local", "duffel"] = "local"
    duffel_access_token: str | None = None
    duffel_base_url: str = "https://api.duffel.com"
    offer_ttl_minutes: int = 30
    currency: str = "USD"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip().startswith("["):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @property
    def llm_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
