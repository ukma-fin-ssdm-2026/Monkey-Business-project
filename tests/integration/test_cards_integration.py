"""
Інструмент: Claude
Застосування: Інтеграційний тест створення картки через API з PostgreSQL
(TP-06 з docs/validation/test-plan.md; FR-007, US-007).
Верифікація: Прогін pytest проти PostgreSQL 16 і 17 у Docker.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select

from src.api.repositories.sql import CardRow

pytestmark = pytest.mark.integration


def _cards_on_board(new_session, board_id: UUID) -> list[CardRow]:
    with new_session() as session:
        return list(
            session.scalars(select(CardRow).where(CardRow.board_id == board_id))
        )


# TP-06
def test_owner_creates_card_that_persists(client, owner, stage_ids, new_session):
    url = f"/v1/boards/{owner.board_id}/cards"
    payload = {
        "company": "Acme",
        "position": "Python Developer",
        "stage_id": str(stage_ids[0]),
    }
    assert _cards_on_board(new_session, owner.board_id) == []

    created = client.post(url, json=payload, headers=owner.headers)

    assert created.status_code == 201
    card_id = UUID(created.json()["id"])
    fetched = client.get(f"{url}/{card_id}", headers=owner.headers)
    assert fetched.status_code == 200
    assert fetched.json() == created.json()
    assert {key: fetched.json()[key] for key in payload} == payload
    rows = _cards_on_board(new_session, owner.board_id)
    assert [(row.id, row.company, row.position, row.stage_id) for row in rows] == [
        (card_id, "Acme", "Python Developer", stage_ids[0])
    ]
