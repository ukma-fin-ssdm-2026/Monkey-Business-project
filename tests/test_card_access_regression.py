"""Спільні гарантії доступу до посилань і нотаток картки.

## Використання ШІ
- **Інструмент:** Codex.
- **Застосування:** створення тестів порядку перевірок доступу й текстів помилок.
- **Верифікація:** автор переглянув сценарії та перевірив результати тестів.
"""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.api.domain import Board, User
from src.api.errors import ForbiddenError, NotFoundError
from src.api.routers import card_links, card_notes


@pytest.fixture(params=[card_links.list_links, card_notes.list_notes])
def list_children(request):
    return request.param


def test_missing_board_keeps_exact_error(list_children):
    board_id, card_id = uuid4(), uuid4()
    repos = SimpleNamespace(boards=Mock(), cards=Mock())
    repos.boards.get.return_value = None
    user = User(email="reader@example.com", password_hash="", role="candidate")

    with pytest.raises(NotFoundError) as error:
        list_children(board_id, card_id, user, repos)

    assert error.value.message == f"Дошку {board_id} не знайдено"
    repos.cards.get.assert_not_called()


def test_forbidden_board_is_checked_before_card(list_children):
    user = User(email="reader@example.com", password_hash="", role="candidate")
    board = Board(owner_id=uuid4())
    repos = SimpleNamespace(boards=Mock(), cards=Mock())
    repos.boards.get.return_value = board

    with pytest.raises(ForbiddenError) as error:
        list_children(board.id, uuid4(), user, repos)

    assert error.value.message == "Доступ до дошки заборонено"
    repos.cards.get.assert_not_called()


@pytest.mark.parametrize("foreign_card", [False, True])
def test_missing_or_foreign_card_keeps_exact_error(list_children, foreign_card):
    user = User(email="reader@example.com", password_hash="", role="candidate")
    board = Board(owner_id=user.id)
    card_id = uuid4()
    repos = SimpleNamespace(boards=Mock(), cards=Mock())
    repos.boards.get.return_value = board
    repos.cards.get.return_value = (
        SimpleNamespace(board_id=uuid4()) if foreign_card else None
    )

    with pytest.raises(NotFoundError) as error:
        list_children(board.id, card_id, user, repos)

    assert error.value.message == (f"Картку {card_id} на дошці {board.id} не знайдено")
