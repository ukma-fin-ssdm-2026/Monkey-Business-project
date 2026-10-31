"""Спільна перевірка доступу до картки для вкладених ресурсів.

## Використання ШІ
- **Інструмент:** Codex.
- **Застосування:** винесення спільної перевірки доступу до картки.
- **Верифікація:** автор переглянув код і перевірив результати тестів до/після.
"""

from __future__ import annotations

from uuid import UUID

from ..auth import require_board_access
from ..domain import Card, User
from ..errors import NotFoundError
from ..repositories.base import Repositories


def require_card(
    repos: Repositories,
    board_id: UUID,
    card_id: UUID,
    user: User,
    *,
    write: bool = False,
) -> Card:
    if repos.boards.get(board_id) is None:
        raise NotFoundError(f"Дошку {board_id} не знайдено")
    require_board_access(repos, board_id, user, write=write)
    card = repos.cards.get(card_id)
    if card is None or card.board_id != board_id:
        raise NotFoundError(f"Картку {card_id} на дошці {board_id} не знайдено")
    return card
