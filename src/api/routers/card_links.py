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
from ..errors import NotFoundError
from ..schemas import CardLinkCreate, CardLinkOut

router = APIRouter(prefix="/boards/{board_id}/cards/{card_id}/links", tags=["Card Links"])


def _require_card(board_id: UUID, card_id: UUID) -> dict:
    record = store.get_card(card_id)
    if record is None or record["board_id"] != board_id:
        raise NotFoundError(f"Картку {card_id} на дошці {board_id} не знайдено")
    return record


@router.get(
    "",
    response_model=list[CardLinkOut],
    status_code=status.HTTP_200_OK,
    summary="Список посилань на тестові завдання картки",
    responses={404: {"description": "Картку не знайдено"}},
)
def list_links(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
) -> list[CardLinkOut]:
    _require_card(board_id, card_id)
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
    responses={
        404: {"description": "Картку не знайдено"},
        422: {"description": "Рядок не є коректним URL"},
    },
)
def create_link(
    payload: CardLinkCreate,
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
) -> CardLinkOut:
    _require_card(board_id, card_id)
    record = store.create_link(card_id, str(payload.url))
    return CardLinkOut(**record)


@router.delete(
    "/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Видалити посилання",
    responses={404: {"description": "Посилання або картку не знайдено"}},
)
def delete_link(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
    link_id: UUID = Path(..., description="Ідентифікатор посилання"),
) -> None:
    _require_card(board_id, card_id)
    if not store.delete_link(card_id, link_id):
        raise NotFoundError(f"Посилання {link_id} не знайдено")