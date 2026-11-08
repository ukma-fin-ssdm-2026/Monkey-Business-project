"""
Інструмент: Claude
Застосування: Спільні фікстури тестів надійності (Лаб 9): застосунок поверх
SQLite у пам'яті замість PostgreSQL.
Верифікація: тести tests/reliability запущено через pytest.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.api import db
from src.api.main import app
from src.api.repositories.sql import Base

TEST_SECRET = "reliability-test-jwt-secret-32-bytes"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)


@pytest.fixture(autouse=True)
def no_backoff_sleep(monkeypatch) -> list[float]:
    """Health check retries record their backoff instead of really sleeping."""
    sleeps: list[float] = []
    monkeypatch.setattr(db, "_sleep", sleeps.append)
    return sleeps


@pytest.fixture
def session_factory(monkeypatch) -> Iterator[sessionmaker[Session]]:
    # One shared connection, so every session sees the same in-memory database.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(db, "_session_factory", lambda: factory)
    yield factory
    engine.dispose()


@pytest.fixture
def client(session_factory) -> TestClient:
    # Without `with`: the lifespan would rewrite docs/api/openapi-generated.yaml.
    return TestClient(app, raise_server_exceptions=False)
