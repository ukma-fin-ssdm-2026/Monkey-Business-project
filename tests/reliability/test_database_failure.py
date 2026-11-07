"""
Інструмент: Claude
Застосування: Тести надійності R1 (Лаб 9): ін'єкція відмови БД, формат
помилки, /health і обмеження очікування на БД.
Верифікація: тести запущено через pytest; без виправлення R1 вони падають
(сирий 500 text/plain, /health 200 при недоступній БД).

Обрана реакція — швидка відмова: 503 у форматі ErrorResponse з request_id,
без деталей драйвера; /health повертає 503, щоб моніторинг побачив інцидент.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from src.api import db

DRIVER_MESSAGE = 'connection to server at "10.0.0.5", port 5432 failed: timeout expired'
LOGIN = {
    "email": "user@example.com",
    "password": "correct-pass-1",  # pragma: allowlist secret
}


class _DeadDatabaseSession:
    """Тестовий дублер сесії: кожен запит до БД падає, як при обриві з'єднання."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception(DRIVER_MESSAGE))

    scalar = get = execute


class _DeadDatabaseFactory:
    def __call__(self) -> _DeadDatabaseSession:
        return _DeadDatabaseSession()

    def begin(self) -> _DeadDatabaseSession:
        return _DeadDatabaseSession()


@pytest.fixture
def dead_database(monkeypatch) -> None:
    monkeypatch.setattr(db, "_session_factory", lambda: _DeadDatabaseFactory())


# Тест зовнішньої відмови (ін'єкція збою)
def test_request_fails_fast_with_503_in_error_format_when_database_is_down(
    client, dead_database
):
    response = client.post("/v1/auth/login", json=LOGIN)

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "SERVICE_UNAVAILABLE"
    assert error["request_id"] == response.headers["X-Request-ID"]
    # Hosts and driver text stay in the server log (CWE-209).
    assert "10.0.0.5" not in response.text
    assert "OperationalError" not in response.text


# Тест зовнішньої відмови (ін'єкція збою)
def test_health_reports_unhealthy_when_database_is_down(client, dead_database):
    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "checks": {"database": "unavailable"},
    }


def test_health_reports_ok_when_database_answers(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok"}


def test_health_recovers_after_database_outage(client, monkeypatch):
    """Codex: health status is rechecked after recovery, without an API restart."""
    assert client.get("/health").status_code == 200

    with monkeypatch.context() as fault:
        fault.setattr(db, "_session_factory", lambda: _DeadDatabaseFactory())
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {
            "status": "unhealthy",
            "checks": {"database": "unavailable"},
        }
        assert "10.0.0.5" not in response.text
        assert "OperationalError" not in response.text

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


def test_health_reports_unhealthy_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db._session_factory.cache_clear()
    try:
        assert db.database_is_available() is False
    finally:
        db._session_factory.cache_clear()


# Граничний тест: жодне очікування на БД не є необмеженим
def test_every_wait_on_database_is_bounded(monkeypatch):
    created: dict = {}
    monkeypatch.setattr(
        db, "create_engine", lambda url, **kwargs: created.update(kwargs)
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db.invalid/app")
    db._session_factory.cache_clear()
    try:
        db._session_factory()
    finally:
        db._session_factory.cache_clear()

    # Connect, query and waiting for a free pool slot are all limited.
    assert created["connect_args"]["connect_timeout"] == db.CONNECT_TIMEOUT_SECONDS
    assert (
        f"statement_timeout={db.STATEMENT_TIMEOUT_MS}"
        in created["connect_args"]["options"]
    )
    assert created["pool_timeout"] == db.POOL_TIMEOUT_SECONDS
    assert db.CONNECT_TIMEOUT_SECONDS + db.POOL_TIMEOUT_SECONDS < 30
