"""
Інструмент: Gemini
Застосування: Створення вкладеного REST-роутера для нотаток та фідбеку до карток (FR-011, FR-022).
Верифікація: Перевірено збереження хронологічного порядку, обмеження прав
(ментори мають лише read-only, FR-014), валідацію тексту нотаток
(1..3000 символів) та коректність статус-кодів.

Ресурс: Card Notes (`/boards/{board_id}/cards/{card_id}/notes`).
Вкладений під `cards`, оскільки нотатки та фідбек прив'язані до конкретної вакансії.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Path, status

from .. import store
from ..auth import CandidateOrAdmin, CurrentUser, require_board_access
from ..errors import NotFoundError, error_responses
from ..schemas import CardNoteCreate, CardNoteOut, CardNoteUpdate

router = APIRouter(
    prefix="/boards/{board_id}/cards/{card_id}/notes",
    tags=["Card Notes"],
)


def _require_card(
    board_id: UUID, card_id: UUID, user: dict, *, write: bool = False
) -> dict:
    if not store.board_exists(board_id):
        raise NotFoundError(f"Дошку {board_id} не знайдено")
    require_board_access(board_id, user, write=write)
    record = store.get_card(card_id)
    if record is None or record["board_id"] != board_id:
        raise NotFoundError(f"Картку {card_id} на дошці {board_id} не знайдено")
    return record


@router.get(
    "",
    response_model=list[CardNoteOut],
    status_code=status.HTTP_200_OK,
    summary="Список нотаток та фідбеку до картки",
    description=(
        "Повертає всі нотатки та фідбек по картці у хронологічному порядку "
        "їх створення (FR-011). Доступно кандидату-власнику, ментору та адміну."
    ),
    responses=error_responses(
        "Картку або дошку не знайдено", "Некоректний ідентифікатор"
    ),
)
def list_notes(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
    user: CurrentUser = None,
) -> list[CardNoteOut]:
    _require_card(board_id, card_id, user)
    return [CardNoteOut(**note) for note in store.list_card_notes(card_id)]


@router.post(
    "",
    response_model=CardNoteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Додати нотатку або фідбек",
    description=(
        "Додає нову нотатку до картки із зазначенням джерела (кандидат, "
        "фідбек рекрутера або результат AI-асистента, FR-011, FR-022). "
        "Ментор не може додавати нотатки (FR-014)."
    ),
    responses=error_responses(
        "Картку або дошку не знайдено",
        "Невалідний текст нотатки",
    ),
)
def create_note(
    payload: CardNoteCreate,
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
    user: CandidateOrAdmin = None,
) -> CardNoteOut:
    _require_card(board_id, card_id, user, write=True)
    record = store.create_card_note(
        card_id=card_id,
        content=payload.content,
        source=payload.source.value,
    )
    return CardNoteOut(**record)


@router.patch(
    "/{note_id}",
    response_model=CardNoteOut,
    status_code=status.HTTP_200_OK,
    summary="Оновити нотатку",
    description="Редагує текст раніше створеної нотатки (FR-011).",
    responses=error_responses(
        "Нотатку або картку не знайдено",
        "Невалідний текст нотатки",
    ),
)
def update_note(
    payload: CardNoteUpdate,
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
    note_id: UUID = Path(..., description="Ідентифікатор нотатки"),
    user: CandidateOrAdmin = None,
) -> CardNoteOut:
    _require_card(board_id, card_id, user, write=True)
    note = store.get_card_note(note_id)
    if note is None or note["card_id"] != card_id:
        raise NotFoundError(f"Нотатку {note_id} для картки {card_id} не знайдено")
    updated = store.update_card_note(note_id, payload.content)
    return CardNoteOut(**updated)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Видалити нотатку",
    description="Видаляє нотатку з картки вакансії (FR-011).",
    responses=error_responses(
        "Нотатку або картку не знайдено",
        "Некоректний ідентифікатор",
    ),
)
def delete_note(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
    note_id: UUID = Path(..., description="Ідентифікатор нотатки"),
    user: CandidateOrAdmin = None,
) -> None:
    _require_card(board_id, card_id, user, write=True)
    if not store.delete_card_note(card_id, note_id):
        raise NotFoundError(f"Нотатку {note_id} не знайдено")
