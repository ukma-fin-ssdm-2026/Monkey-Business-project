"""
Інструмент: Claude
Застосування: Юніт-тести для роутера card_links.py (CRUD над посиланнями картки, FR-009).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.api.routers import card_links
from src.api.domain import Board, Card, CardLink, User
from src.api.errors import ForbiddenError, NotFoundError
from src.api.repositories.base import Repositories
from src.api.schemas import CardLinkCreate


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
        links=InMemoryCardChildRepository(),
        notes=InMemoryRepository(),
    )
    defaults.update(overrides)
    return Repositories(**defaults)


def _user(role: str = "candidate") -> User:
    return User(email="user@example.com", password_hash="unused", role=role)


def _card(board_id: UUID, stage_id: UUID | None = None) -> Card:
    return Card(
        board_id=board_id,
        stage_id=stage_id or uuid4(),
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
# list_links
# --------------------------------------------------------------------------- #


def test_list_links_returns_links_for_card(repos, board_and_card):
    owner, board, card = board_and_card
    repos.links.add(CardLink(card_id=card.id, url="https://example.com/task"))
    other_card = repos.cards.add(_card(board.id))
    repos.links.add(CardLink(card_id=other_card.id, url="https://example.com/other"))

    result = card_links.list_links(board.id, card.id, owner, repos)

    assert len(result) == 1
    assert str(result[0].url).startswith("https://example.com/task")


def test_list_links_rejects_unknown_board(repos, board_and_card):
    owner, _board, card = board_and_card

    with pytest.raises(NotFoundError):
        card_links.list_links(uuid4(), card.id, owner, repos)


def test_list_links_rejects_card_from_other_board(repos, board_and_card):
    owner, board, _existing_card = board_and_card
    foreign_card = repos.cards.add(_card(uuid4()))

    with pytest.raises(NotFoundError):
        card_links.list_links(board.id, foreign_card.id, owner, repos)


def test_list_links_denies_mentor_without_access(repos, board_and_card):
    _owner, board, card = board_and_card
    mentor = _user(role="mentor")

    with pytest.raises(ForbiddenError):
        card_links.list_links(board.id, card.id, mentor, repos)


def test_list_links_allows_invited_mentor(repos, board_and_card):
    _owner, board, card = board_and_card
    mentor = _user(role="mentor")
    repos.boards.mentor_access.add((board.id, mentor.id))

    result = card_links.list_links(board.id, card.id, mentor, repos)

    assert result == []


# --------------------------------------------------------------------------- #
# create_link
# --------------------------------------------------------------------------- #


def test_create_link_adds_link_to_card(repos, board_and_card):
    owner, board, card = board_and_card
    payload = CardLinkCreate(url="https://example.com/task")

    result = card_links.create_link(payload, board.id, card.id, owner, repos)

    assert str(result.url).startswith("https://example.com/task")
    assert len(repos.links.list_for_card(card.id)) == 1


def test_create_link_denies_mentor_write_access(repos, board_and_card):
    _owner, board, card = board_and_card
    mentor = _user(role="mentor")
    repos.boards.mentor_access.add((board.id, mentor.id))  # read-only, не write
    payload = CardLinkCreate(url="https://example.com/task")

    with pytest.raises(ForbiddenError):
        card_links.create_link(payload, board.id, card.id, mentor, repos)


def test_create_link_rejects_invalid_url_at_schema_level():
    with pytest.raises(ValueError):
        CardLinkCreate(url="not-a-url")


# --------------------------------------------------------------------------- #
# delete_link
# --------------------------------------------------------------------------- #


def test_delete_link_removes_existing_link(repos, board_and_card):
    owner, board, card = board_and_card
    link = repos.links.add(CardLink(card_id=card.id, url="https://example.com/task"))

    card_links.delete_link(board.id, card.id, link.id, owner, repos)

    assert repos.links.get(link.id) is None


def test_delete_link_raises_for_unknown_link(repos, board_and_card):
    owner, board, card = board_and_card

    with pytest.raises(NotFoundError):
        card_links.delete_link(board.id, card.id, uuid4(), owner, repos)


def test_delete_link_raises_when_link_belongs_to_other_card(repos, board_and_card):
    owner, board, card = board_and_card
    other_card = repos.cards.add(_card(board.id))
    link = repos.links.add(CardLink(card_id=other_card.id, url="https://example.com/x"))

    with pytest.raises(NotFoundError):
        card_links.delete_link(board.id, card.id, link.id, owner, repos)