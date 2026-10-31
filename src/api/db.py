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
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .repositories.base import Repositories
from .repositories.sql import build_repositories


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
    return sessionmaker(create_engine(database_url(), pool_pre_ping=True))


def get_repositories() -> Iterator[Repositories]:
    # begin() commits when the request handler succeeds and rolls back when
    # it raises, including ApiError responses such as 404 or 409.
    with _session_factory().begin() as session:
        yield build_repositories(session)


Repos = Annotated[Repositories, Depends(get_repositories)]
