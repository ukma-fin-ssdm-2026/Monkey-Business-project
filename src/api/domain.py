"""
Інструмент: Claude
Застосування: Виділення доменних сутностей, якими обмінюються роутери та шар
репозиторіїв, замість словників in-memory сховища.
Верифікація: Поля звірено з data-model.md та Pydantic-схемами в schemas.py.

Доменні сутності — прості dataclass без залежності від бази даних чи ORM.
Роутери та автентифікація працюють лише з ними, тому заміна сховища не
змінює код API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

DEFAULT_STAGE_NAMES = ["Відгук", "Скринінг", "Технічне інтерв'ю", "Офер"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(kw_only=True)
class User:
    email: str
    password_hash: str
    role: str
    is_active: bool = True
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utcnow)


@dataclass(kw_only=True)
class Board:
    owner_id: UUID
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utcnow)


@dataclass(kw_only=True)
class Stage:
    board_id: UUID
    name: str
    order_index: int
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utcnow)


@dataclass(kw_only=True)
class Card:
    board_id: UUID
    stage_id: UUID
    company: str
    position: str
    position_index: int
    vacancy_url: Optional[str] = None
    requirements_text: Optional[str] = None
    deadline: Optional[datetime] = None
    notifications_enabled: bool = True
    status: str = "active"
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.updated_at is None:
            self.updated_at = self.created_at


@dataclass(kw_only=True)
class CardLink:
    card_id: UUID
    url: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utcnow)


@dataclass(kw_only=True)
class CardNote:
    card_id: UUID
    content: str
    source: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.updated_at is None:
            self.updated_at = self.created_at
