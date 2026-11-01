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

import secrets
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from fastapi.security import HTTPAuthorizationCredentials
import mailtrap as mt
import os

from ..auth import (
    CandidateOrAdmin,
    CurrentUser,
    _hash_password,
    _issue_token,
    bearer,
    get_current_user,
    require_board_access,
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
from ..repositories.base import Repositories
from ..schemas import (
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    BoardMentorOut,
    InviteMentorRequest,
    MentorStatus,
    UserRole,
)

MAILTRAP_API_TOKEN = os.getenv("MAILTRAP_API_TOKEN")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

mentors_router = APIRouter(prefix="/boards/{board_id}/mentors", tags=["Mentors"])
invitations_router = APIRouter(prefix="/invitations", tags=["Invitations"])


def _require_board(
    repos: Repositories, board_id: UUID, user: User, *, write: bool = False
) -> None:
    if repos.boards.get(board_id) is None:
        raise NotFoundError(f"Дошку {board_id} не знайдено")
    require_board_access(repos, board_id, user, write=write)


def _to_mentor_out(invitation: BoardMentor, email: str) -> BoardMentorOut:
    return BoardMentorOut(
        id=invitation.id,
        board_id=invitation.board_id,
        mentor_id=invitation.mentor_id,
        email=email,
        status=MentorStatus(invitation.status),
        invite_token=invitation.invite_token,
        invited_at=invitation.invited_at,
        accepted_at=invitation.accepted_at,
    )


def _send_invitation_email(email: str, token: str, board_id: UUID) -> None:
    """Відправка email із посиланням-запрошенням через API Mailtrap."""

    if not MAILTRAP_API_TOKEN:
        raise RuntimeError(
            "MAILTRAP_API_TOKEN не задано — email не може бути відправлено. "
            "Додайте змінну в .env і перезапустіть контейнер."
        )

    invite_url = f"{FRONTEND_URL}/invitations/{token}"
    mail = mt.Mail(
        sender=mt.Address(email="hello@demomailtrap.co", name="Interview Board"),
        to=[mt.Address(email=email)],
        subject="Запрошення до дошки",
        text=(
            f"Привіт!\n\n"
            f"Вас запросили до дошки (ID: {board_id}).\n"
            f"Щоб приєднатися, перейдіть за цим посиланням:\n"
            f"{invite_url}\n\n"
        ),
        category="Invitation Test",
    )

    try:
        client = mt.MailtrapClient(
            token=MAILTRAP_API_TOKEN, sandbox=True, inbox_id=4439163
        )
        response = client.send(mail)
        print(
            f"[Email Service] Успішно надіслано лист на {email}. Відповідь: {response}"
        )
    except Exception as e:
        details = ""
        if hasattr(e, "response") and e.response is not None:
            details = f" Деталі API: {e.response.text}"
        raise ServiceUnavailableError(
            f"Не вдалося надіслати запрошення на {email}: {e}.{details}"
        ) from e


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
    _require_board(repos, board_id, user, write=True)

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

    existing = repos.mentors.get_by_board_and_mentor(board_id, mentor.id)
    if existing is not None:
        if existing.status == MentorStatus.accepted.value:
            raise ConflictError("Цей ментор уже має доступ до дошки")
        if existing.status == MentorStatus.pending.value:
            raise ConflictError("Запрошення для цього ментора вже очікує підтвердження")
        if existing.status == MentorStatus.revoked.value:
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
    _require_board(repos, board_id, user)
    invitations = repos.mentors.list_for_board(board_id)

    result = []
    for inv in invitations:
        mentor = repos.users.get(inv.mentor_id)
        if mentor is not None:
            result.append(_to_mentor_out(inv, mentor.email))
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
    if invitation is None or invitation.status != MentorStatus.pending.value:
        raise NotFoundError("Запрошення не знайдено або термін його дії минув")
    mentor = repos.users.get(invitation.mentor_id)
    if mentor is None:
        raise NotFoundError("Користувача для цього запрошення не знайдено")
    return _to_mentor_out(invitation, mentor.email)


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
    invitation = repos.mentors.get_by_token(token)
    if invitation is None or invitation.status != MentorStatus.pending.value:
        raise ForbiddenError("Недійсне або прострочене запрошення")

    access_token: Optional[str] = None

    if credentials is not None:
        user = get_current_user(credentials, repos)
        if user.role != UserRole.mentor.value:
            raise ForbiddenError("Лише ментор може прийняти запрошення")
        invited_mentor = repos.users.get(invitation.mentor_id)
        if invited_mentor is None:
            raise ForbiddenError("Користувача для цього запрошення не знайдено")
        if invited_mentor.email.lower() != user.email.lower():
            raise ForbiddenError("Це запрошення призначене для іншого email")
        invitation.mentor_id = user.id
    elif payload is not None and payload.password:
        mentor = repos.users.get(invitation.mentor_id)
        if mentor is None:
            raise ForbiddenError("Користувача для цього запрошення не знайдено")
        mentor.password_hash = _hash_password(payload.password)
        repos.users.save(mentor)
        token_response = _issue_token(mentor)
        access_token = token_response.access_token
    else:
        mentor = repos.users.get(invitation.mentor_id)
        if mentor is not None and mentor.password_hash:
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
    _require_board(repos, board_id, user, write=True)
    invitation = repos.mentors.get_by_board_and_mentor(board_id, mentor_id)
    if invitation is None:
        raise NotFoundError("Ментора серед запрошених для цієї дошки не знайдено")
    invitation.status = MentorStatus.revoked.value
    invitation.accepted_at = None
    repos.mentors.save(invitation)
