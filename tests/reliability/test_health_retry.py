"""
Інструмент: Claude Code
Застосування: Лаб 9, бонус «повтори з відступом і джитером» для
database_is_available (/health): ін'єкція тимчасових відмов БД, перевірка
обмеженої кількості спроб, експоненційного відступу з full jitter, дедлайну
та реакції після останньої спроби (fallback → 503 unhealthy).
Верифікація: запуск pytest tests/reliability.
"""

from __future__ import annotations

import logging

import pytest
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from src.api import db

UNHEALTHY = {"status": "unhealthy", "checks": {"database": "unavailable"}}


def _connection_lost() -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception("connection reset by peer"))


class FlakyDatabase:
    """Тестовий дублер: перші `failures` спроб SELECT 1 падають, далі успіх."""

    def __init__(self, failures: int, error=_connection_lost) -> None:
        self.failures = failures
        self.error = error
        self.attempts = 0

    def __call__(self) -> None:
        self.attempts += 1
        if self.attempts <= self.failures:
            raise self.error()


@pytest.fixture
def max_jitter(monkeypatch) -> list[tuple[float, float]]:
    """Jitter returns the upper bound, so delays are deterministic."""
    calls: list[tuple[float, float]] = []

    def upper_bound(low: float, high: float) -> float:
        calls.append((low, high))
        return high

    monkeypatch.setattr(db, "_uniform", upper_bound)
    return calls


# Ін'єкція збою: БД лежить постійно — кількість спроб обмежена,
# після останньої спрацьовує fallback.
def test_retries_are_bounded_and_fallback_reports_unhealthy(
    client, monkeypatch, no_backoff_sleep, max_jitter, caplog
):
    dead = FlakyDatabase(failures=10**6)
    monkeypatch.setattr(db, "_ping_database", dead)

    with caplog.at_level(logging.WARNING, logger=db.__name__):
        response = client.get("/health")

    assert dead.attempts == db.HEALTH_CHECK_MAX_ATTEMPTS == 3
    # No sleep after the last attempt: the fallback answers immediately.
    assert no_backoff_sleep == [0.2, 0.4]
    assert response.status_code == 503
    assert response.json() == UNHEALTHY
    assert "unavailable after 3 attempt(s)" in caplog.text


# Тимчасовий збій: одна обірвана сесія не перемикає /health у 503.
@pytest.mark.parametrize("error", [_connection_lost, lambda: PoolTimeoutError()])
def test_transient_failure_recovers_within_retries(
    client, monkeypatch, no_backoff_sleep, max_jitter, error
):
    flaky = FlakyDatabase(failures=2, error=error)
    monkeypatch.setattr(db, "_ping_database", flaky)

    response = client.get("/health")

    assert flaky.attempts == 3
    assert len(no_backoff_sleep) == 2
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


def test_healthy_database_is_checked_once_without_sleep(monkeypatch, no_backoff_sleep):
    healthy = FlakyDatabase(failures=0)
    monkeypatch.setattr(db, "_ping_database", healthy)

    assert db.database_is_available() is True
    assert healthy.attempts == 1
    assert no_backoff_sleep == []


# Неперехідні помилки не повторюються: секунда очікування їх не виправить.
@pytest.mark.parametrize(
    "error",
    [
        lambda: RuntimeError("DATABASE_URL is not set"),
        lambda: ProgrammingError("SELECT 1", {}, Exception("permission denied")),
    ],
)
def test_non_transient_error_is_not_retried(monkeypatch, no_backoff_sleep, error):
    broken = FlakyDatabase(failures=1, error=error)
    monkeypatch.setattr(db, "_ping_database", broken)

    assert db.database_is_available() is False
    assert broken.attempts == 1
    assert no_backoff_sleep == []


# Full jitter: затримка рівномірна від 0 до min(cap, base * 2**(n-1)).
def test_backoff_is_exponential_capped_full_jitter(max_jitter):
    delays = [db.backoff_delay(attempt) for attempt in range(1, 7)]

    assert delays == [0.2, 0.4, 0.8, 1.0, 1.0, 1.0]
    assert all(low == 0.0 for low, _ in max_jitter)


def test_backoff_delay_stays_within_full_jitter_bounds():
    for attempt in range(1, 8):
        ceiling = min(
            db.HEALTH_CHECK_BACKOFF_CAP_SECONDS,
            db.HEALTH_CHECK_BACKOFF_BASE_SECONDS * 2 ** (attempt - 1),
        )
        for _ in range(200):
            assert 0.0 <= db.backoff_delay(attempt) <= ceiling


# Тайм-аут обмежує повтори: якщо до дедлайну не вміщується ще одна повна
# спроба, повторів більше немає, навіть якщо ліміт спроб не вичерпано.
def test_retries_stop_when_deadline_leaves_no_room_for_another_attempt(
    monkeypatch, no_backoff_sleep, max_jitter
):
    dead = FlakyDatabase(failures=10**6)
    monkeypatch.setattr(db, "_ping_database", dead)
    # Each attempt "takes" a full connect timeout of 3 s on a fake clock.
    clock = iter([0.0, 3.0, 7.0, 100.0])
    monkeypatch.setattr(db, "_monotonic", lambda: next(clock))
    monkeypatch.setattr(db, "HEALTH_CHECK_MAX_ATTEMPTS", 5)

    assert db.database_is_available() is False
    # Attempt 1 fails at 3.0 s: 3.0 + 0.2 + 3 = 6.2 <= 10 → retry.
    # Attempt 2 fails at 7.0 s: 7.0 + 0.4 + 3 = 10.4 > 10 → stop, though 5 allowed.
    assert dead.attempts == 2
    assert no_backoff_sleep == [0.2]
