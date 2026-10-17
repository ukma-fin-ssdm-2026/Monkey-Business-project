"""
Інструмент: Claude
Застосування: Створення Pydantic-схем для валідації вхідних даних,
генерації OpenAPI моделей та стандартизації повідомлень про помилки.
Верифікація: Усі типи даних та обмеження (Field) перевірені вручну на
відповідність вимогам проєкту, узгоджено командою.

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

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

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
    code: str = Field(
        ..., examples=["VALIDATION_ERROR"], description="Машиночитаний код помилки"
    )
    message: str = Field(..., description="Людиночитане повідомлення про помилку")
    details: list[ErrorDetail] = Field(
        default_factory=list, description="Деталі по кожному полю"
    )
    request_id: str = Field(..., description="Ідентифікатор запиту для пошуку в логах")
    documentation: Optional[str] = Field(
        default=None,
        description="Посилання на розділ документації з поясненням помилки",
    )


class ErrorResponse(BaseModel):
    """Єдиний каркас помилки для всіх кінцевих точок API."""

    error: ErrorBody = Field(..., description="Опис помилки")


class UserRole(str, Enum):
    candidate = "candidate"
    mentor = "mentor"
    admin = "admin"


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., examples=["candidate@example.com"])
    password: str = Field(
        ..., min_length=8, max_length=128, examples=["correct-horse-battery"]
    )
    role: UserRole = Field(default=UserRole.candidate, examples=["candidate"])


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["candidate@example.com"])
    password: str = Field(
        ..., min_length=1, max_length=128, examples=["correct-horse-battery"]
    )


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    role: UserRole
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT Bearer access token")
    token_type: str = Field(default="bearer", examples=["bearer"])
    expires_in: int = Field(..., ge=1, description="Token lifetime in seconds")
    user: UserOut


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
        ...,
        min_length=1,
        max_length=200,
        description="Назва компанії (обов'язкове поле, FR-007)",
        examples=["Acme Corp"],
    )
    position: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Назва позиції (обов'язкове поле, FR-007)",
        examples=["Backend Engineer"],
    )
    vacancy_url: Optional[HttpUrl] = Field(
        default=None,
        description="Посилання на оригінальну вакансію",
        examples=["https://acme.example.com/jobs/42"],
    )
    requirements_text: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Текст вимог вакансії (FR-007, FR-003 розширення)",
        examples=["3+ роки Python, знання FastAPI"],
    )
    deadline: Optional[datetime] = Field(
        default=None,
        description="Дедлайн тестового завдання або співбесіди (FR-010)",
        examples=["2026-10-20T18:00:00Z"],
    )
    notifications_enabled: bool = Field(
        default=True, description="Чи увімкнені нагадування для цієї картки (FR-018)"
    )

    @field_validator("company", "position")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("поле не може бути порожнім рядком")
        return value


class CardCreate(CardBase):
    """Тіло запиту на створення картки (FR-007)."""

    stage_id: UUID = Field(
        ...,
        description="Етап, у якому створюється картка",
        examples=["22222222-2222-2222-2222-222222222222"],
    )


class CardUpdate(BaseModel):
    """Часткове оновлення картки (PATCH, FR-008) — усі поля опційні."""

    company: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Нова назва компанії",
        examples=["Acme Corp"],
    )
    position: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Нова назва позиції",
        examples=["Senior Backend Engineer"],
    )
    vacancy_url: Optional[HttpUrl] = Field(
        default=None,
        description="Нове посилання на вакансію",
        examples=["https://acme.example.com/jobs/42"],
    )
    requirements_text: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Новий текст вимог вакансії",
    )
    deadline: Optional[datetime] = Field(
        default=None,
        description="Новий дедлайн (FR-010)",
        examples=["2026-10-20T18:00:00Z"],
    )
    notifications_enabled: Optional[bool] = Field(
        default=None,
        description="Увімкнути або вимкнути нагадування (FR-018)",
        examples=[False],
    )
    status: Optional[CardStatus] = Field(
        default=None,
        description="Закриття картки: 'rejected' або 'offer_accepted' (FR-006)",
        examples=["rejected"],
    )

    @model_validator(mode="after")
    def require_change(self) -> "CardUpdate":
        if not self.model_fields_set:
            raise ValueError("потрібно вказати хоча б одне поле для оновлення")
        return self


class CardMove(BaseModel):
    """Переміщення картки між етапами методом drag-and-drop (FR-004, FR-005)."""

    stage_id: UUID = Field(
        ...,
        description="Ідентифікатор цільового етапу",
        examples=["22222222-2222-2222-2222-222222222222"],
    )
    position_index: int = Field(
        ...,
        ge=0,
        description="Порядок картки в межах етапу (0 = перша зверху)",
        examples=[0],
    )


class CardOut(CardBase):
    id: UUID = Field(..., description="Ідентифікатор картки")
    board_id: UUID = Field(..., description="Дошка, якій належить картка")
    stage_id: UUID = Field(..., description="Поточний етап картки")
    status: CardStatus = Field(
        ..., description="Статус картки: активна або закрита (FR-006)"
    )
    # Not "position": that name is the job title inherited from CardBase (FR-007).
    position_index: int = Field(
        ..., ge=0, description="Порядок картки в межах етапу (0 = перша зверху)"
    )
    created_at: datetime = Field(..., description="Час створення")
    updated_at: datetime = Field(..., description="Час останньої зміни")

    model_config = {"from_attributes": True}


class CardListResponse(BaseModel):
    items: list[CardOut] = Field(..., description="Картки поточної сторінки")
    pagination: PaginationMeta = Field(
        ..., description="Параметри пагінації та загальна кількість"
    )


# --------------------------------------------------------------------------- #
# Card links (FR-009)
# --------------------------------------------------------------------------- #


class CardLinkCreate(BaseModel):
    url: HttpUrl = Field(
        ...,
        description="Посилання на тестове завдання (валідний URL)",
        examples=["https://github.com/acme/test-task"],
    )


class CardLinkOut(BaseModel):
    id: UUID = Field(..., description="Ідентифікатор посилання")
    card_id: UUID = Field(..., description="Картка, до якої додано посилання")
    url: HttpUrl = Field(..., description="Посилання на тестове завдання")
    created_at: datetime = Field(..., description="Час додавання")

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Stages (FR-003, FR-024)
# --------------------------------------------------------------------------- #


class StageBase(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Назва етапу (FR-003)",
        examples=["Технічне інтерв'ю"],
    )

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("назва етапу не може бути порожнім рядком")
        return value.strip()


class StageCreate(StageBase):
    order_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Порядок сортування етапу на дошці",
        examples=[4],
    )


class StageUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Нова назва етапу",
        examples=["Фінальна бесіда"],
    )
    order_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Новий порядок сортування етапу",
        examples=[2],
    )

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("назва етапу не може бути порожнім рядком")
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> "StageUpdate":
        if not self.model_fields_set:
            raise ValueError("потрібно вказати хоча б одне поле для оновлення")
        return self


class StageOut(StageBase):
    id: UUID = Field(..., description="Ідентифікатор етапу")
    board_id: UUID = Field(..., description="Дошка, якій належить етап")
    order_index: int = Field(..., ge=0, description="Порядок сортування етапу на дошці")
    created_at: datetime = Field(..., description="Час створення етапу")

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Card Notes (FR-011, FR-022)
# --------------------------------------------------------------------------- #


class NoteSource(str, Enum):
    candidate = "candidate"
    recruiter = "recruiter"
    ai = "ai"


class CardNoteCreate(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=3000,
        description="Текст нотатки або фідбеку (FR-011)",
        examples=["Скринінг пройдено. Запропонували технічне завдання до п'ятниці."],
    )
    source: NoteSource = Field(
        default=NoteSource.candidate,
        description="Джерело нотатки: кандидат, фідбек рекрутера або AI (FR-011, FR-022)",
        examples=["recruiter"],
    )

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("вміст нотатки не може бути порожнім рядком")
        return value.strip()


class CardNoteUpdate(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=3000,
        description="Оновлений текст нотатки",
        examples=["Уточнено дедлайн: понеділок 18:00."],
    )

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("вміст нотатки не може бути порожнім рядком")
        return value.strip()


class CardNoteOut(BaseModel):
    id: UUID = Field(..., description="Ідентифікатор нотатки")
    card_id: UUID = Field(..., description="Картка, до якої належить нотатка")
    content: str = Field(..., description="Текст нотатки або фідбеку")
    source: NoteSource = Field(..., description="Джерело нотатки")
    created_at: datetime = Field(..., description="Час створення нотатки")
    updated_at: datetime = Field(..., description="Час останньої зміни нотатки")

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Ментори та запрошення (FR-012, US-002)
# --------------------------------------------------------------------------- #


class MentorStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    revoked = "revoked"


class InviteMentorRequest(BaseModel):
    email: EmailStr = Field(
        ...,
        examples=["mentor@example.com"],
        description="Email ментора, якого запрошують до перегляду дошки",
    )


class BoardMentorOut(BaseModel):
    id: UUID = Field(..., description="Ідентифікатор запрошення/зв'язку")
    board_id: UUID = Field(..., description="Ідентифікатор дошки")
    mentor_id: UUID = Field(..., description="Ідентифікатор користувача-ментора")
    email: EmailStr = Field(..., description="Email ментора")
    status: MentorStatus = Field(
        ..., description="Поточний статус запрошення (pending, accepted, revoked)"
    )
    invite_token: str = Field(
        ...,
        examples=["k7X9vL2mQ8n4P1z0R3t5Y6u7I8o9W0e1"],
        description="Одноразовий токен запрошення",
    )
    invited_at: datetime = Field(..., description="Дата і час надсилання запрошення")
    accepted_at: Optional[datetime] = Field(
        default=None, description="Дата і час прийняття запрошення"
    )

    model_config = {"from_attributes": True}


class AcceptInvitationRequest(BaseModel):
    password: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=128,
        examples=["correct-horse-battery"],
        description="Пароль для активації нового облікового запису ментора",
    )


class AcceptInvitationResponse(BaseModel):
    message: str = Field(..., examples=["Запрошення успішно прийнято"])
    board_id: UUID = Field(
        ...,
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
        description="Ідентифікатор дошки, до якої надано доступ",
    )
    status: MentorStatus = Field(
        default=MentorStatus.accepted,
        examples=["accepted"],
        description="Новий статус запрошення",
    )
    access_token: Optional[str] = Field(
        default=None,
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
        description="JWT токен, якщо під час прийняття було активовано акаунт із паролем",
    )
    token_type: str = Field(default="bearer", examples=["bearer"])


# --------------------------------------------------------------------------- #
# Коментарі ментора до карток (FR-013, US-002)
# --------------------------------------------------------------------------- #


class CommentCreate(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=3000,
        description="Текст коментаря (1–3000 символів)",
        examples=["Зверніть увагу на вимоги до Go, варто підготуватись."],
    )

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("вміст коментаря не може бути порожнім рядком")
        return value.strip()


class CommentOut(BaseModel):
    id: UUID = Field(..., description="Ідентифікатор коментаря")
    card_id: UUID = Field(..., description="Картка, до якої належить коментар")
    author_id: UUID = Field(..., description="Ідентифікатор автора коментаря")
    content: str = Field(..., description="Текст коментаря")
    created_at: datetime = Field(..., description="Дата і час створення коментаря")

    model_config = {"from_attributes": True}
