"""
Інструмент: Claude
Застосування: Створення REST-роутера для коментарів ментора до карток (FR-013, US-002).
Верифікація: Перевірено обмеження доступу (лише користувач із доступом до дошки може
коментувати), видалення лише автором коментаря, стандартну обробку помилок.

Ресурс: Comments (`/boards/{board_id}/cards/{card_id}/comments`).
Вкладений під `cards`, оскільки коментарі прив'язані до конкретної картки вакансії.
Ментор може залишати коментарі (read + comment), але не може змінювати дані кандидата
(FR-014). Видалити коментар може лише його автор або адмін.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Path, status

from ..auth import CurrentUser, require_board_access
from ..db import Repos
from ..domain import Card, Comment, User
from ..errors import ForbiddenError, NotFoundError, error_responses
from ..repositories.base import Repositories
from ..schemas import CommentCreate, CommentOut

router = APIRouter(
    prefix="/boards/{board_id}/cards/{card_id}/comments",
    tags=["Comments"],
)


def _require_card(
    repos: Repositories,
    board_id: UUID,
    card_id: UUID,
    user: User,
) -> Card:
    if repos.boards.get(board_id) is None:
        raise NotFoundError(f"Дошку {board_id} не знайдено")
    require_board_access(repos, board_id, user)
    card = repos.cards.get(card_id)
    if card is None or card.board_id != board_id:
        raise NotFoundError(f"Картку {card_id} на дошці {board_id} не знайдено")
    return card


def _require_comment(repos: Repositories, card_id: UUID, comment_id: UUID) -> Comment:
    comment = repos.comments.get(comment_id)
    if comment is None or comment.card_id != card_id:
        raise NotFoundError(f"Коментар {comment_id} для картки {card_id} не знайдено")
    return comment


@router.get(
    "",
    response_model=list[CommentOut],
    status_code=status.HTTP_200_OK,
    summary="Список коментарів до картки",
    description=(
        "Повертає всі коментарі до картки у хронологічному порядку (FR-013, US-002). "
        "Доступно кандидату-власнику, ментору з доступом та адміну."
    ),
    responses=error_responses("Картку або дошку не знайдено"),
)
def list_comments(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
    user: CurrentUser = None,
    repos: Repos = None,
) -> list[CommentOut]:
    _require_card(repos, board_id, card_id, user)
    return [CommentOut.model_validate(c) for c in repos.comments.list_for_card(card_id)]


@router.post(
    "",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Додати коментар до картки",
    description=(
        "Додає новий коментар до картки вакансії (FR-013, US-002). "
        "Доступно будь-якому користувачу з доступом до дошки — кандидату, "
        "ментору або адміну."
    ),
    responses=error_responses(
        "Картку або дошку не знайдено",
        "Невалідний текст коментаря",
    ),
)
def create_comment(
    payload: CommentCreate,
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
    user: CurrentUser = None,
    repos: Repos = None,
) -> CommentOut:
    _require_card(repos, board_id, card_id, user)
    comment = repos.comments.add(
        Comment(
            card_id=card_id,
            author_id=user.id,
            content=payload.content,
        )
    )
    return CommentOut.model_validate(comment)


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Видалити коментар",
    description=(
        "Видаляє коментар до картки (FR-013, US-002). "
        "Видалити може лише автор коментаря або адмін."
    ),
    responses=error_responses(
        "Коментар або картку не знайдено",
        "Недостатньо прав для видалення коментаря",
    ),
)
def delete_comment(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    card_id: UUID = Path(..., description="Ідентифікатор картки"),
    comment_id: UUID = Path(..., description="Ідентифікатор коментаря"),
    user: CurrentUser = None,
    repos: Repos = None,
) -> None:
    _require_card(repos, board_id, card_id, user)
    comment = _require_comment(repos, card_id, comment_id)
    if comment.author_id != user.id and user.role != "admin":
        raise ForbiddenError("Видалити коментар може лише його автор або адмін")
    repos.comments.delete(comment_id)
