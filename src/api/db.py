"""
Інструмент: Claude
Застосування: Підключення до бази даних і видача репозиторіїв на час запиту
через залежність FastAPI.
Верифікація: Перевірено вручну фіксацію змін після успішного запиту та їх
відкат після помилки (4xx) проти PostgreSQL у Docker Compose.

Єдине місце, де API пов'язується з конкретним сховищем: роутери отримують
лише набір Repositories. Щоб перейти на іншу СУБД, достатньо підставити тут
іншу реалізацію build_repositories.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from functools import cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .repositories.base import LoginAttemptRepository, Repositories
from .repositories.sql import SqlLoginAttemptRepository, build_repositories

# Every wait on the database is bounded (Lab 9, R1): without these a dead
# database host keeps a worker and a pool slot busy for ~2 minutes of TCP
# retries, and a slow query holds them indefinitely.
CONNECT_TIMEOUT_SECONDS = 3
STATEMENT_TIMEOUT_MS = 5_000
POOL_TIMEOUT_SECONDS = 5


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


def database_is_available() -> bool:
    """Чи відповідає БД на SELECT 1 (для /health)."""
    try:
        with _session_factory()() as session:
            session.execute(text("SELECT 1"))
    # RuntimeError: DATABASE_URL is not set, so there is no database to reach.
    except (SQLAlchemyError, RuntimeError):
        return False
    return True


def get_repositories() -> Iterator[Repositories]:
    # begin() commits when the request handler succeeds and rolls back when
    # it raises, including ApiError responses such as 404 or 409.
    with _session_factory().begin() as session:
        yield build_repositories(session)


def get_login_attempts() -> LoginAttemptRepository:
    return SqlLoginAttemptRepository(_session_factory())


Repos = Annotated[Repositories, Depends(get_repositories)]
LoginAttempts = Annotated[LoginAttemptRepository, Depends(get_login_attempts)]
