"""
Інструмент: Claude
Застосування: Написання ендпоінтів для ресурсу Cards із забезпеченням REST-семантики (HTTP-методи, статус-коди) та OpenAPI анотацій.
Верифікація: Перевірено вручну через Swagger UI працездатність усіх ендпоінтів та формат відповідей, узгоджено командою.

Ресурс: Vacancy Cards (`/boards/{board_id}/cards`).

Покриває FR-004–FR-010 (створення, редагування, переміщення, видалення картки
вакансії). Ресурсна мапа відповідає рекомендаціям курсу: іменник у множині,
дія "move" — як під-ресурс (POST .../move), бо це не проста заміна полів,
а бізнес-операція з побічними ефектами (перерахунок позицій інших карток).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Path, Query, status

from .. import store
from ..errors import NotFoundError, error_responses
from ..schemas import (
    CardCreate,
    CardListResponse,
    CardMove,
    CardOut,
    CardStatus,
    CardUpdate,
    PaginationMeta,
)

router = APIRouter(prefix="/boards/{board_id}/cards", tags=["Cards"])


def _to_card_out(record: dict) -> CardOut:
    return CardOut(
        id=record["id"],
        board_id=record["board_id"],
        stage_id=record["stage_id"],
        company=record["company"],
        position=record["position"],
        position_index=record["position_index"],
        vacancy_url=record.get("vacancy_url"),
        requirements_text=record.get("requirements_text"),
        deadline=record.get("deadline"),
        notifications_enabled=record["notifications_enabled"],
        status=record["status"],
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )


def _require_board(board_id: UUID) -> None:
    if not store.board_exists(board_id):
        raise NotFoundError(f"Дошку {board_id} не знайдено")


def _require_card(board_id: UUID, card_id: UUID) -> dict:
    record = store.get_card(card_id)
    if record is None or record["board_id"] != board_id:
        raise NotFoundError(f"Картку {card_id} на дошці {board_id} не знайдено")
    return record


@router.get(
    "",
    response_model=CardListResponse,
    status_code=status.HTTP_200_OK,
    summary="Список карток вакансій на дошці",
    description=(
        "Повертає картки дошки з опційною фільтрацією за етапом і статусом "
        "(FR-003, FR-006). Пагінація на основі зсуву (offset), бо дошка — "
        "обмежений набір карток (до ~100), а не безкінечна стрічка."
    ),
    responses=error_responses("Дошку не знайдено", "Невалідний фільтр або параметри пагінації"),
)
def list_cards(
    board_id: UUID = Path(..., description="Ідентифікатор дошки-власника карток"),
    stage_id: Optional[UUID] = Query(default=None, description="Фільтр за етапом"),
    status_: Optional[CardStatus] = Query(
        default=None, alias="status", description="Фільтр за статусом картки"
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Розмір сторінки (макс. 100)"),
    offset: int = Query(default=0, ge=0, description="Зсув від початку списку"),
) -> CardListResponse:
    _require_board(board_id)
    all_items = store.list_cards(board_id, stage_id, status_.value if status_ else None)
    page = all_items[offset : offset + limit]
    return CardListResponse(
        items=[_to_card_out(r) for r in page],
        pagination=PaginationMeta(limit=limit, offset=offset, total=len(all_items)),
    )


@router.post(
    "",
    response_model=CardOut,
    status_code=status.HTTP_201_CREATED,
    summary="Створити картку вакансії",
    description="Створює нову картку в зазначеному етапі дошки (FR-007).",
    responses=error_responses("Дошку не знайдено", "Порожнє обов'язкове поле або некоректний формат"),
)
def create_card(
    payload: CardCreate,
    board_id: UUID = Path(..., description="Ідентифікатор дошки, до якої додається картка"),
) -> CardOut:
    _require_board(board_id)
    data = payload.model_dump()
    if data.get("vacancy_url") is not None:
        data["vacancy_url"] = str(data["vacancy_url"])
    record = store.create_card(board_id, data)
    return _to_card_out(record)


@router.get(
    "/{card_id}",
    response_model=CardOut,
    status_code=status.HTTP_200_OK,
    summary="Отримати картку за ідентифікатором",
    description="Повертає одну картку вакансії з усіма полями (FR-007).",
    responses=error_responses("Картку або дошку не знайдено", "Некоректний ідентифікатор"),
)
def get_card(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
) -> CardOut:
    _require_board(board_id)
    record = _require_card(board_id, card_id)
    return _to_card_out(record)


@router.patch(
    "/{card_id}",
    response_model=CardOut,
    status_code=status.HTTP_200_OK,
    summary="Частково оновити картку",
    description=(
        "PATCH, а не PUT: клієнт надсилає лише змінені поля (FR-008). "
        "Також використовується для закриття картки (`status`, FR-006)."
    ),
    responses=error_responses("Картку або дошку не знайдено", "Невалідне значення поля"),
)
def update_card(
    payload: CardUpdate,
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
) -> CardOut:
    _require_board(board_id)
    _require_card(board_id, card_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("vacancy_url") is not None:
        changes["vacancy_url"] = str(changes["vacancy_url"])
    record = store.update_card(card_id, changes)
    return _to_card_out(record)


@router.delete(
    "/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Видалити картку",
    description="Видаляє картку остаточно (FR-008). Повторний виклик — теж 404, а не помилка.",
    responses=error_responses("Картку або дошку не знайдено", "Некоректний ідентифікатор"),
)
def delete_card(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
) -> None:
    _require_board(board_id)
    _require_card(board_id, card_id)
    store.delete_card(card_id)


@router.post(
    "/{card_id}/move",
    response_model=CardOut,
    status_code=status.HTTP_200_OK,
    summary="Перемістити картку між етапами (drag-and-drop)",
    description=(
        "Дія як під-ресурс, а не PATCH основного ресурсу: переміщення "
        "зачіпає позиції інших карток етапу (FR-004, FR-005), тобто це "
        "бізнес-операція, а не проста заміна поля."
    ),
    responses=error_responses("Картку або дошку не знайдено", "Некоректний stage_id або position_index"),
)
def move_card(
    payload: CardMove,
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
) -> CardOut:
    _require_board(board_id)
    _require_card(board_id, card_id)
    record = store.move_card(card_id, payload.stage_id, payload.position_index)
    return _to_card_out(record)