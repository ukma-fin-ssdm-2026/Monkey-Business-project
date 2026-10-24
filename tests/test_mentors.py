"""
Інструмент: Gemini, Claude
Застосування: Gemini — початкові тести та фікстури (запрошення, read-only ментор).
Claude — переробка: прибрано підміну `_require_board` (раніше тест перевіряв власну
заглушку, а не код), використано доменну модель BoardMentor замість копії, додано
тести для invite/list/get/accept/revoke та граничних випадків.
Верифікація: тести запущено через pytest; кожну гілку mentors.py звірено вручну;
перевірено, що навмисне зламання коду (мутації) робить тести червоними.

Тести викликають функції роутерів напряму, без HTTP і бази даних. Захист дошки
(`require_board_access`) працює справжній — підмінено лише відправку email і сховища.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError
from fastapi.security import HTTPAuthorizationCredentials

from unittest.mock import MagicMock
from src.api.errors import ServiceUnavailableError
import src.api.routers.mentors as mentors_router_module

from src.api import auth
from src.api.domain import Board, BoardMentor, Card, User
from src.api.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from src.api.repositories.base import Repositories
from src.api.routers import cards as cards_router
from src.api.routers import mentors
from src.api.schemas import (
    AcceptInvitationRequest,
    CardUpdate,
    InviteMentorRequest,
    MentorStatus,
    UserRole,
)
from src.api.routers import comments as comments_router
from src.api.schemas import CommentCreate

TEST_SECRET = "unit-test-jwt-secret-at-least-32-bytes"  # pragma: allowlist secret
MENTOR_PASSWORD = "mentor-password-123"  # pragma: allowlist secret


# --------------------------------------------------------------------------- #
# Тестові дублери (In-Memory Fakes)
# --------------------------------------------------------------------------- #


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

class InMemoryCardChildRepository(InMemoryRepository):
    def list_for_card(self, card_id):
        return [i for i in self.items.values() if getattr(i, "card_id", None) == card_id]

class InMemoryCommentRepository(InMemoryRepository):
    def list_for_card(self, card_id: uuid4) -> list:
        return [c for c in self.items.values() if getattr(c, "card_id", None) == card_id]

class InMemoryCardChildRepository(InMemoryRepository):
    def list_for_card(self, card_id):
        return [i for i in self.items.values() if getattr(i, "card_id", None) == card_id]

class InMemoryUserRepository(InMemoryRepository):
    def get_by_email(self, email: str):
        return next((u for u in self.items.values() if u.email == email), None)


class InMemoryBoardMentorRepository(InMemoryRepository):
    def get_by_token(self, token: str):
        return next((m for m in self.items.values() if m.invite_token == token), None)

    def get_by_board_and_mentor(self, board_id, mentor_id):
        return next(
            (
                m
                for m in self.items.values()
                if m.board_id == board_id and m.mentor_id == mentor_id
            ),
            None,
        )

    def list_for_board(self, board_id):
        return [m for m in self.items.values() if m.board_id == board_id]


class InMemoryBoardRepository(InMemoryRepository):
    """Доступ ментора, як і в SQL-реалізації, дає лише статус accepted."""

    def __init__(self, mentors_repo: InMemoryBoardMentorRepository) -> None:
        super().__init__()
        self._mentors = mentors_repo

    def mentor_has_access(self, board_id, mentor_id) -> bool:
        link = self._mentors.get_by_board_and_mentor(board_id, mentor_id)
        return link is not None and link.status == MentorStatus.accepted.value


class InMemoryCardRepository(InMemoryRepository):
    pass


# --------------------------------------------------------------------------- #
# Фікстури
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch) -> str:
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    return TEST_SECRET


@pytest.fixture
def mentors_repo() -> InMemoryBoardMentorRepository:
    return InMemoryBoardMentorRepository()


@pytest.fixture
def repos(mentors_repo) -> Repositories:
    return Repositories(
        users=InMemoryUserRepository(),
        boards=InMemoryBoardRepository(mentors_repo),
        stages=InMemoryRepository(),
        cards=InMemoryCardRepository(),
        links=None,
        notes=InMemoryCardChildRepository(),
        mentors=mentors_repo,
        comments=InMemoryCardChildRepository(),
    )


@pytest.fixture
def sent_emails(monkeypatch) -> list[dict]:
    """Заглушка поштового сервісу: запам'ятовує листи замість відправки."""
    sent: list[dict] = []
    monkeypatch.setattr(
        mentors,
        "_send_invitation_email",
        lambda email, token, board_id: sent.append(
            {"email": email, "token": token, "board_id": board_id}
        ),
    )
    return sent


@pytest.fixture
def make_user(repos):
    def _make(email: str, role: UserRole, password_hash: str = "unused") -> User:
        return repos.users.add(
            User(email=email, password_hash=password_hash, role=role.value)
        )

    return _make


@pytest.fixture
def candidate(make_user) -> User:
    return make_user("candidate@example.com", UserRole.candidate)


@pytest.fixture
def board(repos, candidate) -> Board:
    return repos.boards.add(Board(owner_id=candidate.id))


@pytest.fixture
def mentor(make_user) -> User:
    return make_user("mentor@example.com", UserRole.mentor)


@pytest.fixture
def make_invitation(repos, board):
    def _make(mentor: User, status: MentorStatus, token: str = "token-1"):
        return repos.mentors.add(
            BoardMentor(
                board_id=board.id,
                mentor_id=mentor.id,
                invite_token=token,
                status=status.value,
            )
        )

    return _make


@pytest.fixture
def card(repos, board) -> Card:
    return repos.cards.add(
        Card(
            board_id=board.id,
            stage_id=uuid4(),
            company="Acme Corp",
            position="Backend Engineer",
            position_index=0,
        )
    )


def _bearer(user: User) -> HTTPAuthorizationCredentials:
    token = auth._issue_token(user).access_token
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


# --------------------------------------------------------------------------- #
# invite_mentor (FR-012)
# --------------------------------------------------------------------------- #

# US-002
def test_invite_mentor_creates_account_and_pending_invitation(
    repos, board, candidate, sent_emails
):
    # Arrange
    payload = InviteMentorRequest(email="New.Mentor@Example.com")

    # Act
    result = mentors.invite_mentor(
        payload=payload, board_id=board.id, user=candidate, repos=repos
    )

    # Assert
    created = repos.users.get_by_email("new.mentor@example.com")
    assert created.role == UserRole.mentor.value
    assert result.status == MentorStatus.pending
    assert result.email == "new.mentor@example.com"
    assert [e["email"] for e in sent_emails] == ["new.mentor@example.com"]
    assert sent_emails[0]["token"] == result.invite_token

# US-002
def test_invite_mentor_reuses_existing_mentor_account(
    repos, board, candidate, mentor, sent_emails
):
    # Arrange
    payload = InviteMentorRequest(email=mentor.email)

    # Act
    result = mentors.invite_mentor(
        payload=payload, board_id=board.id, user=candidate, repos=repos
    )

    # Assert
    assert result.mentor_id == mentor.id
    assert len(repos.users.items) == 2  # candidate + mentor, без дубліката

# US-002
def test_2_1_invite_mentor_reinvites_revoked_mentor(
    repos, board, candidate, mentor, make_invitation, sent_emails
):
    # Arrange
    revoked = make_invitation(mentor, MentorStatus.revoked, token="old-token")
    payload = InviteMentorRequest(email=mentor.email)

    # Act
    mentors.invite_mentor(
        payload=payload, board_id=board.id, user=candidate, repos=repos
    )

    # Assert
    updated = repos.mentors.get(revoked.id)
    assert updated.status == MentorStatus.pending.value
    assert updated.accepted_at is None
    assert updated.invite_token != "old-token"
    assert len(sent_emails) == 1
    assert sent_emails[0]["token"] == updated.invite_token


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (MentorStatus.accepted, "уже має доступ"),
        (MentorStatus.pending, "вже очікує підтвердження"),
    ],
    ids=["already-accepted", "already-pending"],
)
# US-002
def test_invite_mentor_rejects_duplicate_invitation(
    repos, board, candidate, mentor, make_invitation, sent_emails, status, message
):
    # Arrange
    make_invitation(mentor, status)

    # Act & Assert
    with pytest.raises(ConflictError, match=message):
        mentors.invite_mentor(
            payload=InviteMentorRequest(email=mentor.email),
            board_id=board.id,
            user=candidate,
            repos=repos,
        )
    assert sent_emails == []

# US-002
def test_invite_mentor_rejects_inviting_yourself(repos, board, candidate, sent_emails):
    # Arrange
    payload = InviteMentorRequest(email=candidate.email.upper())

    # Act & Assert
    with pytest.raises(ConflictError, match="самого себе"):
        mentors.invite_mentor(
            payload=payload, board_id=board.id, user=candidate, repos=repos
        )
    assert sent_emails == []

# US-002
def test_invite_mentor_rejects_email_registered_with_other_role(
    repos, board, candidate, make_user, sent_emails
):
    # Arrange
    other = make_user("other.candidate@example.com", UserRole.candidate)

    # Act & Assert
    with pytest.raises(ConflictError, match="іншою роллю"):
        mentors.invite_mentor(
            payload=InviteMentorRequest(email=other.email),
            board_id=board.id,
            user=candidate,
            repos=repos,
        )

# US-002
def test_invite_mentor_raises_not_found_for_missing_board(
    repos, candidate, sent_emails
):
    # Act & Assert
    with pytest.raises(NotFoundError):
        mentors.invite_mentor(
            payload=InviteMentorRequest(email="m@example.com"),
            board_id=uuid4(),
            user=candidate,
            repos=repos,
        )

# US-002
def test_invite_mentor_forbidden_for_foreign_candidate(
    repos, board, make_user, sent_emails
):
    # Arrange
    stranger = make_user("stranger@example.com", UserRole.candidate)

    # Act & Assert
    with pytest.raises(ForbiddenError):
        mentors.invite_mentor(
            payload=InviteMentorRequest(email="m@example.com"),
            board_id=board.id,
            user=stranger,
            repos=repos,
        )
    assert sent_emails == []


# --------------------------------------------------------------------------- #
# list_board_mentors / get_invitation
# --------------------------------------------------------------------------- #

# US-002
def test_list_board_mentors_returns_emails_and_statuses(
    repos, board, candidate, mentor, make_invitation
):
    # Arrange
    make_invitation(mentor, MentorStatus.accepted)

    # Act
    result = mentors.list_board_mentors(board_id=board.id, user=candidate, repos=repos)

    # Assert
    assert [(m.email, m.status) for m in result] == [
        (mentor.email, MentorStatus.accepted)
    ]

# US-002
def test_list_board_mentors_skips_deleted_mentor(
    repos, board, candidate, mentor, make_invitation
):
    # Arrange: запрошення посилається на користувача, якого немає в базі
    ghost = User(email="ghost@example.com", password_hash="", role="mentor")
    make_invitation(ghost, MentorStatus.pending)
    make_invitation(mentor, MentorStatus.accepted, token="valid")

    # Act
    result = mentors.list_board_mentors(board_id=board.id, user=candidate, repos=repos)

    # Assert
    assert [(item.mentor_id, item.email) for item in result] == [
        (mentor.id, mentor.email)
    ]

# US-002
def test_get_invitation_rejects_deleted_mentor(repos, make_invitation):
    ghost = User(email="ghost@example.com", password_hash="", role="mentor")
    invitation = make_invitation(ghost, MentorStatus.pending)

    with pytest.raises(NotFoundError):
        mentors.get_invitation(token=invitation.invite_token, repos=repos)


@pytest.mark.parametrize("use_bearer", [False, True], ids=["password", "bearer"])

# US-002
def test_accept_invitation_rejects_deleted_mentor(
    repos, mentor, make_invitation, use_bearer
):
    ghost = User(email="ghost@example.com", password_hash="", role="mentor")
    invitation = make_invitation(ghost, MentorStatus.pending)
    payload = None if use_bearer else AcceptInvitationRequest(password=MENTOR_PASSWORD)
    credentials = _bearer(mentor) if use_bearer else None

    with pytest.raises(ForbiddenError):
        mentors.accept_invitation(
            token=invitation.invite_token,
            payload=payload,
            credentials=credentials,
            repos=repos,
        )

    assert invitation.status == MentorStatus.pending.value
    assert invitation.mentor_id == ghost.id

# US-002
def test_get_invitation_returns_pending_invitation(repos, mentor, make_invitation):
    # Arrange
    make_invitation(mentor, MentorStatus.pending, token="abc")

    # Act
    result = mentors.get_invitation(token="abc", repos=repos)

    # Assert
    assert result.email == mentor.email
    assert result.status == MentorStatus.pending


@pytest.mark.parametrize(
    "status",
    [None, MentorStatus.accepted, MentorStatus.revoked],
    ids=["unknown-token", "already-accepted", "revoked"],
)

# US-002
def test_get_invitation_hides_non_pending_invitations(
    repos, mentor, make_invitation, status
):
    # Arrange
    if status is not None:
        make_invitation(mentor, status, token="abc")

    # Act & Assert
    with pytest.raises(NotFoundError):
        mentors.get_invitation(token="abc", repos=repos)


# --------------------------------------------------------------------------- #
# accept_invitation
# --------------------------------------------------------------------------- #

# US-002
def test_accept_invitation_with_password_activates_account_and_issues_token(
    repos, mentor, make_invitation
):
    # Arrange
    invitation = make_invitation(mentor, MentorStatus.pending, token="abc")
    payload = AcceptInvitationRequest(password=MENTOR_PASSWORD)

    # Act
    response = mentors.accept_invitation(
        token="abc", payload=payload, credentials=None, repos=repos
    )

    # Assert
    assert response.status == MentorStatus.accepted
    assert response.access_token
    assert auth._verify_password(MENTOR_PASSWORD, mentor.password_hash)
    saved = repos.mentors.get(invitation.id)
    assert saved.status == MentorStatus.accepted.value
    assert saved.accepted_at is not None

# US-002
def test_accept_invitation_with_bearer_of_invited_mentor(
    repos, mentor, make_invitation
):
    # Arrange
    invitation = make_invitation(mentor, MentorStatus.pending, token="abc")

    # Act
    response = mentors.accept_invitation(
        token="abc", payload=None, credentials=_bearer(mentor), repos=repos
    )

    # Assert
    assert response.access_token is None
    assert repos.mentors.get(invitation.id).status == MentorStatus.accepted.value

# US-002
@pytest.mark.parametrize("status", [None, MentorStatus.accepted, MentorStatus.revoked])
def test_accept_invitation_rejects_unknown_or_used_token(
    repos, mentor, make_invitation, status
):
    # Arrange
    if status is not None:
        make_invitation(mentor, status, token="abc")

    # Act & Assert
    with pytest.raises(ForbiddenError, match="Недійсне"):
        mentors.accept_invitation(
            token="abc",
            payload=AcceptInvitationRequest(password=MENTOR_PASSWORD),
            credentials=None,
            repos=repos,
        )

# US-002
def test_accept_invitation_rejects_bearer_of_non_mentor(
    repos, mentor, candidate, make_invitation
):
    # Arrange
    make_invitation(mentor, MentorStatus.pending, token="abc")

    # Act & Assert
    with pytest.raises(ForbiddenError, match="Лише ментор"):
        mentors.accept_invitation(
            token="abc", payload=None, credentials=_bearer(candidate), repos=repos
        )

# US-002
def test_accept_invitation_rejects_bearer_of_different_mentor(
    repos, mentor, make_user, make_invitation
):
    # Arrange
    make_invitation(mentor, MentorStatus.pending, token="abc")
    other_mentor = make_user("other.mentor@example.com", UserRole.mentor)

    # Act & Assert
    with pytest.raises(ForbiddenError, match="іншого email"):
        mentors.accept_invitation(
            token="abc", payload=None, credentials=_bearer(other_mentor), repos=repos
        )


@pytest.mark.parametrize(
    ("password_hash", "message"),
    [
        ("", "Вкажіть пароль"),
        ("already$set", "Потрібен вхід"),
    ],
    ids=["new-mentor-must-set-password", "existing-mentor-must-log-in"],
)

# US-002
def test_accept_invitation_without_credentials_or_password_is_unauthorized(
    repos, make_user, make_invitation, password_hash, message
):
    # Arrange
    mentor = make_user("m@example.com", UserRole.mentor, password_hash=password_hash)
    invitation = make_invitation(mentor, MentorStatus.pending, token="abc")

    # Act & Assert
    with pytest.raises(UnauthorizedError, match=message):
        mentors.accept_invitation(
            token="abc", payload=None, credentials=None, repos=repos
        )
    assert repos.mentors.get(invitation.id).status == MentorStatus.pending.value

# US-002
def test_accept_invitation_rejects_password_shorter_than_8_chars():
    # Граничне значення схеми: 7 символів — помилка, 8 — дозволено.
    with pytest.raises(ValidationError):
        AcceptInvitationRequest(password="x" * 7)
    assert AcceptInvitationRequest(password="x" * 8).password == "x" * 8


# --------------------------------------------------------------------------- #
# revoke_mentor (FR-015)
# --------------------------------------------------------------------------- #

# US-002
def test_revoke_mentor_marks_invitation_revoked_and_removes_access(
    repos, board, candidate, mentor, make_invitation
):
    # Arrange
    invitation = make_invitation(mentor, MentorStatus.accepted)
    auth.require_board_access(repos, board.id, mentor)  # доступ є

    # Act
    mentors.revoke_mentor(
        board_id=board.id, mentor_id=mentor.id, user=candidate, repos=repos
    )

    # Assert
    saved = repos.mentors.get(invitation.id)
    assert saved.status == MentorStatus.revoked.value
    assert saved.accepted_at is None
    with pytest.raises(ForbiddenError):
        auth.require_board_access(repos, board.id, mentor)

# US-002
def test_revoke_mentor_raises_not_found_when_mentor_was_not_invited(
    repos, board, candidate
):
    # Act & Assert
    with pytest.raises(NotFoundError):
        mentors.revoke_mentor(
            board_id=board.id, mentor_id=uuid4(), user=candidate, repos=repos
        )

# US-002
def test_revoke_mentor_forbidden_for_mentor(repos, board, mentor, make_invitation):
    # Arrange
    make_invitation(mentor, MentorStatus.accepted)

    # Act & Assert
    with pytest.raises(ForbiddenError):
        mentors.revoke_mentor(
            board_id=board.id, mentor_id=mentor.id, user=mentor, repos=repos
        )


# --------------------------------------------------------------------------- #
# Read-only доступ ментора до карток (справжня перевірка доступу, без підмін)
# --------------------------------------------------------------------------- #


@pytest.fixture
def invited_mentor(mentor, make_invitation) -> User:
    make_invitation(mentor, MentorStatus.accepted)
    return mentor

# US-002
def test_02_mentor_cannot_edit_card(repos, board, card, invited_mentor):
    # Arrange
    payload = CardUpdate(position="New Position")

    # Act & Assert
    with pytest.raises(ForbiddenError):
        cards_router.update_card(
            payload=payload,
            board_id=board.id,
            card_id=card.id,
            user=invited_mentor,
            repos=repos,
        )
    assert repos.cards.get(card.id).position == "Backend Engineer"

# US-002
def test_08_mentor_cannot_change_company_field(repos, board, card, invited_mentor):
    # Arrange
    payload = CardUpdate(company="Нова Компанія")

    # Act & Assert
    with pytest.raises(ForbiddenError):
        cards_router.update_card(
            payload=payload,
            board_id=board.id,
            card_id=card.id,
            user=invited_mentor,
            repos=repos,
        )
    assert repos.cards.get(card.id).company == "Acme Corp"

# US-008
def test_owner_can_edit_card(repos, board, card, candidate):
    # Контрольний тест: той самий виклик для власника дошки успішний,
    # тож відмова ментору в тестах вище спричинена саме роллю, а не помилкою даних.
    # Arrange
    payload = CardUpdate(position="Senior Backend Engineer")

    # Act
    cards_router.update_card(
        payload=payload,
        board_id=board.id,
        card_id=card.id,
        user=candidate,
        repos=repos,
    )

    # Assert
    assert repos.cards.get(card.id).position == "Senior Backend Engineer"

# US-002
def test_send_invitation_email_raises_error_if_no_token(monkeypatch):
    monkeypatch.setattr(mentors_router_module, "MAILTRAP_API_TOKEN", None)

    with pytest.raises(RuntimeError, match="MAILTRAP_API_TOKEN не задано"):
        mentors_router_module._send_invitation_email(
            email="test@example.com", 
            token="dummy-token", 
            board_id=uuid4()
        )

# US-002
def test_send_invitation_email_raises_service_unavailable_on_mailtrap_error(monkeypatch):
    monkeypatch.setattr(mentors_router_module, "MAILTRAP_API_TOKEN", "fake-token")

    mock_client_instance = MagicMock()
    mock_client_instance.send.side_effect = Exception("Mailtrap API timeout")
    
    mock_client_class = MagicMock(return_value=mock_client_instance)
    monkeypatch.setattr(mentors_router_module.mt, "MailtrapClient", mock_client_class)

    with pytest.raises(ServiceUnavailableError, match="Не вдалося надіслати запрошення"):
        mentors_router_module._send_invitation_email(
            email="test@example.com", 
            token="dummy-token", 
            board_id=uuid4()
        )

# US-002
def test_invite_mentor_rejects_invalid_email_format():
    with pytest.raises(ValidationError) as exc_info:
        InviteMentorRequest(email="invalid-email-format")
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert errors[0]["loc"] == ("email",)