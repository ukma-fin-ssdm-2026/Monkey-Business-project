"""
Інструмент: Claude
Застосування: Інтеграційні тести доступу ментора через API з PostgreSQL:
TP-02 (відкликання доступу; FR-015, US-002) і TP-11 (заборона зміни карток
ментором; SEC-3, FR-014, US-002) з docs/validation/test-plan.md.
Верифікація: прогін pytest проти PostgreSQL (TEST_DATABASE_URL), перевірка
чек-листом ШІ-коду з docs/validation/review-log.md.

Фікстури client, owner, mentor, card, stage_ids, new_session беруться з
tests/integration/conftest.py. Перед кожним тестом таблиці очищуються, тому
кожен варіант TP-11 стартує з однакових даних.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import func, select

from src.api.repositories.sql import BoardMentorRow, CardRow

pytestmark = pytest.mark.integration


def _card_snapshot(new_session, card_id: UUID) -> dict:
    with new_session() as session:
        row = session.execute(
            select(CardRow.__table__).where(CardRow.id == card_id)
        ).one()
    return row._asdict()


def _cards_count(new_session, board_id: UUID) -> int:
    with new_session() as session:
        return session.scalar(
            select(func.count()).select_from(CardRow).where(CardRow.board_id == board_id)
        )


# TP-02
def test_revoked_mentor_loses_access_and_status_is_persisted(
    client, owner, mentor, card, new_session
):
    cards_url = f"/v1/boards/{owner.board_id}/cards"

    # Передумова: ментор із прийнятим запрошенням читає картки дошки.
    assert client.get(cards_url, headers=mentor.headers).status_code == 200

    revoked = client.delete(
        f"/v1/boards/{owner.board_id}/mentors/{mentor.id}", headers=owner.headers
    )

    assert revoked.status_code == 204
    # Той самий JWT ментора більше не дає доступу.
    assert client.get(cards_url, headers=mentor.headers).status_code == 403
    # Власник доступ зберігає.
    assert client.get(cards_url, headers=owner.headers).status_code == 200
    # Статус збережено й видно з нової сесії БД.
    with new_session() as session:
        invitation = session.scalar(
            select(BoardMentorRow).where(
                BoardMentorRow.board_id == owner.board_id,
                BoardMentorRow.mentor_id == mentor.id,
            )
        )
    assert invitation.status == "revoked"
    assert invitation.accepted_at is None


# TP-11 (SEC-3): 3 варіанти заборонених дій, 3 із 3 мають дати 403 без змін у БД
FORBIDDEN_ACTIONS = [
    pytest.param(
        "patch", lambda c, stages: ("PATCH", {"position": "Hacked by mentor"}), id="patch"
    ),
    pytest.param("delete", lambda c, stages: ("DELETE", None), id="delete"),
    pytest.param(
        "move",
        lambda c, stages: (
            "POST",
            {"stage_id": str(stages[1]), "position_index": 0},
        ),
        id="move",
    ),
]


@pytest.mark.parametrize("action, build", FORBIDDEN_ACTIONS)
def test_mentor_with_read_access_cannot_change_card(
    action, build, client, owner, mentor, card, stage_ids, new_session
):
    card_id = UUID(card["id"])
    card_url = f"/v1/boards/{owner.board_id}/cards/{card_id}"
    url = card_url + "/move" if action == "move" else card_url
    method, payload = build(card, stage_ids)

    # Передумова: ментор має доступ на читання цієї картки.
    assert client.get(card_url, headers=mentor.headers).status_code == 200
    before = _card_snapshot(new_session, card_id)
    count_before = _cards_count(new_session, owner.board_id)

    response = client.request(method, url, json=payload, headers=mentor.headers)

    assert response.status_code == 403
    # Дані не змінено: поля, етап, позиція й кількість карток.
    assert _card_snapshot(new_session, card_id) == before
    assert _cards_count(new_session, owner.board_id) == count_before