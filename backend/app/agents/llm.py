"""LLM factory: Gemini through CrewAI's native provider."""

from __future__ import annotations

from crewai import LLM, BaseLLM

from app.config import Settings, get_settings


class LLMNotConfigured(RuntimeError):
    pass


def build_llm(settings: Settings | None = None) -> BaseLLM:
    settings = settings or get_settings()
    if not settings.gemini_api_key:
        raise LLMNotConfigured(
            "GEMINI_API_KEY is not set, so the AI agents cannot run. Flight and hotel "
            "search and booking still work - add a key to backend/.env to enable planning."
        )
    model = settings.gemini_model
    if "/" not in model:
        model = f"gemini/{model}"
    return LLM(model=model, api_key=settings.gemini_api_key, temperature=settings.llm_temperature)
