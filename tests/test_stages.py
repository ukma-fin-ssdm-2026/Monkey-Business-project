"""
Тести для модуля src/api/routers/stages.py:
- Отримання списку етапів (FR-003, сортування за order_index).
- Створення нових етапів з явним або автоматичним order_index (FR-024).
- Оновлення назви та порядку етапів.
- Видалення етапу та захист від видалення при наявності карток (409 Conflict).
- Перевірка прав доступу: кандидат-власник, адміністратор, read-only ментор, сторонній користувач.

Використано шаблон AAA (Arrange - Act - Assert), фікстури pytest,
in-memory тестові дублери (заглушки) репозиторіїв та Mock.
"""

from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.api.domain import Board, Stage, User
from src.api.errors import ConflictError, ForbiddenError, NotFoundError
from src.api.repositories.base import Repositories
from src.api.routers import stages as stages_router
from src.api.schemas import StageCreate, StageUpdate, UserRole


# --------------------------------------------------------------------------- #
# Тестові дублери (In-Memory Fakes)
# --------------------------------------------------------------------------- #


class InMemoryBoardRepository:
    def __init__(self) -> None:
        self.items: dict = {}
        self.mentor_access: set[tuple] = set()

    def add(self, board: Board) -> Board:
        self.items[board.id] = board
        return board

    def get(self, board_id):
        return self.items.get(board_id)

    def mentor_has_access(self, board_id, mentor_id) -> bool:
        return (board_id, mentor_id) in self.mentor_access


class InMemoryStageRepository:
    def __init__(self) -> None:
        self.items: dict = {}
        self.stages_with_cards: set = set()

    def add(self, stage: Stage) -> Stage:
        self.items[stage.id] = stage
        return stage

    def get(self, stage_id):
        return self.items.get(stage_id)

    def save(self, stage: Stage) -> Stage:
        self.items[stage.id] = stage
        return stage

    def delete(self, stage_id) -> None:
        self.items.pop(stage_id, None)

    def list_for_board(self, board_id) -> list[Stage]:
        matching = [s for s in self.items.values() if s.board_id == board_id]
        return sorted(matching, key=lambda s: s.order_index)

    def has_cards(self, stage_id) -> bool:
        return stage_id in self.stages_with_cards


# --------------------------------------------------------------------------- #
# Фікстури (Fixtures)
# --------------------------------------------------------------------------- #


@pytest.fixture
def owner() -> User:
    return User(
        email="candidate.owner@example.com",
        password_hash="hash",
        role=UserRole.candidate.value,
    )


@pytest.fixture
def other_candidate() -> User:
    return User(
        email="stranger@example.com",
        password_hash="hash",
        role=UserRole.candidate.value,
    )


@pytest.fixture
def admin_user() -> User:
    return User(
        email="admin@example.com",
        password_hash="hash",
        role=UserRole.admin.value,
    )


@pytest.fixture
def mentor_user() -> User:
    return User(
        email="mentor@example.com",
        password_hash="hash",
        role=UserRole.mentor.value,
    )


@pytest.fixture
def board(owner) -> Board:
    return Board(owner_id=owner.id)


@pytest.fixture
def stage_repo() -> InMemoryStageRepository:
    return InMemoryStageRepository()


@pytest.fixture
def board_repo(board) -> InMemoryBoardRepository:
    repo = InMemoryBoardRepository()
    repo.add(board)
    return repo


@pytest.fixture
def repos(board_repo, stage_repo) -> Repositories:
    return Repositories(
        users=Mock(),
        boards=board_repo,
        stages=stage_repo,
        cards=Mock(),
        links=Mock(),
        notes=Mock(),
    )


# --------------------------------------------------------------------------- #
# Тести: list_stages (FR-003)
# --------------------------------------------------------------------------- #


def test_list_stages_returns_sorted_by_order_index(repos, board, owner):
    # Arrange
    repos.stages.add(Stage(board_id=board.id, name="Офер", order_index=3))
    repos.stages.add(Stage(board_id=board.id, name="Скринінг", order_index=1))
    repos.stages.add(Stage(board_id=board.id, name="Відгук", order_index=0))

    # Act
    result = stages_router.list_stages(board_id=board.id, user=owner, repos=repos)

    # Assert
    assert [s.name for s in result] == ["Відгук", "Скринінг", "Офер"]
    assert [s.order_index for s in result] == [0, 1, 3]


def test_list_stages_raises_not_found_for_missing_board(repos, owner):
    # Arrange
    missing_board_id = uuid4()

    # Act & Assert
    with pytest.raises(NotFoundError) as exc_info:
        stages_router.list_stages(
            board_id=missing_board_id, user=owner, repos=repos
        )
    assert f"Дошку {missing_board_id} не знайдено" in str(exc_info.value)


def test_list_stages_forbidden_for_stranger_candidate(repos, board, other_candidate):
    # Arrange & Act & Assert
    with pytest.raises(ForbiddenError):
        stages_router.list_stages(
            board_id=board.id, user=other_candidate, repos=repos
        )


def test_list_stages_allows_mentor_with_access(
    repos, board_repo, board, mentor_user
):
    # Arrange
    board_repo.mentor_access.add((board.id, mentor_user.id))
    repos.stages.add(Stage(board_id=board.id, name="Відгук", order_index=0))

    # Act
    result = stages_router.list_stages(
        board_id=board.id, user=mentor_user, repos=repos
    )

    # Assert
    assert len(result) == 1
    assert result[0].name == "Відгук"


# --------------------------------------------------------------------------- #
# Тести: create_stage (FR-024)
# --------------------------------------------------------------------------- #


def test_create_stage_auto_assigns_order_index(repos, board, owner):
    # Arrange
    repos.stages.add(Stage(board_id=board.id, name="Етап 1", order_index=0))
    repos.stages.add(Stage(board_id=board.id, name="Етап 2", order_index=1))
    payload = StageCreate(name="Новий етап")

    # Act
    created = stages_router.create_stage(
        payload=payload, board_id=board.id, user=owner, repos=repos
    )

    # Assert
    assert created.name == "Новий етап"
    assert created.order_index == 2
    assert repos.stages.get(created.id) is not None


def test_create_stage_with_explicit_order_index(repos, board, owner):
    # Arrange
    payload = StageCreate(name="Кастомний етап", order_index=10)

    # Act
    created = stages_router.create_stage(
        payload=payload, board_id=board.id, user=owner, repos=repos
    )

    # Assert
    assert created.order_index == 10
    assert repos.stages.get(created.id).order_index == 10


def test_create_stage_forbidden_for_mentor_read_only(
    repos, board_repo, board, mentor_user
):
    # Arrange
    board_repo.mentor_access.add((board.id, mentor_user.id))
    payload = StageCreate(name="Спроба створення ментором")

    # Act & Assert
    with pytest.raises(ForbiddenError):
        stages_router.create_stage(
            payload=payload, board_id=board.id, user=mentor_user, repos=repos
        )


def test_create_stage_allowed_for_admin(repos, board, admin_user):
    # Arrange
    payload = StageCreate(name="Етап створений адміном")

    # Act
    created = stages_router.create_stage(
        payload=payload, board_id=board.id, user=admin_user, repos=repos
    )

    # Assert
    assert created.name == "Етап створений адміном"
    assert repos.stages.get(created.id) is not None


# --------------------------------------------------------------------------- #
# Тести: update_stage
# --------------------------------------------------------------------------- #


def test_update_stage_name_and_order_success(repos, board, owner):
    # Arrange
    stage = repos.stages.add(Stage(board_id=board.id, name="Стара назва", order_index=1))
    payload = StageUpdate(name="Нова назва", order_index=5)

    # Act
    updated = stages_router.update_stage(
        payload=payload, board_id=board.id, stage_id=stage.id, user=owner, repos=repos
    )

    # Assert
    assert updated.name == "Нова назва"
    assert updated.order_index == 5
    saved = repos.stages.get(stage.id)
    assert saved.name == "Нова назва"
    assert saved.order_index == 5


def test_update_stage_partial_update_only_name(repos, board, owner):
    # Arrange
    stage = repos.stages.add(Stage(board_id=board.id, name="Стара назва", order_index=3))
    payload = StageUpdate(name="Оновлена назва")

    # Act
    updated = stages_router.update_stage(
        payload=payload, board_id=board.id, stage_id=stage.id, user=owner, repos=repos
    )

    # Assert
    assert updated.name == "Оновлена назва"
    assert updated.order_index == 3


def test_update_stage_raises_not_found_for_missing_stage(repos, board, owner):
    # Arrange
    payload = StageUpdate(name="Нова")
    missing_stage_id = uuid4()

    # Act & Assert
    with pytest.raises(NotFoundError) as exc_info:
        stages_router.update_stage(
            payload=payload,
            board_id=board.id,
            stage_id=missing_stage_id,
            user=owner,
            repos=repos,
        )
    assert f"Етап {missing_stage_id} на дошці {board.id} не знайдено" in str(
        exc_info.value
    )


def test_update_stage_raises_not_found_when_stage_belongs_to_different_board(
    repos, board, owner
):
    # Arrange
    other_board_id = uuid4()
    stage = repos.stages.add(Stage(board_id=other_board_id, name="Чужий етап", order_index=0))
    payload = StageUpdate(name="Зміна")

    # Act & Assert
    with pytest.raises(NotFoundError):
        stages_router.update_stage(
            payload=payload,
            board_id=board.id,
            stage_id=stage.id,
            user=owner,
            repos=repos,
        )


# --------------------------------------------------------------------------- #
# Тести: delete_stage & Edge Cases (409 Conflict)
# --------------------------------------------------------------------------- #


def test_delete_stage_success_when_stage_has_no_cards(repos, board, owner):
    # Arrange
    stage = repos.stages.add(Stage(board_id=board.id, name="Порожній етап", order_index=0))

    # Act
    stages_router.delete_stage(
        board_id=board.id, stage_id=stage.id, user=owner, repos=repos
    )

    # Assert
    assert repos.stages.get(stage.id) is None


def test_delete_stage_raises_conflict_when_stage_has_cards(repos, board, owner):
    # Arrange: Граничний випадок цілісності даних (FR-024)
    stage = repos.stages.add(Stage(board_id=board.id, name="Етап із картками", order_index=0))
    repos.stages.stages_with_cards.add(stage.id)

    # Act & Assert
    with pytest.raises(ConflictError) as exc_info:
        stages_router.delete_stage(
            board_id=board.id, stage_id=stage.id, user=owner, repos=repos
        )
    assert "Неможливо видалити етап, у якому є картки" in str(exc_info.value)
    # Перевірка що етап не видалився
    assert repos.stages.get(stage.id) is not None


def test_delete_stage_raises_not_found_for_nonexistent_stage(repos, board, owner):
    # Arrange
    missing_stage_id = uuid4()

    # Act & Assert
    with pytest.raises(NotFoundError):
        stages_router.delete_stage(
            board_id=board.id, stage_id=missing_stage_id, user=owner, repos=repos
        )


def test_delete_stage_forbidden_for_stranger(repos, board, other_candidate):
    # Arrange
    stage = repos.stages.add(Stage(board_id=board.id, name="Етап", order_index=0))

    # Act & Assert
    with pytest.raises(ForbiddenError):
        stages_router.delete_stage(
            board_id=board.id, stage_id=stage.id, user=other_candidate, repos=repos
        )
