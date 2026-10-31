"""
Інструмент: Claude
Застосування: Інтеграційні тести GET /v1/boards («мої дошки») з PostgreSQL:
кандидат бачить власну дошку, ментор — лише після прийняття запрошення і до
його відкликання.
Верифікація: прогін pytest проти PostgreSQL (TEST_DATABASE_URL).

Фікстури client, owner, mentor беруться з tests/integration/conftest.py.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_owner_gets_board_created_at_registration(client, owner):
    response = client.get("/v1/boards", headers=owner.headers)

    assert response.status_code == 200
    assert [(b["id"], b["access"]) for b in response.json()] == [
        (str(owner.board_id), "owner")
    ]


def test_mentor_sees_board_only_while_access_is_accepted(client, owner, mentor):
    listed = client.get("/v1/boards", headers=mentor.headers)

    assert listed.status_code == 200
    assert [(b["id"], b["owner_id"], b["access"]) for b in listed.json()] == [
        (str(owner.board_id), str(owner.id), "mentor")
    ]

    revoked = client.delete(
        f"/v1/boards/{owner.board_id}/mentors/{mentor.id}", headers=owner.headers
    )
    assert revoked.status_code == 204
    assert client.get("/v1/boards", headers=mentor.headers).json() == []


def test_boards_require_token(client):
    assert client.get("/v1/boards").status_code == 401
