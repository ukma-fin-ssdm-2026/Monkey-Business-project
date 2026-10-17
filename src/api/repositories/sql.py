"""
Інструмент: Claude
Застосування: Реалізація інтерфейсів репозиторіїв для PostgreSQL на SQLAlchemy 2.0
та опис таблиць за моделлю даних.
Верифікація: Схему звірено з data-model.md; CRUD-операції перевірено через
API проти PostgreSQL у Docker Compose.

Реалізація репозиторіїв на SQLAlchemy.

Таблиці відповідають data-model.md. Типи колонок переносні (Uuid, DateTime з
часовою зоною, Enum як VARCHAR + CHECK), тож модуль не залежить від
специфічних типів PostgreSQL. Запити будуються через ORM і завжди
параметризовані (ризик R3 у threat-model.md).
"""

from __future__ import annotations

from dataclasses import asdict, fields
from datetime import datetime
from typing import Generic, Optional, TypeVar
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    delete,
    exists,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from ..domain import Board, BoardMentor, Card, CardLink, CardNote, Stage, User
from .base import Repositories


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
    type_annotation_map = {datetime: DateTime(timezone=True)}


def _enum(name: str, *values: str) -> Enum:
    # VARCHAR + CHECK instead of a native PostgreSQL enum type: adding a value
    # is a plain migration and the schema stays portable to other databases.
    return Enum(
        *values, name=name, native_enum=False, create_constraint=True, length=20
    )


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        _enum("user_role", "candidate", "mentor", "admin")
    )
    is_active: Mapped[bool]
    created_at: Mapped[datetime]


class BoardRow(Base):
    __tablename__ = "boards"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    created_at: Mapped[datetime]


class StageRow(Base):
    __tablename__ = "stages"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    board_id: Mapped[UUID] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    order_index: Mapped[int]
    created_at: Mapped[datetime]


class CardRow(Base):
    __tablename__ = "cards"
    __table_args__ = (
        Index(
            "ix_cards_board_stage_position", "board_id", "stage_id", "position_index"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    board_id: Mapped[UUID] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"))
    stage_id: Mapped[UUID] = mapped_column(
        ForeignKey("stages.id", ondelete="RESTRICT"), index=True
    )
    company: Mapped[str] = mapped_column(String(200))
    position: Mapped[str] = mapped_column(String(200))
    vacancy_url: Mapped[Optional[str]] = mapped_column(String(2048))
    requirements_text: Mapped[Optional[str]] = mapped_column(Text)
    deadline: Mapped[Optional[datetime]]
    notifications_enabled: Mapped[bool]
    status: Mapped[str] = mapped_column(
        _enum("card_status", "active", "rejected", "offer_accepted")
    )
    position_index: Mapped[int]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class CardLinkRow(Base):
    __tablename__ = "card_links"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    card_id: Mapped[UUID] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime]


class CardNoteRow(Base):
    __tablename__ = "card_notes"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    card_id: Mapped[UUID] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(
        _enum("note_source", "candidate", "recruiter", "ai")
    )
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class BoardMentorRow(Base):
    __tablename__ = "board_mentors"
    __table_args__ = (UniqueConstraint("board_id", "mentor_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    board_id: Mapped[UUID] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"))
    mentor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    invite_token: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(
        _enum("mentor_status", "pending", "accepted", "revoked")
    )
    invited_at: Mapped[datetime]
    accepted_at: Mapped[Optional[datetime]]


E = TypeVar("E")


class _SqlRepository(Generic[E]):
    # Row columns are named exactly like the domain dataclass fields,
    # so rows and entities convert field by field.
    row_type: type[Base]
    entity_type: type[E]

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_entity(self, row: Base) -> E:
        return self.entity_type(
            **{f.name: getattr(row, f.name) for f in fields(self.entity_type)}
        )

    def add(self, entity: E) -> E:
        self._session.add(self.row_type(**asdict(entity)))
        # Flush right away so inserts reach the database in call order and
        # foreign keys between rows added in one request are satisfied.
        self._session.flush()
        return entity

    def get(self, entity_id: UUID) -> Optional[E]:
        row = self._session.get(self.row_type, entity_id)
        return None if row is None else self._to_entity(row)

    def save(self, entity: E) -> E:
        self._session.merge(self.row_type(**asdict(entity)))
        self._session.flush()
        return entity

    def delete(self, entity_id: UUID) -> None:
        self._session.execute(
            delete(self.row_type).where(self.row_type.id == entity_id)
        )


class SqlUserRepository(_SqlRepository[User]):
    row_type = UserRow
    entity_type = User

    def get_by_email(self, email: str) -> Optional[User]:
        row = self._session.scalar(select(UserRow).where(UserRow.email == email))
        return None if row is None else self._to_entity(row)


class SqlBoardRepository(_SqlRepository[Board]):
    row_type = BoardRow
    entity_type = Board

    def mentor_has_access(self, board_id: UUID, mentor_id: UUID) -> bool:
        return bool(
            self._session.scalar(
                select(
                    exists().where(
                        BoardMentorRow.board_id == board_id,
                        BoardMentorRow.mentor_id == mentor_id,
                        BoardMentorRow.status == "accepted",
                    )
                )
            )
        )


class SqlStageRepository(_SqlRepository[Stage]):
    row_type = StageRow
    entity_type = Stage

    def list_for_board(self, board_id: UUID) -> list[Stage]:
        rows = self._session.scalars(
            select(StageRow)
            .where(StageRow.board_id == board_id)
            .order_by(StageRow.order_index, StageRow.created_at)
        )
        return [self._to_entity(row) for row in rows]

    def has_cards(self, stage_id: UUID) -> bool:
        return bool(
            self._session.scalar(select(exists().where(CardRow.stage_id == stage_id)))
        )


class SqlCardRepository(_SqlRepository[Card]):
    row_type = CardRow
    entity_type = Card

    def list_for_board(
        self, board_id: UUID, stage_id: Optional[UUID], status: Optional[str]
    ) -> list[Card]:
        query = select(CardRow).where(CardRow.board_id == board_id)
        if stage_id is not None:
            query = query.where(CardRow.stage_id == stage_id)
        if status is not None:
            query = query.where(CardRow.status == status)
        rows = self._session.scalars(
            query.order_by(CardRow.position_index, CardRow.created_at)
        )
        return [self._to_entity(row) for row in rows]

    def count_in_stage(self, stage_id: UUID) -> int:
        return self._session.scalar(
            select(func.count())
            .select_from(CardRow)
            .where(CardRow.stage_id == stage_id)
        )


class SqlCardLinkRepository(_SqlRepository[CardLink]):
    row_type = CardLinkRow
    entity_type = CardLink

    def list_for_card(self, card_id: UUID) -> list[CardLink]:
        rows = self._session.scalars(
            select(CardLinkRow)
            .where(CardLinkRow.card_id == card_id)
            .order_by(CardLinkRow.created_at)
        )
        return [self._to_entity(row) for row in rows]


class SqlCardNoteRepository(_SqlRepository[CardNote]):
    row_type = CardNoteRow
    entity_type = CardNote

    def list_for_card(self, card_id: UUID) -> list[CardNote]:
        rows = self._session.scalars(
            select(CardNoteRow)
            .where(CardNoteRow.card_id == card_id)
            .order_by(CardNoteRow.created_at)
        )
        return [self._to_entity(row) for row in rows]


class SqlBoardMentorRepository(_SqlRepository[BoardMentor]):
    row_type = BoardMentorRow
    entity_type = BoardMentor

    def get_by_token(self, token: str) -> Optional[BoardMentor]:
        row = self._session.scalar(
            select(BoardMentorRow).where(BoardMentorRow.invite_token == token)
        )
        return None if row is None else self._to_entity(row)

    def get_by_board_and_mentor(
        self, board_id: UUID, mentor_id: UUID
    ) -> Optional[BoardMentor]:
        row = self._session.scalar(
            select(BoardMentorRow).where(
                BoardMentorRow.board_id == board_id,
                BoardMentorRow.mentor_id == mentor_id,
            )
        )
        return None if row is None else self._to_entity(row)

    def list_for_board(self, board_id: UUID) -> list[BoardMentor]:
        rows = self._session.scalars(
            select(BoardMentorRow)
            .where(BoardMentorRow.board_id == board_id)
            .order_by(BoardMentorRow.invited_at)
        )
        return [self._to_entity(row) for row in rows]

    def list_for_mentor(self, mentor_id: UUID) -> list[BoardMentor]:
        rows = self._session.scalars(
            select(BoardMentorRow)
            .where(BoardMentorRow.mentor_id == mentor_id)
            .order_by(BoardMentorRow.invited_at)
        )
        return [self._to_entity(row) for row in rows]


def build_repositories(session: Session) -> Repositories:
    return Repositories(
        users=SqlUserRepository(session),
        boards=SqlBoardRepository(session),
        stages=SqlStageRepository(session),
        cards=SqlCardRepository(session),
        links=SqlCardLinkRepository(session),
        notes=SqlCardNoteRepository(session),
        mentors=SqlBoardMentorRepository(session),
    )
