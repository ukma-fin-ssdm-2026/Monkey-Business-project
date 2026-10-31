"""
Інструмент: Claude
Застосування: Ендпоінт «мої дошки», щоб клієнт дізнавався board_id через API,
а не запитом до бази даних.
Верифікація: Модульні тести tests/test_boards.py та інтеграційний тест
tests/integration/test_boards_integration.py проти PostgreSQL.

Ресурс: Boards (`/boards`).
Повертає дошки, доступні поточному користувачу: власну дошку кандидата
(створюється під час реєстрації) і дошки, до яких ментор прийняв запрошення
(FR-012). Адміністратор має доступ до будь-якої дошки за її board_id, але
список усіх дошок тут не повертається.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from ..auth import CurrentUser
from ..db import Repos
from ..errors import auth_error_responses
from ..schemas import BoardAccess, BoardOut

router = APIRouter(prefix="/boards", tags=["Boards"])


@router.get(
    "",
    response_model=list[BoardOut],
    status_code=status.HTTP_200_OK,
    summary="Мої дошки",
    description=(
        "Повертає дошки поточного користувача: власну дошку кандидата та "
        "дошки, до яких ментор має доступ за прийнятим запрошенням. "
        "Відсортовано за датою створення."
    ),
    responses=auth_error_responses(unauthorized="Потрібен Bearer-токен"),
)
def list_my_boards(user: CurrentUser, repos: Repos) -> list[BoardOut]:
    return [
        BoardOut(
            id=board.id,
            owner_id=board.owner_id,
            access=(
                BoardAccess.owner if board.owner_id == user.id else BoardAccess.mentor
            ),
            created_at=board.created_at,
        )
        for board in repos.boards.list_for_user(user.id)
    ]
