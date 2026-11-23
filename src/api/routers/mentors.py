"""
Інструмент: Claude
Застосування: Створення REST-роутерів для керування менторами та запрошеннями до дошки (FR-012, US-002).
Верифікація: Перевірено валідацію вхідних даних (Pydantic), коди помилок (401, 403, 404, 409, 422),
статуси запрошень (pending, accepted) та обмеження доступу.

Ресурси:
- Mentors (`/boards/{board_id}/mentors`): надсилання запрошень кандидатом та перегляд списку менторів.
- Invitations (`/invitations`): перегляд та прийняття запрошення ментором.
Покриває FR-012 (запрошення ментора за email із посиланням, доступ «перегляд і коментарі»).

Доповнення Лаб06: Codex — регресійні тести та виправлення виявленого дефекту.
Доповнення: Claude — адреса фронтенду в посиланні-запрошенні береться з FRONTEND_URL,
щоб після деплою (Azure Static Web Apps) лист не вів на localhost.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta, timezone
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from fastapi.security import HTTPAuthorizationCredentials
import mailtrap as mt
import os
import requests

from ..auth import (
    CandidateOrAdmin,
    CurrentUser,
    _hash_password,
    _issue_token,
    bearer,
    get_current_user,
)
from ..db import Repos
from ..domain import BoardMentor, User, utcnow
from ..errors import (
    DOCS_BASE,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
    error_responses,
)
from ..schemas import (
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    BoardMentorOut,
    InviteMentorRequest,
    MentorStatus,
    UserRole,
)
from .card_access import require_board

MAILTRAP_API_TOKEN = os.getenv("MAILTRAP_API_TOKEN")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
INVITATION_TTL = timedelta(days=7)

# Provider details (URLs, inbox id, raw API answers) go to the log only;
# the client gets this message and the request_id (CWE-209).
EMAIL_UNAVAILABLE_MESSAGE = (
    "Не вдалося надіслати лист із запрошенням. Запрошення не створено, "
    "спробуйте пізніше"
)

logger = logging.getLogger(__name__)

mentors_router = APIRouter(prefix="/boards/{board_id}/mentors", tags=["Mentors"])
invitations_router = APIRouter(prefix="/invitations", tags=["Invitations"])


def _expires_at(invitation: BoardMentor):
    invited_at = invitation.invited_at
    return invited_at.replace(tzinfo=invited_at.tzinfo or timezone.utc) + INVITATION_TTL


def _pending(invitation: BoardMentor | None) -> bool:
    return (
        invitation is not None
        and invitation.status == MentorStatus.pending.value
        and _expires_at(invitation) > utcnow()
    )


def _to_mentor_out(
    invitation: BoardMentor,
    email: str,
    *,
    expose_token: bool = True,
    requires_password: bool = False,
) -> BoardMentorOut:
    return BoardMentorOut(
        id=invitation.id,
        board_id=invitation.board_id,
        mentor_id=invitation.mentor_id,
        email=email,
        status=MentorStatus(invitation.status),
        invite_token=invitation.invite_token if expose_token else None,
        invited_at=invitation.invited_at,
        accepted_at=invitation.accepted_at,
        expires_at=_expires_at(invitation),
        requires_password=requires_password,
    )


def _send_invitation_email(email: str, token: str, board_id: UUID) -> None:
    """Відправка email із посиланням-запрошенням через API Mailtrap.

    Швидка відмова: без листа ментор не дізнається про запрошення, тож
    ServiceUnavailableError відкочує транзакцію і запис не створюється.
    """

    if not MAILTRAP_API_TOKEN:
        logger.error(
            "MAILTRAP_API_TOKEN is not set, invitation email for board %s "
            "was not sent; add it to .env and restart the container",
            board_id,
        )
        raise ServiceUnavailableError(EMAIL_UNAVAILABLE_MESSAGE)

    sender = os.getenv("MAIL_FROM_EMAIL", "").strip()
    mode = os.getenv("MAILTRAP_SANDBOX", "false").lower()
    inbox_id = os.getenv("MAILTRAP_INBOX_ID", "").strip()
    if not sender or mode not in {"true", "false"} or (mode == "true" and not inbox_id):
        logger.error("Invitation email configuration is incomplete or invalid")
        raise ServiceUnavailableError(EMAIL_UNAVAILABLE_MESSAGE)

    invite_url = f"{FRONTEND_URL}/invitations/{token}"
    mail = mt.Mail(
        sender=mt.Address(
            email=sender, name=os.getenv("MAIL_FROM_NAME", "Interview Board")
        ),
        to=[mt.Address(email=email)],
        subject="Запрошення до дошки",
        text=(
            f"Привіт!\n\n"
            f"Вас запросили до дошки (ID: {board_id}).\n"
            f"Щоб приєднатися, перейдіть за цим посиланням:\n"
            f"{invite_url}\n\n"
        ),
        category="Mentor invitation",
    )

    try:
        client = mt.MailtrapClient(
            token=MAILTRAP_API_TOKEN,
            sandbox=mode == "true",
            inbox_id=inbox_id if mode == "true" else None,
        )
        client.send(mail)
    # Only provider and network failures; a bug in our own code (TypeError
    # while building the mail) must surface as a 500, not hide behind a 503.
    except (mt.MailtrapError, requests.RequestException) as e:
        logger.warning(
            "Mailtrap failed to send invitation for board %s: %s", board_id, e
        )
        raise ServiceUnavailableError(EMAIL_UNAVAILABLE_MESSAGE) from e
    logger.info("Invitation email sent for board %s", board_id)


@mentors_router.post(
    "",
    response_model=BoardMentorOut,
    status_code=status.HTTP_201_CREATED,
    summary="Запросити ментора до дошки",
    description=(
        "Кандидат надсилає запрошення ментору за вказаним email. "
        "Система надсилає лист із посиланням-запрошенням і створює запис зі статусом pending."
    ),
    responses=error_responses(
        not_found="Дошку не знайдено",
        conflict="Ментор уже має доступ або запрошення вже очікує підтвердження",
    ),
)
def invite_mentor(
    payload: InviteMentorRequest,
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    user: CandidateOrAdmin = None,
    repos: Repos = None,
) -> BoardMentorOut:
    require_board(repos, board_id, user, write=True)

    email = str(payload.email).lower()
    if email == user.email.lower():
        raise ConflictError("Не можна запросити самого себе як ментора")

    mentor = repos.users.get_by_email(email)
    if mentor is None:
        mentor = repos.users.add(
            User(
                email=email,
                # Password is set on invitation acceptance.
                password_hash="",  # nosec B106
                role=UserRole.mentor.value,
                is_active=True,
            )
        )
    elif mentor.role != UserRole.mentor.value:
        raise ConflictError("Користувач із таким email зареєстрований з іншою роллю")
    if not mentor.is_active:
        raise ForbiddenError("Обліковий запис ментора заблоковано")

    existing = repos.mentors.get_by_board_and_mentor(
        board_id, mentor.id, for_update=True
    )
    if existing is not None:
        if existing.status == MentorStatus.accepted.value:
            raise ConflictError("Цей ментор уже має доступ до дошки")
        if _pending(existing):
            raise ConflictError("Запрошення для цього ментора вже очікує підтвердження")
        if existing.status in {MentorStatus.revoked.value, MentorStatus.pending.value}:
            existing.status = MentorStatus.pending.value
            existing.invite_token = secrets.token_urlsafe(32)
            existing.invited_at = utcnow()
            existing.accepted_at = None
            invitation = repos.mentors.save(existing)
            _send_invitation_email(email, invitation.invite_token, board_id)
            return _to_mentor_out(invitation, email)

    token = secrets.token_urlsafe(32)
    invitation = repos.mentors.add(
        BoardMentor(
            board_id=board_id,
            mentor_id=mentor.id,
            invite_token=token,
            status=MentorStatus.pending.value,
        )
    )
    _send_invitation_email(email, token, board_id)
    return _to_mentor_out(invitation, email)


@mentors_router.get(
    "",
    response_model=list[BoardMentorOut],
    status_code=status.HTTP_200_OK,
    summary="Список менторів дошки",
    description=(
        "Повертає список запрошених менторів для дошки зі статусами запрошень (FR-012, US-002)."
    ),
    responses=error_responses("Дошку не знайдено"),
)
def list_board_mentors(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    user: CurrentUser = None,
    repos: Repos = None,
) -> list[BoardMentorOut]:
    require_board(repos, board_id, user)
    invitations = repos.mentors.list_for_board(board_id)

    result = []
    for inv in invitations:
        mentor = repos.users.get(inv.mentor_id)
        if mentor is not None:
            result.append(
                _to_mentor_out(
                    inv, mentor.email, expose_token=user.role != UserRole.mentor.value
                )
            )
    return result


@invitations_router.get(
    "/{token}",
    response_model=BoardMentorOut,
    status_code=status.HTTP_200_OK,
    summary="Перевірити запрошення за токеном",
    description=(
        "Отримує інформацію про запрошення за одноразовим токеном перед його прийняттям (FR-012)."
    ),
    responses=error_responses("Запрошення не знайдено"),
)
def get_invitation(
    token: str = Path(..., description="Токен запрошення"),
    repos: Repos = None,
) -> BoardMentorOut:
    invitation = repos.mentors.get_by_token(token)
    if not _pending(invitation):
        raise NotFoundError("Запрошення не знайдено або термін його дії минув")
    mentor = repos.users.get(invitation.mentor_id)
    if mentor is None or not mentor.is_active or mentor.role != UserRole.mentor.value:
        raise NotFoundError("Користувача для цього запрошення не знайдено")
    return _to_mentor_out(
        invitation, mentor.email, requires_password=not mentor.password_hash
    )


@invitations_router.post(
    "/{token}/accept",
    response_model=AcceptInvitationResponse,
    status_code=status.HTTP_200_OK,
    summary="Прийняти запрошення до дошки",
    description=(
        "Ментор приймає запрошення за посиланням із токеном (FR-012, US-002). "
        "Після прийняття ментор бачить дошку в режимі «перегляд і коментарі». "
        "Якщо ментор ще не встановив пароль, він може надати його в тілі запиту."
    ),
    responses=error_responses(
        not_found="Запрошення не знайдено або термін його дії минув",
        examples={
            403: {
                "forbidden": {
                    "summary": "Недійсне або прострочене запрошення",
                    "value": {
                        "error": {
                            "code": "FORBIDDEN",
                            "message": "Недійсне або прострочене запрошення",
                            "details": [],
                            "request_id": "req_example",
                            "documentation": f"{DOCS_BASE}#error-handling",
                        }
                    },
                }
            }
        },
    ),
)
def accept_invitation(
    token: str = Path(..., description="Токен запрошення"),
    payload: Optional[AcceptInvitationRequest] = None,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
    repos: Repos = None,
) -> AcceptInvitationResponse:
    # Keep the invitation and account locked until the request transaction commits.
    # The user lock also protects activation through two different invitations.
    invitation = repos.mentors.get_by_token(token, for_update=True)
    if not _pending(invitation):
        raise ForbiddenError("Недійсне або прострочене запрошення")

    access_token: Optional[str] = None
    token_response = None
    mentor = repos.users.get_for_update(invitation.mentor_id)
    if mentor is None:
        raise ForbiddenError("Користувача для цього запрошення не знайдено")
    if not mentor.is_active or mentor.role != UserRole.mentor.value:
        raise ForbiddenError("Обліковий запис ментора недоступний")

    if credentials is not None:
        user = get_current_user(credentials, repos)
        if user.role != UserRole.mentor.value:
            raise ForbiddenError("Лише ментор може прийняти запрошення")
        if mentor.id != user.id:
            raise ForbiddenError("Це запрошення призначене для іншого email")
        invitation.mentor_id = user.id
    elif payload is not None and payload.password:
        if mentor.password_hash:
            raise UnauthorizedError("Потрібен вхід у систему для прийняття запрошення")
        mentor.password_hash = _hash_password(payload.password)
        repos.users.save(mentor)
        token_response = _issue_token(mentor)
        access_token = token_response.access_token
    else:
        if mentor.password_hash:
            raise UnauthorizedError("Потрібен вхід у систему для прийняття запрошення")
        raise UnauthorizedError(
            "Вкажіть пароль для активації облікового запису ментора"
        )

    invitation.status = MentorStatus.accepted.value
    invitation.accepted_at = utcnow()
    repos.mentors.save(invitation)

    return AcceptInvitationResponse(
        message="Запрошення успішно прийнято",
        board_id=invitation.board_id,
        status=MentorStatus.accepted,
        access_token=access_token,
        user=token_response.user if token_response else None,
        expires_in=token_response.expires_in if token_response else None,
    )


@mentors_router.delete(
    "/{mentor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Відкликати доступ ментора до дошки",
    description=(
        "Кандидат або адмін відкликає доступ ментора до дошки (FR-015, US-002). "
        "Після відкликання ментор отримає 403 при будь-якому зверненні до дошки. "
        "Якщо ментора не знайдено серед запрошених — повертає 404."
    ),
    responses=error_responses(
        not_found="Ментора серед запрошених для цієї дошки не знайдено",
    ),
)
def revoke_mentor(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    mentor_id: UUID = Path(..., description="Ідентифікатор ментора"),
    user: CandidateOrAdmin = None,
    repos: Repos = None,
) -> None:
    require_board(repos, board_id, user, write=True)
    invitation = repos.mentors.get_by_board_and_mentor(
        board_id, mentor_id, for_update=True
    )
    if invitation is None:
        raise NotFoundError("Ментора серед запрошених для цієї дошки не знайдено")
    invitation.status = MentorStatus.revoked.value
    invitation.accepted_at = None
    repos.mentors.save(invitation)
