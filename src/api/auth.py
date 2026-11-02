from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import LoginAttempts, Repos
from .domain import DEFAULT_STAGE_NAMES, Board, Stage, User
from .errors import (
    ConflictError,
    ForbiddenError,
    UnauthorizedError,
    auth_error_responses,
)
from .repositories.base import Repositories
from .schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    UserRole,
    ChangePasswordRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer = HTTPBearer(auto_error=False)
TOKEN_TTL = timedelta(hours=24)

# Brute-force protection: after MAX_FAILED_ATTEMPTS consecutive wrong
# passwords login is blocked for LOCKOUT_DURATION, then a new window starts.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def _secret() -> str:
    return os.getenv("JWT_SECRET", "development-only-change-me-32-bytes!")


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"{salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split("$", 1)
        expected = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), 210_000
        ).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(expected, digest_hex)


def _public_user(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
    )


def _issue_token(user: User) -> TokenResponse:
    expires_at = datetime.now(timezone.utc) + TOKEN_TTL
    token = jwt.encode(
        {"sub": str(user.id), "exp": expires_at, "role": user.role},
        _secret(),
        algorithm="HS256",
    )
    return TokenResponse(
        access_token=token,
        expires_in=int(TOKEN_TTL.total_seconds()),
        user=_public_user(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    responses=auth_error_responses(
        conflict="Користувач із таким email уже існує",
        forbidden="Реєстрація доступна лише для ролі кандидата",
    ),
)
def register(payload: RegisterRequest, repos: Repos) -> TokenResponse:
    if payload.role != UserRole.candidate:
        raise ForbiddenError("Реєстрація доступна лише для ролі кандидата")
    email = str(payload.email).lower()
    if repos.users.get_by_email(email) is not None:
        raise ConflictError("Користувач із таким email уже існує")
    user = repos.users.add(
        User(
            email=email,
            password_hash=_hash_password(payload.password),
            role=payload.role.value,
        )
    )
    board = repos.boards.add(Board(owner_id=user.id))
    for order_index, name in enumerate(DEFAULT_STAGE_NAMES):
        repos.stages.add(Stage(board_id=board.id, name=name, order_index=order_index))
    return _issue_token(user)


def _locked_error(locked_until: datetime | None) -> ForbiddenError:
    if locked_until is None:
        return ForbiddenError("Обліковий запис тимчасово заблоковано")
    return ForbiddenError(
        "Обліковий запис тимчасово заблоковано до "
        f"{locked_until:%H:%M} UTC. Спробуйте пізніше"
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    responses=auth_error_responses(forbidden="Обліковий запис тимчасово заблоковано"),
)
def login(
    payload: LoginRequest, repos: Repos, attempts: LoginAttempts
) -> TokenResponse:
    user = repos.users.get_by_email(str(payload.email).lower())
    if user is None or not user.is_active:
        raise UnauthorizedError("Невірний email або пароль")

    now = datetime.now(timezone.utc)
    if user.locked_until is not None:
        # Stored in UTC; a backend without time zones (SQLite) returns it naive.
        locked_until = user.locked_until.replace(
            tzinfo=user.locked_until.tzinfo or timezone.utc
        )
        if locked_until > now:
            raise _locked_error(locked_until)
        # The lock has expired: a new window of MAX_FAILED_ATTEMPTS starts.
        attempts.reset(user.id)

    # The attempt is counted before the slow password check, so a burst of
    # parallel requests gets at most MAX_FAILED_ATTEMPTS password checks.
    attempt = attempts.register_attempt(
        user.id, lock_at=MAX_FAILED_ATTEMPTS, lock_until=now + LOCKOUT_DURATION
    )
    if attempt > MAX_FAILED_ATTEMPTS:
        raise _locked_error(None)
    if not _verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Невірний email або пароль")
    attempts.reset(user.id)
    return _issue_token(user)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    repos: Repos,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Потрібен Bearer-токен")
    try:
        payload = jwt.decode(credentials.credentials, _secret(), algorithms=["HS256"])
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise UnauthorizedError("Недійсний або прострочений токен")
    user = repos.users.get(user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError(
            "Користувача не знайдено або обліковий запис заблоковано"
        )
    return user


def require_roles(*roles: UserRole):
    allowed = {role.value for role in roles}

    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed:
            raise ForbiddenError("Недостатньо прав для виконання цієї дії")
        return user

    return dependency


CurrentUser = Annotated[User, Depends(get_current_user)]
CandidateOrAdmin = Annotated[
    User, Depends(require_roles(UserRole.candidate, UserRole.admin))
]


def require_board_access(
    repos: Repositories, board_id: UUID, user: User, *, write: bool = False
) -> None:
    board = repos.boards.get(board_id)
    if board is None:
        raise ForbiddenError("Доступ до дошки заборонено")
    if user.role == UserRole.admin.value:
        return
    if board.owner_id == user.id and user.role == UserRole.candidate.value:
        return
    if (
        user.role == UserRole.mentor.value
        and not write
        and repos.boards.mentor_has_access(board_id, user.id)
    ):
        return
    raise ForbiddenError("Доступ до дошки заборонено")


# TDD - User password change after confirming current password and check for the same password
@router.post(
    "/change-password",
    response_model=TokenResponse,
    responses=auth_error_responses(
        conflict="Новий пароль не може дорівнювати поточному"
    ),
)
def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, repos: Repos
) -> TokenResponse:
    if not _verify_password(payload.current_password, user.password_hash):
        raise UnauthorizedError("Невірний пароль")
    if payload.current_password == payload.new_password:
        raise ConflictError("Новий пароль не може дорівнювати поточному")

    user.password_hash = _hash_password(payload.new_password)
    repos.users.save(user)
    return _issue_token(user)
