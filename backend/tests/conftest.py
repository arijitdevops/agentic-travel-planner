from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / "tests" / ".test.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["GEMINI_API_KEY"] = ""
os.environ["TAVILY_API_KEY"] = ""
os.environ["WEB_SEARCH_ENABLED"] = "false"
os.environ["FLIGHT_PROVIDER"] = "local"
os.environ["SEED_ON_STARTUP"] = "true"
os.environ["ENVIRONMENT"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

from app import db as db_module  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import seed_inventory  # noqa: E402
from tests.fakes import FakeLLM  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    if TEST_DB.exists():
        TEST_DB.unlink()
    db_module.init_db()
    with db_module.SessionLocal() as db:
        seed_inventory(db)
    yield
    db_module.engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture()
def db():
    with db_module.SessionLocal() as session:
        yield session


@pytest.fixture()
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture()
def client(fake_llm):
    app = create_app(llm_factory=lambda: fake_llm)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client_no_llm():
    app = create_app()  # GEMINI_API_KEY is empty -> planning degrades gracefully
    with TestClient(app) as c:
        yield c


def future(days: int) -> date:
    return date.today() + timedelta(days=days)


def user_headers(email: str) -> dict[str, str]:
    return {"X-User-Email": email}
