"""
Інструмент: Claude
Застосування: Інтеграційний тест коментаря ментора через API з PostgreSQL
(TP-10 з docs/validation/test-plan.md; FR-013, FR-014, US-008).
Верифікація: Прогін pytest проти PostgreSQL 16 і 17 у Docker.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import select

from src.api.domain import utcnow
from src.api.repositories.sql import CardRow, CommentRow

pytestmark = pytest.mark.integration


def _card_snapshot(new_session, card_id: UUID) -> dict:
    with new_session() as session:
        row = session.execute(
            select(CardRow.__table__).where(CardRow.id == card_id)
        ).one()
    return row._asdict()


# TP-10
def test_mentor_comment_persists_and_leaves_card_unchanged(
    client, owner, mentor, card, new_session
):
    card_id = UUID(card["id"])
    url = f"/v1/boards/{owner.board_id}/cards/{card_id}/comments"
    content = "Повторіть асинхронність у FastAPI перед технічним інтерв'ю"
    card_before = _card_snapshot(new_session, card_id)
    started_at = utcnow()

    created = client.post(url, json={"content": content}, headers=mentor.headers)

    finished_at = utcnow()
    assert created.status_code == 201
    listed = client.get(url, headers=owner.headers)
    assert listed.status_code == 200
    [comment] = listed.json()
    assert comment["id"] == created.json()["id"]
    assert comment["content"] == content
    assert UUID(comment["author_id"]) == mentor.id
    assert started_at <= datetime.fromisoformat(comment["created_at"]) <= finished_at
    with new_session() as session:
        row = session.get(CommentRow, UUID(comment["id"]))
    assert (row.card_id, row.author_id, row.content) == (card_id, mentor.id, content)
    assert _card_snapshot(new_session, card_id) == card_before
