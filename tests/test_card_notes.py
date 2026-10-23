"""
Інструмент: Claude
Застосування: Юніт-тести для роутера card_notes.py (CRUD над нотатками/фідбеком, FR-011, FR-022).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.api.routers import card_notes
from src.api.domain import Board, Card, CardNote, User
from src.api.errors import ForbiddenError, NotFoundError
from src.api.repositories.base import Repositories
from src.api.schemas import CardNoteCreate, CardNoteUpdate, NoteSource


class InMemoryRepository:
    def __init__(self) -> None:
        self.items: dict = {}

    def add(self, entity):
        self.items[entity.id] = entity
        return entity

    def get(self, entity_id):
        return self.items.get(entity_id)

    def save(self, entity):
        self.items[entity.id] = entity
        return entity

    def delete(self, entity_id) -> None:
        self.items.pop(entity_id, None)


class InMemoryBoardRepository(InMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.mentor_access: set[tuple[UUID, UUID]] = set()

    def mentor_has_access(self, board_id: UUID, mentor_id: UUID) -> bool:
        return (board_id, mentor_id) in self.mentor_access


class InMemoryCardChildRepository(InMemoryRepository):
    def list_for_card(self, card_id: UUID):
        return [i for i in self.items.values() if i.card_id == card_id]


def _repositories(**overrides) -> Repositories:
    defaults = dict(
        users=InMemoryRepository(),
        boards=InMemoryBoardRepository(),
        stages=InMemoryRepository(),
        cards=InMemoryRepository(),
        links=InMemoryRepository(),
        notes=InMemoryCardChildRepository(),
    )
    defaults.update(overrides)
    return Repositories(**defaults)


def _user(role: str = "candidate") -> User:
    return User(email="user@example.com", password_hash="unused", role=role) # pragma: allowlist secret


def _card(board_id: UUID) -> Card:
    return Card(
        board_id=board_id,
        stage_id=uuid4(),
        company="Acme Corp",
        position="Backend Engineer",
        position_index=0,
    )


@pytest.fixture
def repos():
    return _repositories()


@pytest.fixture
def board_and_card(repos):
    owner = _user()
    board = repos.boards.add(Board(owner_id=owner.id))
    card = repos.cards.add(_card(board.id))
    return owner, board, card


# --------------------------------------------------------------------------- #
# list_notes
# --------------------------------------------------------------------------- #


def test_list_notes_returns_notes_in_order(repos, board_and_card):
    owner, board, card = board_and_card
    repos.notes.add(CardNote(card_id=card.id, content="перша", source="candidate"))
    repos.notes.add(CardNote(card_id=card.id, content="друга", source="recruiter"))

    result = card_notes.list_notes(board.id, card.id, owner, repos)

    assert [n.content for n in result] == ["перша", "друга"]
    assert result[1].source == NoteSource.recruiter


def test_list_notes_rejects_unknown_card(repos, board_and_card):
    owner, board, _card = board_and_card

    with pytest.raises(NotFoundError):
        card_notes.list_notes(board.id, uuid4(), owner, repos)


# --------------------------------------------------------------------------- #
# create_note
# --------------------------------------------------------------------------- #


def test_create_note_adds_note_with_default_source(repos, board_and_card):
    owner, board, card = board_and_card
    payload = CardNoteCreate(content="текст нотатки")

    result = card_notes.create_note(payload, board.id, card.id, owner, repos)

    assert result.content == "текст нотатки"
    assert result.source == NoteSource.candidate
    assert len(repos.notes.list_for_card(card.id)) == 1


def test_create_note_stores_explicit_source(repos, board_and_card):
    owner, board, card = board_and_card
    payload = CardNoteCreate(content="фідбек рекрутера", source=NoteSource.recruiter)

    result = card_notes.create_note(payload, board.id, card.id, owner, repos)

    stored = repos.notes.get(result.id)
    assert stored.source == "recruiter"


def test_create_note_denies_mentor(repos, board_and_card):
    _owner, board, card = board_and_card
    mentor = _user(role="mentor")
    repos.boards.mentor_access.add((board.id, mentor.id))
    payload = CardNoteCreate(content="спроба ментора")

    with pytest.raises(ForbiddenError):
        card_notes.create_note(payload, board.id, card.id, mentor, repos)


def test_create_note_rejects_blank_content_at_schema_level():
    with pytest.raises(ValueError):
        CardNoteCreate(content="   ")


# --------------------------------------------------------------------------- #
# update_note
# --------------------------------------------------------------------------- #


def test_update_note_changes_content_and_updated_at(repos, board_and_card):
    owner, board, card = board_and_card
    note = repos.notes.add(CardNote(card_id=card.id, content="стара", source="candidate"))
    payload = CardNoteUpdate(content="нова")

    result = card_notes.update_note(payload, board.id, card.id, note.id, owner, repos)

    assert result.content == "нова"
    assert repos.notes.get(note.id).content == "нова"
    assert repos.notes.get(note.id).updated_at >= note.created_at


def test_update_note_raises_for_unknown_note(repos, board_and_card):
    owner, board, card = board_and_card
    payload = CardNoteUpdate(content="нова")

    with pytest.raises(NotFoundError):
        card_notes.update_note(payload, board.id, card.id, uuid4(), owner, repos)


def test_update_note_denies_mentor(repos, board_and_card):
    _owner, board, card = board_and_card
    note = repos.notes.add(CardNote(card_id=card.id, content="стара", source="candidate"))
    mentor = _user(role="mentor")
    repos.boards.mentor_access.add((board.id, mentor.id))
    payload = CardNoteUpdate(content="нова")

    with pytest.raises(ForbiddenError):
        card_notes.update_note(payload, board.id, card.id, note.id, mentor, repos)


# --------------------------------------------------------------------------- #
# delete_note
# --------------------------------------------------------------------------- #


def test_delete_note_removes_existing_note(repos, board_and_card):
    owner, board, card = board_and_card
    note = repos.notes.add(CardNote(card_id=card.id, content="x", source="candidate"))

    card_notes.delete_note(board.id, card.id, note.id, owner, repos)

    assert repos.notes.get(note.id) is None


def test_delete_note_raises_for_note_of_other_card(repos, board_and_card):
    owner, board, card = board_and_card
    other_card = repos.cards.add(_card(board.id))
    note = repos.notes.add(CardNote(card_id=other_card.id, content="x", source="candidate"))

    with pytest.raises(NotFoundError):
        card_notes.delete_note(board.id, card.id, note.id, owner, repos)