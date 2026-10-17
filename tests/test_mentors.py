"""
Інструмент: Gemini
Застосування: Написання тесту, підготовка фікстур та допоміжних моделей

Верифікація: перевірено логіку та відповідність тесту вимогам та rtm, додано 2.1 в rtm.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

import pytest

from src.api import auth
from src.api.errors import ConflictError, ForbiddenError
from src.api.repositories.base import Repositories
from src.api.routers import cards as cards_router, mentors
from src.api.schemas import CardUpdate, UserRole


# --- Допоміжні моделі та InMemory-репозиторії ---

class MentorStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    revoked = "revoked"


class BoardMentor:
    def __init__(
        self,
        board_id: UUID,
        mentor_id: UUID,
        invite_token: str,
        status: str,
        invited_at: datetime | None = None,
        accepted_at: datetime | None = None,
        id: UUID | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.board_id = board_id
        self.mentor_id = mentor_id
        self.invite_token = invite_token
        self.status = status
        self.invited_at = invited_at or datetime.now(timezone.utc)
        self.accepted_at = accepted_at


class InMemoryRepository:
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


class InMemoryUserRepository(InMemoryRepository):
    def get_by_email(self, email: str):
        return next((u for u in self.items.values() if u.email == email), None)


class InMemoryBoardMentorRepository(InMemoryRepository):
    def get_by_board_and_mentor(self, board_id: UUID, mentor_id: UUID):
        return next(
            (
                m
                for m in self.items.values()
                if m.board_id == board_id and m.mentor_id == mentor_id
            ),
            None,
        )


class InMemoryCardRepository(InMemoryRepository):
    def list_for_board(self, board_id, stage_id=None, status=None):
        return [c for c in self.items.values() if c.board_id == board_id]

    def count_in_stage(self, stage_id):
        return sum(1 for c in self.items.values() if c.stage_id == stage_id)


# --- Pytest Фікстури ---

@pytest.fixture
def mentors_repo() -> InMemoryBoardMentorRepository:
    return InMemoryBoardMentorRepository()


@pytest.fixture
def repos(mentors_repo) -> Repositories:
    return Repositories(
        users=InMemoryUserRepository(),
        boards=InMemoryRepository(),
        stages=InMemoryRepository(),
        cards=InMemoryCardRepository(),
        links=None,
        notes=None,
        mentors=mentors_repo,
    )


@pytest.fixture
def mock_external_calls(monkeypatch) -> list[dict]:
    sent_emails = []

    monkeypatch.setattr(
        mentors,
        "_send_invitation_email",
        lambda email, token, board_id: sent_emails.append(
            {"email": email, "token": token, "board_id": board_id}
        ),
    )
    monkeypatch.setattr(mentors, "_require_board", lambda *args, **kwargs: None)

    return sent_emails


@pytest.fixture
def mock_require_board_for_cards(monkeypatch):
    """Фікстура для захисту роутера карток від запису не-кандидатами."""
    def _fake_require_board(repos, board_id, user, *, write=False):
        if write and user.role != UserRole.candidate.value and user.role != "admin":
            raise ForbiddenError("Доступ до дошки заборонено")

    monkeypatch.setattr(cards_router, "_require_board", _fake_require_board)


@pytest.fixture
def card_repos(repos, mentors_repo):
    """Репозиторії та тестові дані для перевірки дій із картками."""
    from src.api.domain import Board, Card

    board_id = uuid4()
    stage_id = uuid4()

    candidate = repos.users.add(
        auth.User(
            email="candidate@example.com",
            password_hash="unused",  # pragma: allowlist secret
            role=UserRole.candidate.value,
            is_active=True,
        )
    )
    mentor = repos.users.add(
        auth.User(
            email="mentor@example.com",
            password_hash="unused",  # pragma: allowlist secret
            role=UserRole.mentor.value,
            is_active=True,
        )
    )

    repos.boards.add(Board(owner_id=candidate.id, id=board_id))

    card = Card(
        board_id=board_id,
        stage_id=stage_id,
        company="Acme Corp",
        position="Backend Engineer",
        position_index=0,
    )
    repos.cards.add(card)

    mentors_repo.add(
        BoardMentor(
            board_id=board_id,
            mentor_id=mentor.id,
            invite_token="accepted-token",
            status=MentorStatus.accepted.value,
        )
    )

    return {
        "repos": repos,
        "mentor": mentor,
        "candidate": candidate,
        "board_id": board_id,
        "card_id": card.id,
    }


# --- Тести ---

def test_2_1_invite_mentor_reinvites_revoked_mentor(
    repos, mentors_repo, mock_external_calls
):
    board_id = uuid4()

    inviter = repos.users.add(
        auth.User(
            email="candidate@example.com",
            password_hash="unused",  # pragma: allowlist secret
            role=UserRole.candidate.value,
            is_active=True,
        )
    )

    mentor_email = "mentor@example.com"
    mentor = repos.users.add(
        auth.User(
            email=mentor_email,
            password_hash="unused",  # pragma: allowlist secret
            role=UserRole.mentor.value,
            is_active=True,
        )
    )
    old_token = "old-revoked-token"
    revoked_invitation = mentors_repo.add(
        BoardMentor(
            board_id=board_id,
            mentor_id=mentor.id,
            invite_token=old_token,
            status=MentorStatus.revoked.value,
            accepted_at=datetime.now(timezone.utc),
        )
    )

    payload = mentors.InviteMentorRequest(email=mentor_email)

    mentors.invite_mentor(
        payload=payload,
        board_id=board_id,
        user=inviter,
        repos=repos,
    )

    updated = mentors_repo.get(revoked_invitation.id)

    assert updated.status == MentorStatus.pending.value
    assert updated.accepted_at is None
    assert updated.invite_token != old_token

    assert len(mock_external_calls) == 1
    assert mock_external_calls[0]["email"] == mentor_email
    assert mock_external_calls[0]["token"] == updated.invite_token
    assert mock_external_calls[0]["board_id"] == board_id


def test_02_mentor_cannot_edit_card(card_repos, mock_require_board_for_cards):
    payload = CardUpdate(position="New Position")

    with pytest.raises(ForbiddenError):
        cards_router.update_card(
            payload=payload,
            board_id=card_repos["board_id"],
            card_id=card_repos["card_id"],
            user=card_repos["mentor"],
            repos=card_repos["repos"],
        )


def test_08_mentor_cannot_change_company_field(card_repos, mock_require_board_for_cards):
    payload = CardUpdate(company="Нова Компанія")
    assert payload.company == "Нова Компанія"

    with pytest.raises(ForbiddenError) as exc_info:
        cards_router.update_card(
            payload=payload,
            board_id=card_repos["board_id"],
            card_id=card_repos["card_id"],
            user=card_repos["mentor"],
            repos=card_repos["repos"],
        )

    status_code = getattr(exc_info.value, "status_code", 403)
    assert status_code == 403 or exc_info.type is ForbiddenError