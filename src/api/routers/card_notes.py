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

from dataclasses import replace
from uuid import UUID

from fastapi import APIRouter, Path, status

from ..auth import CandidateOrAdmin, CurrentUser
from ..db import Repos
from ..domain import CardNote, utcnow
from ..errors import NotFoundError, error_responses
from ..repositories.base import Repositories
from ..schemas import CardNoteCreate, CardNoteOut, CardNoteUpdate

from .card_access import require_card

router = APIRouter(
    prefix="/boards/{board_id}/cards/{card_id}/notes",
    tags=["Card Notes"],
)


def _require_note(repos: Repositories, card_id: UUID, note_id: UUID) -> CardNote:
    note = repos.notes.get(note_id)
    if note is None or note.card_id != card_id:
        raise NotFoundError(f"Нотатку {note_id} для картки {card_id} не знайдено")
    return note


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
    repos: Repos = None,
) -> list[CardNoteOut]:
    require_card(repos, board_id, card_id, user)
    return [CardNoteOut.model_validate(n) for n in repos.notes.list_for_card(card_id)]


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
    repos: Repos = None,
) -> CardNoteOut:
    require_card(repos, board_id, card_id, user, write=True)
    note = repos.notes.add(
        CardNote(card_id=card_id, content=payload.content, source=payload.source.value)
    )
    return CardNoteOut.model_validate(note)


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
    repos: Repos = None,
) -> CardNoteOut:
    require_card(repos, board_id, card_id, user, write=True)
    note = _require_note(repos, card_id, note_id)
    note = repos.notes.save(replace(note, content=payload.content, updated_at=utcnow()))
    return CardNoteOut.model_validate(note)


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
    repos: Repos = None,
) -> None:
    require_card(repos, board_id, card_id, user, write=True)
    _require_note(repos, card_id, note_id)
    repos.notes.delete(note_id)
