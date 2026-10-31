"""
Тести для модуля src/api/routers/boards.py:
- Кандидат отримує власну дошку з access=owner.
- Ментор отримує дошку, до якої має доступ, з access=mentor.
- Користувач без дошок отримує порожній список.

Використано шаблон AAA (Arrange - Act - Assert) та Mock репозиторію дошок.
"""

from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

from src.api.domain import Board, User
from src.api.repositories.base import Repositories
from src.api.routers import boards as boards_router
from src.api.schemas import BoardAccess


def _user(role: str) -> User:
    return User(
        email=f"{role}@example.com",
        password_hash="unused",  # pragma: allowlist secret
        role=role,
    )


def _repos(boards: list[Board]) -> Repositories:
    board_repo = Mock(spec=["list_for_user"])
    board_repo.list_for_user.return_value = boards
    return Repositories(
        users=None,
        boards=board_repo,
        stages=None,
        cards=None,
        links=None,
        notes=None,
    )


def test_candidate_sees_own_board_as_owner():
    candidate = _user("candidate")
    board = Board(owner_id=candidate.id)
    repos = _repos([board])

    result = boards_router.list_my_boards(user=candidate, repos=repos)

    assert [(b.id, b.access) for b in result] == [(board.id, BoardAccess.owner)]
    repos.boards.list_for_user.assert_called_once_with(candidate.id)


def test_mentor_sees_shared_board_as_mentor():
    mentor = _user("mentor")
    board = Board(owner_id=uuid4())

    result = boards_router.list_my_boards(user=mentor, repos=_repos([board]))

    assert len(result) == 1
    assert result[0].id == board.id
    assert result[0].owner_id == board.owner_id
    assert result[0].access == BoardAccess.mentor


def test_user_without_boards_gets_empty_list():
    admin = _user("admin")

    assert boards_router.list_my_boards(user=admin, repos=_repos([])) == []
