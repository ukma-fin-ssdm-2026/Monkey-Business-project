"""
Інструмент: Claude
Застосування: Проєктування інтерфейсів репозиторіїв — шару між API та
конкретною базою даних.
Верифікація: Набір методів звірено з усіма зверненнями роутерів і auth.py
до колишнього store.py.

Інтерфейси репозиторіїв.

Роутери та автентифікація залежать лише від цих протоколів і доменних
сутностей (domain.py). Реалізація для PostgreSQL — repositories/sql.py;
щоб перейти на іншу СУБД, достатньо нової реалізації та зміни однієї
функції в db.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, TypeVar
from uuid import UUID

from ..domain import Board, Card, CardLink, CardNote, Stage, User

E = TypeVar("E")


class Repository(Protocol[E]):
    def add(self, entity: E) -> E: ...

    def get(self, entity_id: UUID) -> Optional[E]: ...

    def save(self, entity: E) -> E: ...

    def delete(self, entity_id: UUID) -> None: ...


class UserRepository(Repository[User], Protocol):
    def get_by_email(self, email: str) -> Optional[User]: ...


class BoardRepository(Repository[Board], Protocol):
    def mentor_has_access(self, board_id: UUID, mentor_id: UUID) -> bool: ...


class StageRepository(Repository[Stage], Protocol):
    def list_for_board(self, board_id: UUID) -> list[Stage]: ...

    def has_cards(self, stage_id: UUID) -> bool: ...


class CardRepository(Repository[Card], Protocol):
    def list_for_board(
        self, board_id: UUID, stage_id: Optional[UUID], status: Optional[str]
    ) -> list[Card]: ...

    def count_in_stage(self, stage_id: UUID) -> int: ...


class CardLinkRepository(Repository[CardLink], Protocol):
    def list_for_card(self, card_id: UUID) -> list[CardLink]: ...


class CardNoteRepository(Repository[CardNote], Protocol):
    def list_for_card(self, card_id: UUID) -> list[CardNote]: ...


@dataclass(frozen=True)
class Repositories:
    """Набір репозиторіїв, що працюють в одній транзакції запиту."""

    users: UserRepository
    boards: BoardRepository
    stages: StageRepository
    cards: CardRepository
    links: CardLinkRepository
    notes: CardNoteRepository
