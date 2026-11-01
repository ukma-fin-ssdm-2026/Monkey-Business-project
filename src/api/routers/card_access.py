"""Спільні перевірки доступу до дошки та картки для роутерів.

## Використання ШІ
- **Інструмент:** Codex.
- **Застосування:** винесення спільної перевірки доступу до картки.
- **Верифікація:** автор переглянув код і перевірив результати тестів до/після.

- **Інструмент:** Claude.
- **Застосування:** винесення `require_board` замість трьох однакових
  `_require_board` у stages.py, cards.py, mentors.py і копії `_require_card`
  у comments.py (Extract Function).
- **Верифікація:** перегляд змін рядок за рядком, повний прогін pytest до і
  після (220 passed) та інтеграційні тести з PostgreSQL.
"""

from __future__ import annotations

from uuid import UUID

from ..auth import require_board_access
from ..domain import Card, User
from ..errors import NotFoundError
from ..repositories.base import Repositories


def require_board(
    repos: Repositories, board_id: UUID, user: User, *, write: bool = False
) -> None:
    # 404 for a missing board comes before the 403 access check.
    if repos.boards.get(board_id) is None:
        raise NotFoundError(f"Дошку {board_id} не знайдено")
    require_board_access(repos, board_id, user, write=write)


def require_card(
    repos: Repositories,
    board_id: UUID,
    card_id: UUID,
    user: User,
    *,
    write: bool = False,
) -> Card:
    require_board(repos, board_id, user, write=write)
    card = repos.cards.get(card_id)
    if card is None or card.board_id != board_id:
        raise NotFoundError(f"Картку {card_id} на дошці {board_id} не знайдено")
    return card
