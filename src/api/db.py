"""
Інструмент: Claude
Застосування: Підключення до бази даних і видача репозиторіїв на час запиту
через залежність FastAPI.
Верифікація: Перевірено вручну фіксацію змін після успішного запиту та їх
відкат після помилки (4xx) проти PostgreSQL у Docker Compose.
Доповнення (Claude Code, Лаб 9, бонус): обмежені повтори health check з
експоненційним відступом і full jitter; перевірено
tests/reliability/test_health_retry.py.

Єдине місце, де API пов'язується з конкретним сховищем: роутери отримують
лише набір Repositories. Щоб перейти на іншу СУБД, достатньо підставити тут
іншу реалізацію build_repositories.
"""

from __future__ import annotations

import logging
import os
import random
import time
from collections.abc import Iterator
from functools import cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.orm import Session, sessionmaker

from .repositories.base import LoginAttemptRepository, Repositories
from .repositories.sql import SqlLoginAttemptRepository, build_repositories

# Every wait on the database is bounded (Lab 9, R1): without these a dead
# database host keeps a worker and a pool slot busy for ~2 minutes of TCP
# retries, and a slow query holds them indefinitely.
CONNECT_TIMEOUT_SECONDS = 3
STATEMENT_TIMEOUT_MS = 5_000
POOL_TIMEOUT_SECONDS = 5

# Health check retries (Lab 9 bonus): a single dropped connection or a busy
# pool should not flip /health to 503, but the probe must still answer within
# a load balancer's typical 10 s probe timeout.
HEALTH_CHECK_MAX_ATTEMPTS = 3
HEALTH_CHECK_BACKOFF_BASE_SECONDS = 0.2
HEALTH_CHECK_BACKOFF_CAP_SECONDS = 1.0
HEALTH_CHECK_DEADLINE_SECONDS = 10.0
_TRANSIENT_DB_ERRORS = (OperationalError, PoolTimeoutError)

# Indirection so tests can count sleeps and fix the jitter without waiting.
_sleep = time.sleep
_monotonic = time.monotonic
_uniform = random.uniform

logger = logging.getLogger(__name__)


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Змінну середовища DATABASE_URL не задано (див. src/api/README.md)"
        )
    return url


# Created on first use, not at import: generating the OpenAPI spec in CI
# imports the app without a database.
@cache
def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        database_url(),
        pool_pre_ping=True,
        pool_timeout=POOL_TIMEOUT_SECONDS,
        connect_args={
            "connect_timeout": CONNECT_TIMEOUT_SECONDS,
            "options": f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",
        },
    )
    return sessionmaker(engine)


def _ping_database() -> None:
    """One attempt: SELECT 1, bounded by connect/statement/pool timeouts."""
    with _session_factory()() as session:
        session.execute(text("SELECT 1"))


def backoff_delay(attempt: int) -> float:
    """Full jitter after failed attempt N (from 1): uniform(0, min(cap, base * 2**(N-1)))."""
    ceiling = min(
        HEALTH_CHECK_BACKOFF_CAP_SECONDS,
        HEALTH_CHECK_BACKOFF_BASE_SECONDS * 2 ** (attempt - 1),
    )
    # Jitter only spreads retries in time; it is not a security value.
    return _uniform(0.0, ceiling)  # nosec B311


def database_is_available() -> bool:
    """Чи відповідає БД на SELECT 1 (для /health), з обмеженими повторами.

    Composition (Lecture 9, §3.5), from the inside out:
    1. timeout — every attempt is bounded by CONNECT/STATEMENT/POOL timeouts;
    2. retry — at most HEALTH_CHECK_MAX_ATTEMPTS attempts with exponential
       backoff and full jitter, and only while the overall deadline allows
       another full attempt;
    3. fallback — False, so /health reports "unhealthy" (503).

    SELECT 1 is read-only, so repeating it is safe. Only transient errors
    (connection failure, pool timeout) are retried: a missing DATABASE_URL or
    another database error will not fix itself in a second.
    """
    started = _monotonic()
    for attempt in range(1, HEALTH_CHECK_MAX_ATTEMPTS + 1):
        try:
            _ping_database()
        except _TRANSIENT_DB_ERRORS as exc:
            if attempt == HEALTH_CHECK_MAX_ATTEMPTS:
                break
            delay = backoff_delay(attempt)
            elapsed = _monotonic() - started
            if (
                elapsed + delay + CONNECT_TIMEOUT_SECONDS
                > HEALTH_CHECK_DEADLINE_SECONDS
            ):
                logger.warning(
                    "Database health check: no time left for attempt %d "
                    "within %.1fs deadline",
                    attempt + 1,
                    HEALTH_CHECK_DEADLINE_SECONDS,
                )
                break
            logger.warning(
                "Database health check attempt %d/%d failed (%s); retrying in %.2fs",
                attempt,
                HEALTH_CHECK_MAX_ATTEMPTS,
                type(exc).__name__,
                delay,
            )
            _sleep(delay)
        # RuntimeError: DATABASE_URL is not set, so there is no database to reach.
        except (SQLAlchemyError, RuntimeError) as exc:
            logger.error(
                "Database health check failed with a non-retryable error: %s",
                type(exc).__name__,
            )
            return False
        else:
            if attempt > 1:
                logger.info("Database answered on attempt %d", attempt)
            return True
    logger.error("Database unavailable after %d attempt(s)", attempt)
    return False


def get_repositories() -> Iterator[Repositories]:
    # begin() commits when the request handler succeeds and rolls back when
    # it raises, including ApiError responses such as 404 or 409.
    with _session_factory().begin() as session:
        yield build_repositories(session)


def get_login_attempts() -> LoginAttemptRepository:
    return SqlLoginAttemptRepository(_session_factory())


Repos = Annotated[Repositories, Depends(get_repositories)]
LoginAttempts = Annotated[LoginAttemptRepository, Depends(get_login_attempts)]
