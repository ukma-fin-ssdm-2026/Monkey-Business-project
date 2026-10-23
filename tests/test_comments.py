"""
Інструмент: Claude
Застосування: Юніт-тести для роутера comments.py (коментарі до картки, FR-013, US-002).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.api.routers import comments as comments_router
from src.api.domain import Board, Card, Comment, User
from src.api.errors import ForbiddenError, NotFoundError
from src.api.repositories.base import Repositories
from src.api.schemas import CommentCreate


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
        notes=InMemoryRepository(),
        comments=InMemoryCardChildRepository(),
    )
    defaults.update(overrides)
    return Repositories(**defaults)


def _user(role: str = "candidate") -> User:
    return User(email="user@example.com", password_hash="unused", role=role)#pragma: allowlist secret


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
# list_comments
# --------------------------------------------------------------------------- #


def test_list_comments_returns_comments_for_card(repos, board_and_card):
    owner, board, card = board_and_card
    repos.comments.add(Comment(card_id=card.id, author_id=owner.id, content="перший"))

    result = comments_router.list_comments(board.id, card.id, owner, repos)

    assert [c.content for c in result] == ["перший"]


def test_list_comments_rejects_unknown_board(repos, board_and_card):
    owner, _board, card = board_and_card

    with pytest.raises(NotFoundError):
        comments_router.list_comments(uuid4(), card.id, owner, repos)


def test_list_comments_denies_uninvited_mentor(repos, board_and_card):
    _owner, board, card = board_and_card
    mentor = _user(role="mentor")

    with pytest.raises(ForbiddenError):
        comments_router.list_comments(board.id, card.id, mentor, repos)


# --------------------------------------------------------------------------- #
# create_comment
# --------------------------------------------------------------------------- #


def test_create_comment_allows_mentor_with_access(repos, board_and_card):
    _owner, board, card = board_and_card
    mentor = _user(role="mentor")
    repos.boards.mentor_access.add((board.id, mentor.id))
    payload = CommentCreate(content="коментар ментора")

    result = comments_router.create_comment(payload, board.id, card.id, mentor, repos)

    assert result.content == "коментар ментора"
    assert result.author_id == mentor.id


def test_create_comment_denies_mentor_without_access(repos, board_and_card):
    _owner, board, card = board_and_card
    mentor = _user(role="mentor")
    payload = CommentCreate(content="коментар ментора")

    with pytest.raises(ForbiddenError):
        comments_router.create_comment(payload, board.id, card.id, mentor, repos)


def test_create_comment_rejects_blank_content_at_schema_level():
    with pytest.raises(ValueError):
        CommentCreate(content="   ")


# --------------------------------------------------------------------------- #
# delete_comment
# --------------------------------------------------------------------------- #


def test_delete_comment_allows_author(repos, board_and_card):
    owner, board, card = board_and_card
    comment = repos.comments.add(
        Comment(card_id=card.id, author_id=owner.id, content="x")
    )

    comments_router.delete_comment(board.id, card.id, comment.id, owner, repos)

    assert repos.comments.get(comment.id) is None


def test_delete_comment_allows_admin_even_if_not_author(repos, board_and_card):
    owner, board, card = board_and_card
    admin = _user(role="admin")
    comment = repos.comments.add(
        Comment(card_id=card.id, author_id=owner.id, content="x")
    )

    comments_router.delete_comment(board.id, card.id, comment.id, admin, repos)

    assert repos.comments.get(comment.id) is None


def test_delete_comment_denies_other_non_admin_user(repos, board_and_card):
    owner, board, card = board_and_card
    other_candidate = _user(role="candidate")
    comment = repos.comments.add(
        Comment(card_id=card.id, author_id=owner.id, content="x")
    )

    with pytest.raises(ForbiddenError):
        comments_router.delete_comment(board.id, card.id, comment.id, other_candidate, repos)


def test_delete_comment_raises_for_unknown_comment(repos, board_and_card):
    owner, board, card = board_and_card

    with pytest.raises(NotFoundError):
        comments_router.delete_comment(board.id, card.id, uuid4(), owner, repos)


def test_delete_comment_raises_for_comment_of_other_card(repos, board_and_card):
    owner, board, card = board_and_card
    other_card = repos.cards.add(_card(board.id))
    comment = repos.comments.add(
        Comment(card_id=other_card.id, author_id=owner.id, content="x")
    )

    with pytest.raises(NotFoundError):
        comments_router.delete_comment(board.id, card.id, comment.id, owner, repos)