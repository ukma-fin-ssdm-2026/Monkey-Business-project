"""
Інструмент: Claude
Застосування: Тести надійності R3 (Лаб 9): межі блокування входу, його
закінчення за часом і збереження лічильника попри відкат транзакції запиту.
Верифікація: тести запущено через pytest; без виправлення R3 вони падають
(лічильник у БД лишається 0, блокування не закінчується).

Обрана реакція — безпечна відмова з обмеженням у часі: після
MAX_FAILED_ATTEMPTS невдалих спроб вхід закрито на LOCKOUT_DURATION,
далі обліковий запис відновлюється сам, без ручного UPDATE у БД.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from src.api import auth
from src.api.repositories.sql import SqlLoginAttemptRepository, UserRow

EMAIL = "user@example.com"
PASSWORD = "correct-pass-1"  # pragma: allowlist secret
WRONG = "wrong-pass-xx"  # pragma: allowlist secret


def _login(client, password: str):
    return client.post("/v1/auth/login", json={"email": EMAIL, "password": password})


def _user_row(session_factory) -> UserRow:
    with session_factory() as session:
        return session.scalars(select(UserRow).where(UserRow.email == EMAIL)).one()


def _set_lock(session_factory, locked_until: datetime | None, attempts: int) -> None:
    with session_factory.begin() as session:
        row = session.scalars(select(UserRow).where(UserRow.email == EMAIL)).one()
        row.locked_until = locked_until
        row.failed_login_attempts = attempts


@pytest.fixture
def registered(client) -> None:
    response = client.post(
        "/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "role": "candidate"},
    )
    assert response.status_code == 201


# Тест обробки помилки: 401 відкочує транзакцію, але лічильник лишається
def test_failed_attempts_survive_request_rollback(client, session_factory, registered):
    for _ in range(3):
        assert _login(client, WRONG).status_code == 401

    assert _user_row(session_factory).failed_login_attempts == 3


# Граничний тест: остання дозволена спроба ще не блокує
def test_one_attempt_below_limit_still_allows_correct_password(
    client, session_factory, registered
):
    for _ in range(auth.MAX_FAILED_ATTEMPTS - 1):
        assert _login(client, WRONG).status_code == 401

    assert _login(client, PASSWORD).status_code == 200
    row = _user_row(session_factory)
    assert (row.failed_login_attempts, row.locked_until) == (0, None)


# Граничний тест: спроба на межі встановлює блокування з кінцем у часі
def test_reaching_the_limit_sets_a_lock_with_an_end(
    client, session_factory, registered
):
    before = datetime.now(timezone.utc)
    for _ in range(auth.MAX_FAILED_ATTEMPTS):
        assert _login(client, WRONG).status_code == 401

    row = _user_row(session_factory)
    assert row.failed_login_attempts == auth.MAX_FAILED_ATTEMPTS
    # SQLite drops the time zone; PostgreSQL keeps it.
    locked_until = row.locked_until.replace(tzinfo=timezone.utc)
    assert locked_until - before == pytest.approx(
        auth.LOCKOUT_DURATION, abs=timedelta(seconds=5)
    )


def test_active_lock_rejects_even_the_correct_password(
    client, session_factory, registered
):
    until = datetime.now(timezone.utc) + timedelta(minutes=10)
    _set_lock(session_factory, until, auth.MAX_FAILED_ATTEMPTS)

    response = _login(client, PASSWORD)

    assert response.status_code == 403
    assert f"{until:%H:%M} UTC" in response.json()["error"]["message"]


def test_expired_lock_is_released_without_manual_db_update(
    client, session_factory, registered
):
    _set_lock(
        session_factory,
        datetime.now(timezone.utc) - timedelta(seconds=1),
        auth.MAX_FAILED_ATTEMPTS,
    )

    assert _login(client, PASSWORD).status_code == 200
    row = _user_row(session_factory)
    assert (row.failed_login_attempts, row.locked_until) == (0, None)


# Граничний тест: спроби понад ліміт (паралельна «хвиля») не доходять до
# перевірки пароля, навіть якщо пароль правильний
def test_attempts_past_the_limit_are_rejected_before_password_check(
    client, session_factory, registered, monkeypatch
):
    _set_lock(session_factory, None, auth.MAX_FAILED_ATTEMPTS)
    checked: list[str] = []
    monkeypatch.setattr(
        auth, "_verify_password", lambda password, encoded: checked.append(password)
    )

    response = _login(client, PASSWORD)

    assert response.status_code == 403
    assert checked == []


def test_register_attempt_numbers_attempts_and_locks_at_limit(
    session_factory, registered
):
    attempts = SqlLoginAttemptRepository(session_factory)
    user_id = _user_row(session_factory).id
    until = datetime(2030, 1, 1, tzinfo=timezone.utc)

    numbers = [
        attempts.register_attempt(user_id, lock_at=3, lock_until=until)
        for _ in range(4)
    ]

    assert numbers == [1, 2, 3, 4]
    assert _user_row(session_factory).locked_until is not None
