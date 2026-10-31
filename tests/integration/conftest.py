"""
Інструмент: Claude
Застосування: Спільні фікстури інтеграційних тестів API + PostgreSQL за
docs/validation/test-plan.md (власник дошки, ментор із прийнятим запрошенням,
картка, нова сесія БД для перевірки збереження).
Верифікація: Прогін pytest проти PostgreSQL 16 і 17 у Docker.

Тести працюють з окремою базою з TEST_DATABASE_URL: схема створюється
міграціями Alembic, а перед кожним тестом усі таблиці очищуються. Тому не
вказуйте тут адресу бази, дані якої потрібні. Без TEST_DATABASE_URL тести
пропускаються; у CI їх запускає .github/workflows/lab07-card-order.yml.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session

from src.api.db import _session_factory
from src.api.main import app
from src.api.repositories.sql import Base, BoardRow
from src.api.routers import mentors as mentors_router

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


@dataclass(frozen=True)
class Account:
    id: UUID
    board_id: UUID
    headers: dict[str, str]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TP-06/TP-10 потребують TEST_DATABASE_URL на окрему PostgreSQL")
    with pytest.MonkeyPatch.context() as patch:
        # The app reads DATABASE_URL once and caches the session factory.
        patch.setenv("DATABASE_URL", url)
        _session_factory.cache_clear()
        # A Config without an ini file skips fileConfig in migrations/env.py,
        # which would otherwise reset pytest's logging setup.
        config = Config()
        config.set_main_option("script_location", str(MIGRATIONS))
        command.upgrade(config, "head")
        engine = create_engine(url)
        yield engine
        engine.dispose()
        _session_factory.cache_clear()


@pytest.fixture(autouse=True)
def clean_tables(engine: Engine) -> None:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} CASCADE"))


@pytest.fixture
def new_session(engine: Engine) -> Callable[[], Session]:
    """Сесія поза транзакцією запиту: бачить лише зафіксовані API дані."""
    return lambda: Session(engine)


@pytest.fixture
def client(engine: Engine) -> TestClient:
    # No `with` block: the lifespan would rewrite docs/api/openapi-generated.yaml.
    return TestClient(app)


@pytest.fixture
def owner(client: TestClient, new_session: Callable[[], Session]) -> Account:
    response = client.post(
        "/v1/auth/register",
        json={
            "email": "candidate@example.com",
            "password": "candidate-password",  # pragma: allowlist secret
        },
    )
    assert response.status_code == 201
    user_id = UUID(response.json()["user"]["id"])
    # Read the board from the database, not GET /v1/boards, so that
    # test_boards_integration.py checks that endpoint against independent data.
    with new_session() as session:
        board_id = session.scalar(
            select(BoardRow.id).where(BoardRow.owner_id == user_id)
        )
    return Account(
        id=user_id, board_id=board_id, headers=_bearer(response.json()["access_token"])
    )


@pytest.fixture
def mentor(client: TestClient, owner: Account, monkeypatch) -> Account:
    # Real email delivery is out of scope of the test plan; the token is in the response.
    monkeypatch.setattr(mentors_router, "_send_invitation_email", lambda *args: None)
    invitation = client.post(
        f"/v1/boards/{owner.board_id}/mentors",
        json={"email": "mentor@example.com"},
        headers=owner.headers,
    )
    assert invitation.status_code == 201
    accepted = client.post(
        f"/v1/invitations/{invitation.json()['invite_token']}/accept",
        json={"password": "mentor-password"},  # pragma: allowlist secret
    )
    assert accepted.status_code == 200
    return Account(
        id=UUID(invitation.json()["mentor_id"]),
        board_id=owner.board_id,
        headers=_bearer(accepted.json()["access_token"]),
    )


@pytest.fixture
def stage_ids(client: TestClient, owner: Account) -> list[UUID]:
    response = client.get(f"/v1/boards/{owner.board_id}/stages", headers=owner.headers)
    assert response.status_code == 200
    return [UUID(stage["id"]) for stage in response.json()]


@pytest.fixture
def card(client: TestClient, owner: Account, stage_ids: list[UUID]) -> dict:
    response = client.post(
        f"/v1/boards/{owner.board_id}/cards",
        json={
            "company": "Acme",
            "position": "Python Developer",
            "stage_id": str(stage_ids[0]),
        },
        headers=owner.headers,
    )
    assert response.status_code == 201
    return response.json()
