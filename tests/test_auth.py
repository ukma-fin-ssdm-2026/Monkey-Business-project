"""
Інструмент: Claude
Застосування: Написання модульних тестів для src/api/auth.py: хешування паролів,
видача та перевірка JWT, реєстрація і вхід (FR-001), перевірка ролей (FR-002)
та доступу до дошки, зокрема read-only доступ ментора (FR-012, FR-014).
Верифікація: Тести запущено через pytest; кожен сценарій звірено з гілками
коду auth.py вручну.

Тести викликають функції auth.py напряму, без HTTP і бази даних: репозиторії
користувачів, дошок і етапів замінено in-memory фейками, а для перевірки
взаємодій у require_board_access використано Mock.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials

from src.api import auth
from src.api.domain import DEFAULT_STAGE_NAMES, Board, User
from src.api.errors import ConflictError, ForbiddenError, UnauthorizedError
from src.api.repositories.base import Repositories
from src.api.schemas import (
    LoginRequest,
    RegisterRequest,
    UserOut,
    UserRole,
    ChangePasswordRequest,
)

TEST_SECRET = "unit-test-jwt-secret-at-least-32-bytes"  # pragma: allowlist secret
OTHER_SECRET = "some-other-jwt-secret-at-least-32-bytes"  # pragma: allowlist secret
PASSWORD = "correct-horse-battery"  # pragma: allowlist secret
TTL_SECONDS = 24 * 60 * 60


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


def _repositories(*, users=None, boards=None, stages=None) -> Repositories:
    return Repositories(
        users=users, boards=boards, stages=stages, cards=None, links=None, notes=None
    )


def _user(role: str = "candidate", **fields) -> User:
    return User(
        email="user@example.com",
        password_hash="unused",  # pragma: allowlist secret
        role=role,
        **fields,
    )


def _encode(claims: dict, secret: str = TEST_SECRET) -> str:
    return jwt.encode(claims, secret, algorithm="HS256")


def _from_now(**delta) -> datetime:
    return datetime.now(timezone.utc) + timedelta(**delta)


def _bearer(token: str, scheme: str = "Bearer") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme=scheme, credentials=token)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch) -> str:
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    return TEST_SECRET


@pytest.fixture
def repos() -> Repositories:
    return _repositories(
        users=InMemoryUserRepository(),
        boards=InMemoryRepository(),
        stages=InMemoryRepository(),
    )


@pytest.fixture
def make_user(repos):
    def _make(email="user@example.com", role="candidate", is_active=True) -> User:
        return repos.users.add(
            User(
                email=email,
                password_hash=auth._hash_password(PASSWORD),
                role=role,
                is_active=is_active,
            )
        )

    return _make


# --------------------------------------------------------------------------- #
# Хешування паролів
# --------------------------------------------------------------------------- #


def test_verify_password_accepts_original_password():
    encoded = auth._hash_password(PASSWORD)

    assert auth._verify_password(PASSWORD, encoded) is True


def test_verify_password_rejects_wrong_password():
    encoded = auth._hash_password(PASSWORD)

    assert auth._verify_password("wrong-password", encoded) is False


def test_hash_password_uses_random_salt_per_call():
    first = auth._hash_password(PASSWORD)
    second = auth._hash_password(PASSWORD)

    assert first != second
    assert auth._verify_password(PASSWORD, first)
    assert auth._verify_password(PASSWORD, second)


def test_hash_password_with_fixed_salt_is_deterministic_salt_and_digest():
    salt = bytes(range(16))

    encoded = auth._hash_password(PASSWORD, salt)

    salt_hex, digest_hex = encoded.split("$")
    assert salt_hex == salt.hex()
    assert len(digest_hex) == 64
    assert encoded == auth._hash_password(PASSWORD, salt)
    assert PASSWORD not in encoded


@pytest.mark.parametrize(
    "password",
    ["пароль-кандидата", "  spaces around  ", "x" * 128],
    ids=["non-ascii", "whitespace", "max-length"],
)
def test_verify_password_round_trips_unusual_passwords(password):
    encoded = auth._hash_password(password)

    assert auth._verify_password(password, encoded) is True
    assert auth._verify_password(password.strip() + "!", encoded) is False


@pytest.mark.parametrize(
    "encoded",
    ["", "no-separator", "not-hex$00ff", "abc$00ff", "$", "00ff$"],
    ids=[
        "empty",
        "no-separator",
        "non-hex-salt",
        "odd-length-salt",
        "empty-parts",
        "empty-digest",
    ],
)
def test_verify_password_returns_false_for_malformed_hash(encoded):
    assert auth._verify_password(PASSWORD, encoded) is False


# --------------------------------------------------------------------------- #
# Секрет і видача токена
# --------------------------------------------------------------------------- #


def test_secret_is_read_from_environment(jwt_secret):
    assert auth._secret() == jwt_secret


def test_secret_falls_back_to_development_default(monkeypatch):
    monkeypatch.delenv("JWT_SECRET")

    secret = auth._secret()

    # PyJWT warns about HMAC keys shorter than the 32 bytes of the SHA-256 output.
    assert len(secret.encode()) >= 32


def test_issue_token_encodes_subject_role_and_expiry(jwt_secret):
    user = _user(role="mentor")
    before = int(time.time())

    response = auth._issue_token(user)

    after = int(time.time())
    claims = jwt.decode(response.access_token, jwt_secret, algorithms=["HS256"])
    assert claims["sub"] == str(user.id)
    assert claims["role"] == "mentor"
    assert before + TTL_SECONDS <= claims["exp"] <= after + TTL_SECONDS
    assert response.expires_in == TTL_SECONDS
    assert response.token_type == "bearer"


def test_issue_token_returns_public_user_without_password_hash():
    user = _user(role="admin", is_active=False)

    response = auth._issue_token(user)

    assert response.user == UserOut(
        id=user.id, email=user.email, role=UserRole.admin, is_active=False
    )
    assert "password_hash" not in response.user.model_dump()


# --------------------------------------------------------------------------- #
# Реєстрація
# --------------------------------------------------------------------------- #


def test_register_stores_candidate_with_lowercased_email_and_hashed_password(
    repos, jwt_secret
):
    payload = RegisterRequest(email="New.User@Example.com", password=PASSWORD)

    response = auth.register(payload, repos)

    stored = repos.users.get(response.user.id)
    assert stored.email == "new.user@example.com"
    assert stored.role == "candidate"
    assert stored.password_hash != PASSWORD
    assert auth._verify_password(PASSWORD, stored.password_hash)
    claims = jwt.decode(response.access_token, jwt_secret, algorithms=["HS256"])
    assert claims["sub"] == str(stored.id)


def test_register_creates_board_with_default_stages_in_order(repos):
    payload = RegisterRequest(email="new@example.com", password=PASSWORD)

    response = auth.register(payload, repos)

    [board] = repos.boards.items.values()
    assert board.owner_id == response.user.id
    stages = sorted(repos.stages.items.values(), key=lambda s: s.order_index)
    assert [s.name for s in stages] == DEFAULT_STAGE_NAMES
    assert [s.order_index for s in stages] == list(range(len(DEFAULT_STAGE_NAMES)))
    assert all(s.board_id == board.id for s in stages)


@pytest.mark.parametrize("role", [UserRole.mentor, UserRole.admin])
def test_register_rejects_non_candidate_roles(repos, role):
    payload = RegisterRequest(email="new@example.com", password=PASSWORD, role=role)

    with pytest.raises(ForbiddenError):
        auth.register(payload, repos)

    assert repos.users.items == {}
    assert repos.boards.items == {}


def test_register_rejects_existing_email_regardless_of_case(repos, make_user):
    existing = make_user(email="taken@example.com")
    payload = RegisterRequest(email="TAKEN@example.com", password=PASSWORD)

    with pytest.raises(ConflictError):
        auth.register(payload, repos)

    assert list(repos.users.items.values()) == [existing]
    assert repos.boards.items == {}


# --------------------------------------------------------------------------- #
# Вхід
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("email", ["user@example.com", "USER@example.com"])
def test_login_returns_token_for_valid_credentials(repos, make_user, email):
    user = make_user(email="user@example.com")

    response = auth.login(LoginRequest(email=email, password=PASSWORD), repos)

    assert response.user.id == user.id
    assert response.access_token


@pytest.mark.parametrize(
    ("email", "password", "is_active"),
    [
        ("ghost@example.com", PASSWORD, True),
        ("user@example.com", "wrong-password", True),
        ("user@example.com", PASSWORD, False),
    ],
    ids=["unknown-email", "wrong-password", "blocked-user"],
)
def test_login_rejects_bad_credentials_with_one_generic_error(
    repos, make_user, email, password, is_active
):
    make_user(email="user@example.com", is_active=is_active)
    payload = LoginRequest(email=email, password=password)

    with pytest.raises(UnauthorizedError) as exc_info:
        auth.login(payload, repos)

    # One message for every case, so the response does not reveal which emails exist.
    assert exc_info.value.message == "Невірний email або пароль"


# --------------------------------------------------------------------------- #
# Поточний користувач за токеном
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
def test_get_current_user_returns_user_for_valid_token(repos, make_user, scheme):
    user = make_user()
    token = auth._issue_token(user).access_token

    assert auth.get_current_user(_bearer(token, scheme), repos) is user


@pytest.mark.parametrize(
    "credentials",
    [None, _bearer("dXNlcjpwYXNz", scheme="Basic")],
    ids=["missing", "basic-scheme"],
)
def test_get_current_user_requires_bearer_credentials(repos, credentials):
    with pytest.raises(UnauthorizedError, match="Потрібен Bearer-токен"):
        auth.get_current_user(credentials, repos)


INVALID_TOKENS = {
    "garbage": lambda sub: "not-a-jwt",
    "wrong-secret": lambda sub: _encode(
        {"sub": sub, "exp": _from_now(hours=1)}, OTHER_SECRET
    ),
    "expired": lambda sub: _encode({"sub": sub, "exp": _from_now(seconds=-1)}),
    "alg-none": lambda sub: jwt.encode({"sub": sub}, None, algorithm="none"),
    "missing-sub": lambda sub: _encode({"exp": _from_now(hours=1)}),
    "sub-not-uuid": lambda sub: _encode({"sub": "not-a-uuid"}),
    "sub-not-string": lambda sub: _encode({"sub": 42}),
}


@pytest.mark.parametrize(
    "make_token", INVALID_TOKENS.values(), ids=list(INVALID_TOKENS.keys())
)
def test_get_current_user_rejects_invalid_token(repos, make_user, make_token):
    user = make_user()
    token = make_token(str(user.id))

    with pytest.raises(UnauthorizedError, match="Недійсний або прострочений токен"):
        auth.get_current_user(_bearer(token), repos)


def test_get_current_user_rejects_token_of_unknown_user(repos):
    never_stored = _user()
    token = auth._issue_token(never_stored).access_token

    with pytest.raises(UnauthorizedError, match="не знайдено"):
        auth.get_current_user(_bearer(token), repos)


def test_get_current_user_rejects_blocked_user_with_valid_token(repos, make_user):
    user = make_user(is_active=False)
    token = auth._issue_token(user).access_token

    with pytest.raises(UnauthorizedError, match="заблоковано"):
        auth.get_current_user(_bearer(token), repos)


# --------------------------------------------------------------------------- #
# Перевірка ролей і доступу до дошки
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("role", "allowed"),
    [("candidate", True), ("admin", True), ("mentor", False)],
)
def test_require_roles_allows_only_listed_roles(role, allowed):
    dependency = auth.require_roles(UserRole.candidate, UserRole.admin)
    user = _user(role=role)

    if allowed:
        assert dependency(user) is user
    else:
        with pytest.raises(ForbiddenError):
            dependency(user)


@pytest.fixture
def boards():
    return Mock(spec=["get", "mentor_has_access"])


def test_require_board_access_denies_missing_board_even_for_admin(boards):
    boards.get.return_value = None

    with pytest.raises(ForbiddenError):
        auth.require_board_access(
            _repositories(boards=boards), uuid4(), _user(role="admin")
        )


@pytest.mark.parametrize(
    ("role", "is_owner", "mentor_invited", "write", "allowed"),
    [
        ("admin", False, False, False, True),
        ("admin", False, False, True, True),
        ("candidate", True, False, False, True),
        ("candidate", True, False, True, True),
        ("candidate", False, False, False, False),
        ("mentor", False, True, False, True),
        ("mentor", False, True, True, False),
        ("mentor", False, False, False, False),
    ],
    ids=[
        "admin-read",
        "admin-write",
        "owner-read",
        "owner-write",
        "other-candidate-read",
        "invited-mentor-read",
        "invited-mentor-write",
        "uninvited-mentor-read",
    ],
)
def test_require_board_access_role_matrix(
    boards, role, is_owner, mentor_invited, write, allowed
):
    user = _user(role=role)
    board = Board(owner_id=user.id if is_owner else uuid4())
    boards.get.return_value = board
    boards.mentor_has_access.return_value = mentor_invited
    repos = _repositories(boards=boards)

    if allowed:
        assert auth.require_board_access(repos, board.id, user, write=write) is None
    else:
        with pytest.raises(ForbiddenError):
            auth.require_board_access(repos, board.id, user, write=write)


def test_require_board_access_checks_mentor_invitation_for_this_board(boards):
    mentor = _user(role="mentor")
    board = Board(owner_id=uuid4())
    boards.get.return_value = board
    boards.mentor_has_access.return_value = True

    auth.require_board_access(_repositories(boards=boards), board.id, mentor)

    boards.get.assert_called_once_with(board.id)
    boards.mentor_has_access.assert_called_once_with(board.id, mentor.id)


@pytest.mark.parametrize("role", ["admin", "candidate"])
def test_require_board_access_skips_invitation_lookup_for_non_mentors(boards, role):
    user = _user(role=role)
    boards.get.return_value = Board(owner_id=user.id)

    auth.require_board_access(_repositories(boards=boards), uuid4(), user, write=True)

    boards.mentor_has_access.assert_not_called()


def test_change_password_success(repos, make_user):
    user = make_user(email="user@example.com")
    payload = ChangePasswordRequest(current_password=PASSWORD, new_password="abcd12345")
    response = auth.change_password(payload, user, repos)

    assert response.user.id == user.id
    assert auth._verify_password("abcd12345", user.password_hash)


def test_change_password_rejects_wrong_current_password(repos, make_user):
    user = make_user(email="user@example.com")
    payload = ChangePasswordRequest(
        current_password="wrong_password", new_password="abcd12345"
    )
    with pytest.raises(UnauthorizedError, match="Невірний пароль"):
        auth.change_password(payload, user, repos)


def test_change_password_rejects_same_password(repos, make_user):
    user = make_user(email="user@example.com")
    payload = ChangePasswordRequest(current_password=PASSWORD, new_password=PASSWORD)
    with pytest.raises(
        ConflictError, match="Новий пароль не може дорівнювати поточному"
    ):
        auth.change_password(payload, user, repos)


def test_login_increments_failed_attempts_on_wrong_password(repos, make_user):
    user = make_user(email="user@example.com")

    with pytest.raises(UnauthorizedError):
        auth.login(LoginRequest(email=user.email, password="wrong"), repos)

    assert repos.users.get(user.id).failed_login_attempts == 1


def test_login_rejects_locked_account_even_with_correct_password(repos, make_user):
    user = make_user(email="user@example.com")
    user.failed_login_attempts = auth.MAX_FAILED_ATTEMPTS
    repos.users.save(user)

    with pytest.raises(ForbiddenError, match="заблоковано"):
        auth.login(LoginRequest(email=user.email, password=PASSWORD), repos)


def test_login_resets_failed_attempts_on_success(repos, make_user):
    user = make_user(email="user@example.com")
    user.failed_login_attempts = 3
    repos.users.save(user)

    auth.login(LoginRequest(email=user.email, password=PASSWORD), repos)

    assert repos.users.get(user.id).failed_login_attempts == 0
