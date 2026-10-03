"""
Інструмент: Claude
Застосування: Створення Pydantic-схем для валідації вхідних даних, генерації OpenAPI моделей та стандартизації повідомлень про помилки.
Верифікація: Усі типи даних та обмеження (Field) перевірені вручну на відповідність вимогам проєкту, узгоджено командою.
"""

"""
Pydantic-схеми API.

Джерело вимог: requirements.md (FR-006–FR-010), data-model.md (сутності `cards`,
`card_links`). Структура помилок — за довідником курсу "Узгоджена структура
помилок" (код + повідомлення + деталі полів + request_id + посилання на docs).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


# --------------------------------------------------------------------------- #
# Спільні схеми (помилки, пагінація)
# --------------------------------------------------------------------------- #

class ErrorDetail(BaseModel):
    field: str = Field(..., description="Назва поля, яке не пройшло валідацію")
    message: str = Field(..., description="Людиночитане пояснення, що саме не так")
    provided_value: Optional[str] = Field(
        default=None, description="Значення, яке надіслав клієнт (якщо доречно)"
    )


class ErrorBody(BaseModel):
    code: str = Field(..., examples=["VALIDATION_ERROR"], description="Машиночитаний код помилки")
    message: str = Field(..., description="Людиночитане повідомлення про помилку")
    details: list[ErrorDetail] = Field(default_factory=list, description="Деталі по кожному полю")
    request_id: str = Field(..., description="Ідентифікатор запиту для пошуку в логах")
    documentation: Optional[str] = Field(
        default=None, description="Посилання на розділ документації з поясненням помилки"
    )


class ErrorResponse(BaseModel):
    """Єдиний каркас помилки для всіх кінцевих точок API."""

    error: ErrorBody


class PaginationMeta(BaseModel):
    limit: int = Field(..., ge=1, le=100, description="Розмір сторінки (макс. 100)")
    offset: int = Field(..., ge=0, description="Зсув від початку списку")
    total: int = Field(..., ge=0, description="Загальна кількість елементів у ресурсі")


# --------------------------------------------------------------------------- #
# Cards (FR-006 – FR-010)
# --------------------------------------------------------------------------- #

class CardStatus(str, Enum):
    active = "active"
    rejected = "rejected"
    offer_accepted = "offer_accepted"


class CardBase(BaseModel):
    company: str = Field(
        ..., min_length=1, max_length=200,
        description="Назва компанії (обов'язкове поле, FR-007)",
        examples=["Acme Corp"],
    )
    position: str = Field(
        ..., min_length=1, max_length=200,
        description="Назва позиції (обов'язкове поле, FR-007)",
        examples=["Backend Engineer"],
    )
    vacancy_url: Optional[HttpUrl] = Field(
        default=None, description="Посилання на оригінальну вакансію"
    )
    requirements_text: Optional[str] = Field(
        default=None, max_length=5000, description="Текст вимог вакансії (FR-007, FR-003 розширення)"
    )
    deadline: Optional[datetime] = Field(
        default=None, description="Дедлайн тестового завдання або співбесіди (FR-010)"
    )
    notifications_enabled: bool = Field(
        default=True, description="Чи увімкнені нагадування для цієї картки (FR-018)"
    )


class CardCreate(CardBase):
    """Тіло запиту на створення картки (FR-007)."""

    stage_id: UUID = Field(..., description="Етап, у якому створюється картка")


class CardUpdate(BaseModel):
    """Часткове оновлення картки (PATCH, FR-008) — усі поля опційні."""

    company: Optional[str] = Field(default=None, min_length=1, max_length=200)
    position: Optional[str] = Field(default=None, min_length=1, max_length=200)
    vacancy_url: Optional[HttpUrl] = None
    requirements_text: Optional[str] = Field(default=None, max_length=5000)
    deadline: Optional[datetime] = None
    notifications_enabled: Optional[bool] = None
    status: Optional[CardStatus] = Field(
        default=None, description="Закриття картки: 'rejected' або 'offer_accepted' (FR-006)"
    )

    @field_validator("company", "position")
    @classmethod
    def not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("поле не може бути порожнім рядком")
        return value


class CardMove(BaseModel):
    """Переміщення картки між етапами методом drag-and-drop (FR-004, FR-005)."""

    stage_id: UUID = Field(..., description="Ідентифікатор цільового етапу")
    position: int = Field(
        ..., ge=0, description="Позиція картки в межах етапу (0 = перша зверху)"
    )


class CardOut(CardBase):
    id: UUID
    board_id: UUID
    stage_id: UUID
    status: CardStatus
    position: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CardListResponse(BaseModel):
    items: list[CardOut]
    pagination: PaginationMeta


# --------------------------------------------------------------------------- #
# Card links (FR-009)
# --------------------------------------------------------------------------- #

class CardLinkCreate(BaseModel):
    url: HttpUrl = Field(..., description="Посилання на тестове завдання (валідний URL)")


class CardLinkOut(BaseModel):
    id: UUID
    card_id: UUID
    url: HttpUrl
    created_at: datetime

    model_config = {"from_attributes": True}