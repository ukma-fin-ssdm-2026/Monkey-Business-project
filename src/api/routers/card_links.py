"""
Інструмент: Claude
Застосування: Створення вкладених ендпоінтів для під-ресурсу Card Links з реалізацією валідації посилань (HttpUrl).
Верифікація: Перевірено вручну логіку додавання та видалення посилань через Swagger UI, узгоджено командою.

Ресурс: Card Links (`/boards/{board_id}/cards/{card_id}/links`).

Вкладений під `cards`, бо посилання не мають самостійного сенсу поза карткою
(FR-009: "до картки можна додати кілька посилань на тестові завдання").
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Path, status

from .. import store
from ..auth import CandidateOrAdmin, CurrentUser, require_board_access
from ..errors import NotFoundError, error_responses
from ..schemas import CardLinkCreate, CardLinkOut

router = APIRouter(prefix="/boards/{board_id}/cards/{card_id}/links", tags=["Card Links"])


def _require_card(board_id: UUID, card_id: UUID, user: dict, *, write: bool = False) -> dict:
    if not store.board_exists(board_id):
        raise NotFoundError(f"Дошку {board_id} не знайдено")
    require_board_access(board_id, user, write=write)
    record = store.get_card(card_id)
    if record is None or record["board_id"] != board_id:
        raise NotFoundError(f"Картку {card_id} на дошці {board_id} не знайдено")
    return record


@router.get(
    "",
    response_model=list[CardLinkOut],
    status_code=status.HTTP_200_OK,
    summary="Список посилань на тестові завдання картки",
    description="Повертає всі посилання на тестові завдання, додані до картки (FR-009).",
    responses=error_responses("Картку не знайдено", "Некоректний ідентифікатор"),
)
def list_links(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
    user: CurrentUser = None,
) -> list[CardLinkOut]:
    _require_card(board_id, card_id, user)
    return [CardLinkOut(**link) for link in store.list_links(card_id)]


@router.post(
    "",
    response_model=CardLinkOut,
    status_code=status.HTTP_201_CREATED,
    summary="Додати посилання на тестове завдання",
    description=(
        "Валідація URL відбувається на рівні типу Pydantic (`HttpUrl`) — "
        "рядок, що не є коректним URL, відхиляється з 422 (FR-009)."
    ),
    responses=error_responses("Картку не знайдено", "Рядок не є коректним URL"),
)
def create_link(
    payload: CardLinkCreate,
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
    user: CandidateOrAdmin = None,
) -> CardLinkOut:
    _require_card(board_id, card_id, user, write=True)
    record = store.create_link(card_id, str(payload.url))
    return CardLinkOut(**record)


@router.delete(
    "/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Видалити посилання",
    description="Видаляє посилання з картки. Повторний виклик повертає 404.",
    responses=error_responses("Посилання або картку не знайдено", "Некоректний ідентифікатор"),
)
def delete_link(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
    link_id: UUID = Path(..., description="Ідентифікатор посилання"),
    user: CandidateOrAdmin = None,
) -> None:
    _require_card(board_id, card_id, user, write=True)
    if not store.delete_link(card_id, link_id):
        raise NotFoundError(f"Посилання {link_id} не знайдено")