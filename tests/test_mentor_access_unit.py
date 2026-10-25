"""
Інструмент: Claude
Застосування: Модульні тести TP-01 (доступ ментора до запису; FR-014, US-002) і
TP-14 (запрошення ментора; FR-012, US-002) з docs/validation/test-plan.md.
Доповнюють tests/test_auth.py і tests/test_mentors.py перевірками, яких там немає:
TP-01 — що жоден метод запису репозиторіїв не викликається при відмові;
TP-14 — що запрошення збережено зі статусом pending, непорожнім токеном і
прив'язкою до створеного облікового запису, а лист отримав саме цю адресу й токен.
Верифікація: прогін pytest без БД; кожну перевірку звірено з auth.py і
routers/mentors.py; чек-лист ШІ-коду з docs/validation/review-log.md.

Тести викликають функції напряму, без HTTP і бази даних. Справжня доставка
email поза обсягом плану: _send_invitation_email замінено дублером.
"""

from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.api import auth
from src.api.domain import Board, User
from src.api.errors import ForbiddenError
from src.api.repositories.base import Repositories
from src.api.routers import mentors
from src.api.schemas import InviteMentorRequest, MentorStatus, UserRole


# --------------------------------------------------------------------------- #
# TP-01: auth.require_board_access
# --------------------------------------------------------------------------- #


def _repos_with_invited_mentor(board: Board) -> tuple[Repositories, dict, Mock]:
    """Репозиторії, де дошка існує, а ментора запрошено; решта — спостережувані Mock."""
    boards = Mock(spec=["get", "mentor_has_access"])
    boards.get.return_value = board
    boards.mentor_has_access.return_value = True
    others = {
        name: Mock()
        for name in ("users", "stages", "cards", "links", "notes", "mentors", "comments")
    }
    return Repositories(boards=boards, **others), others, boards


# TP-01
def test_tp01_invited_mentor_write_access_is_forbidden_and_nothing_is_written():
    mentor = User(email="mentor@example.com", password_hash="unused", role="mentor")
    board = Board(owner_id=uuid4())
    repos, others, boards = _repos_with_invited_mentor(board)

    with pytest.raises(ForbiddenError):
        auth.require_board_access(repos, board.id, mentor, write=True)

    # Жоден репозиторій, окрім читання дошки й перевірки запрошення, не зачеплено.
    for name, repo in others.items():
        assert repo.mock_calls == [], f"репозиторій {name} не мав викликатися"
    assert {call[0] for call in boards.mock_calls} <= {"get", "mentor_has_access"}


# TP-01 (контроль): відмова залежить саме від write=True, а не від відсутності доступу
def test_tp01_same_invited_mentor_can_read():
    mentor = User(email="mentor@example.com", password_hash="unused", role="mentor")
    board = Board(owner_id=uuid4())
    repos, others, _ = _repos_with_invited_mentor(board)

    assert auth.require_board_access(repos, board.id, mentor, write=False) is None
    for repo in others.values():
        assert repo.mock_calls == []


# --------------------------------------------------------------------------- #
# TP-14: mentors.invite_mentor
# --------------------------------------------------------------------------- #


class _InMemory:
    def __init__(self) -> None:
        self.items: dict = {}

    def add(self, entity):
        self.items[entity.id] = entity
        return entity

    def get(self, entity_id):
        return self.items.get(entity_id)

    def save(self, entity):
        self.items[entity.id] = entity
        return entity


class _Users(_InMemory):
    def get_by_email(self, email: str):
        return next((u for u in self.items.values() if u.email == email), None)


class _Mentors(_InMemory):
    def get_by_board_and_mentor(self, board_id, mentor_id):
        return next(
            (
                m
                for m in self.items.values()
                if m.board_id == board_id and m.mentor_id == mentor_id
            ),
            None,
        )


# TP-14
def test_tp14_owner_invites_new_email_creates_mentor_and_pending_invitation(
    monkeypatch,
):
    sent: list[tuple] = []
    monkeypatch.setattr(
        mentors,
        "_send_invitation_email",
        lambda email, token, board_id: sent.append((email, token, board_id)),
    )
    users, invitations, boards = _Users(), _Mentors(), _InMemory()
    owner = users.add(
        User(
            email="candidate@example.com",
            password_hash="unused", # pragma: allowlist secret
            role=UserRole.candidate.value,
        )
    )
    board = boards.add(Board(owner_id=owner.id))
    repos = Repositories(
        users=users,
        boards=boards,
        stages=None,
        cards=None,
        links=None,
        notes=None,
        mentors=invitations,
    )

    result = mentors.invite_mentor(
        payload=InviteMentorRequest(email="new.mentor@example.com"),
        board_id=board.id,
        user=owner,
        repos=repos,
    )

    # Створено обліковий запис ролі mentor.
    created = users.get_by_email("new.mentor@example.com")
    assert created is not None
    assert created.role == UserRole.mentor.value
    # Створено рівно одне запрошення: pending, непорожній токен, прив'язка до дошки й ментора.
    [invitation] = list(invitations.items.values())
    assert invitation.status == MentorStatus.pending.value
    assert invitation.board_id == board.id
    assert invitation.mentor_id == created.id
    assert invitation.invite_token.strip() != ""
    # Поштовий дублер отримав саме цю адресу, цей токен і цю дошку — рівно один лист.
    assert sent == [("new.mentor@example.com", invitation.invite_token, board.id)]
    # Відповідь API узгоджена зі збереженим станом.
    assert result.status == MentorStatus.pending
    assert result.mentor_id == created.id
    assert result.invite_token == invitation.invite_token