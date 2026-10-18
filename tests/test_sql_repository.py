"""Регресії невідповідності User та SQL-моделі.

Використання ШІ: Codex — два тести дефекту лічильника входів;
перевірка через pytest. Сесію БД замінено моком.
"""

from dataclasses import asdict
from unittest.mock import Mock

from sqlalchemy.orm import Session

from src.api.domain import User
from src.api.repositories.sql import SqlUserRepository, UserRow


def test_user_repository_stores_failed_login_attempts():
    # Arrange
    user = User(
        email="user@example.com",
        password_hash="unused",
        role="candidate",
        failed_login_attempts=4,
    )
    session = Mock(spec=Session)

    # Act
    result = SqlUserRepository(session).add(user)

    # Assert
    row = session.add.call_args.args[0]
    assert (row.id, row.failed_login_attempts) == (user.id, 4)
    assert result is user
    session.flush.assert_called_once_with()


def test_user_repository_restores_failed_login_attempts():
    # Arrange
    user = User(
        email="user@example.com",
        password_hash="unused",
        role="candidate",
        failed_login_attempts=5,
    )
    session = Mock(spec=Session)
    session.get.return_value = UserRow(**asdict(user))

    # Act
    result = SqlUserRepository(session).get(user.id)

    # Assert
    assert result == user
    session.get.assert_called_once_with(UserRow, user.id)
