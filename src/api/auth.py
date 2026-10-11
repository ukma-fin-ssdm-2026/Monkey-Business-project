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

from . import store
from .errors import ConflictError, ForbiddenError, UnauthorizedError
from .schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut, UserRole

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer = HTTPBearer(auto_error=False)
TOKEN_TTL = timedelta(hours=24)


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


def _public_user(user: dict) -> UserOut:
    return UserOut(
        id=user["id"],
        email=user["email"],
        role=user["role"],
        is_active=user["is_active"],
    )


def _issue_token(user: dict) -> TokenResponse:
    expires_at = datetime.now(timezone.utc) + TOKEN_TTL
    token = jwt.encode(
        {"sub": str(user["id"]), "exp": expires_at, "role": user["role"]},
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
    responses={409: {"description": "Email is already registered"}},
)
def register(payload: RegisterRequest) -> TokenResponse:
    if payload.role != UserRole.candidate:
        raise ForbiddenError("Реєстрація доступна лише для ролі кандидата")
    if store.get_user_by_email(str(payload.email)) is not None:
        raise ConflictError("Користувач із таким email уже існує")
    user = store.create_user(
        str(payload.email), _hash_password(payload.password), payload.role.value
    )
    store.create_board(user["id"])
    return _issue_token(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"description": "Invalid credentials"}},
)
def login(payload: LoginRequest) -> TokenResponse:
    user = store.get_user_by_email(str(payload.email))
    if (
        user is None
        or not user["is_active"]
        or not _verify_password(payload.password, user["password_hash"])
    ):
        raise UnauthorizedError("Невірний email або пароль")
    return _issue_token(user)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Потрібен Bearer-токен")
    try:
        payload = jwt.decode(credentials.credentials, _secret(), algorithms=["HS256"])
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise UnauthorizedError("Недійсний або прострочений токен")
    user = store.get_user(user_id)
    if user is None or not user["is_active"]:
        raise UnauthorizedError(
            "Користувача не знайдено або обліковий запис заблоковано"
        )
    return user


def require_roles(*roles: UserRole):
    allowed = {role.value for role in roles}

    def dependency(user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if user["role"] not in allowed:
            raise ForbiddenError("Недостатньо прав для виконання цієї дії")
        return user

    return dependency


CurrentUser = Annotated[dict, Depends(get_current_user)]
CandidateOrAdmin = Annotated[
    dict, Depends(require_roles(UserRole.candidate, UserRole.admin))
]


def require_board_access(board_id: UUID, user: dict, *, write: bool = False) -> None:
    board = store.get_board(board_id)
    if board is None:
        raise ForbiddenError("Доступ до дошки заборонено")
    if user["role"] == UserRole.admin.value:
        return
    if board["owner_id"] is None and user["role"] == UserRole.candidate.value:
        store.claim_demo_board(user["id"])
        return
    if board["owner_id"] == user["id"] and user["role"] == UserRole.candidate.value:
        return
    if (
        user["role"] == UserRole.mentor.value
        and not write
        and store.has_board_access(board_id, user["id"])
    ):
        return
    raise ForbiddenError("Доступ до дошки заборонено")
