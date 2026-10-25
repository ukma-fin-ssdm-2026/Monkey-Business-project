"""TP-04 / FR-004, FR-005 / US-005: HTTP and committed PostgreSQL state."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from src.api import db
from src.api.auth import _issue_token
from src.api.domain import Board, Card, Stage, User
from src.api.main import app
from src.api.repositories.sql import Base, CardRow, build_repositories


@pytest.fixture
def postgres_sessions(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TP-04 requires TEST_DATABASE_URL pointing to PostgreSQL")
    root_engine = create_engine(url)
    if root_engine.dialect.name != "postgresql":
        pytest.fail("TP-04 must use PostgreSQL, not a SQLite substitute")
    schema = "lab07_" + uuid4().hex
    with root_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = root_engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(engine)
        sessions = sessionmaker(engine)
        # Keep the real request dependency: each request commits or rolls back.
        monkeypatch.setattr(db, "_session_factory", lambda: sessions)
        monkeypatch.setenv(
            "JWT_SECRET", "lab07-test-only-signing-key-32-characters"
        )  # pragma: allowlist secret
        yield sessions
    finally:
        with root_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        root_engine.dispose()


@pytest.mark.integration
def test_tp04_move_between_stages_commits_order(postgres_sessions):
    """TP-04: S1=A,B and S2=C become S1=A and S2=B,C after POST."""
    with postgres_sessions.begin() as session:
        repos = build_repositories(session)
        owner = repos.users.add(
            User(email="owner@example.com", password_hash="", role="candidate")
        )
        board = repos.boards.add(Board(owner_id=owner.id))
        source = repos.stages.add(Stage(board_id=board.id, name="S1", order_index=0))
        target = repos.stages.add(Stage(board_id=board.id, name="S2", order_index=1))
        cards = [
            repos.cards.add(
                Card(
                    board_id=board.id,
                    stage_id=stage.id,
                    company=name,
                    position="Developer",
                    position_index=index,
                )
            )
            for name, stage, index in (
                ("A", source, 0),
                ("B", source, 1),
                ("C", target, 0),
            )
        ]
    headers = {"Authorization": f"Bearer {_issue_token(owner).access_token}"}
    path = f"/v1/boards/{board.id}/cards"

    with TestClient(app) as client:
        response = client.post(
            f"{path}/{cards[1].id}/move",
            json={"stage_id": str(target.id), "position_index": 0},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["id"] == str(cards[1].id)
        assert response.json()["stage_id"] == str(target.id)
        assert response.json()["position_index"] == 0
        for stage, expected in ((source, ["A"]), (target, ["B", "C"])):
            response = client.get(
                path, params={"stage_id": str(stage.id)}, headers=headers
            )
            assert response.status_code == 200, response.text
            items = response.json()["items"]
            assert [item["company"] for item in items] == expected
            assert [item["position_index"] for item in items] == list(
                range(len(expected))
            )

    # A separate connection/session proves persistence after the HTTP transaction.
    with postgres_sessions() as verification:
        rows = verification.scalars(
            select(CardRow).where(CardRow.board_id == board.id)
        ).all()
        assert {row.id for row in rows} == {card.id for card in cards}
        for stage, expected in ((source, ["A"]), (target, ["B", "C"])):
            ordered = sorted(
                (row for row in rows if row.stage_id == stage.id),
                key=lambda row: row.position_index,
            )
            assert [row.company for row in ordered] == expected
            assert [row.position_index for row in ordered] == list(range(len(expected)))
