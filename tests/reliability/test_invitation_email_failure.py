"""
Інструмент: Claude
Застосування: Тести надійності R2 (Лаб 9): ін'єкція відмови Mailtrap і
відсутньої конфігурації під час надсилання запрошення ментору.
Верифікація: тести запущено через pytest; без виправлення R2 вони падають
(RuntimeError → сирий 500, текст Mailtrap у повідомленні клієнту).

Обрана реакція — швидка відмова: 503 з нейтральним повідомленням, транзакція
відкочується, тож запрошення без листа не з'являється.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import requests

from src.api.errors import ServiceUnavailableError
from src.api.routers import mentors

INBOX_LEAK = "https://sandbox.api.mailtrap.io/api/send/4439163"
RECIPIENT = "mentor@example.com"


@pytest.fixture
def mailtrap_client(monkeypatch) -> MagicMock:
    """Тестовий дублер клієнта Mailtrap замість мережевого виклику."""
    client = MagicMock()
    monkeypatch.setattr(mentors, "MAILTRAP_API_TOKEN", "fake-token")
    monkeypatch.setattr(mentors.mt, "MailtrapClient", MagicMock(return_value=client))
    return client


def _send() -> None:
    mentors._send_invitation_email(RECIPIENT, "invite-token", uuid4())


# Тест зовнішньої відмови (ін'єкція збою)
@pytest.mark.parametrize(
    "failure",
    [
        requests.Timeout(f"Read timed out for url: {INBOX_LEAK}"),
        requests.ConnectionError(f"Connection refused: {INBOX_LEAK}"),
        mentors.mt.AuthorizationError(["Unauthorized: token abc*** has no access"]),
    ],
    ids=["timeout", "connection-refused", "unauthorized"],
)
def test_mailtrap_failure_becomes_neutral_503(mailtrap_client, caplog, failure):
    mailtrap_client.send.side_effect = failure

    with caplog.at_level(logging.WARNING, logger=mentors.__name__):
        with pytest.raises(ServiceUnavailableError) as exc_info:
            _send()

    message = exc_info.value.message
    assert message == mentors.EMAIL_UNAVAILABLE_MESSAGE
    assert "mailtrap" not in message.lower()
    assert RECIPIENT not in message
    # The cause is not lost: it is in the log for the team.
    assert str(failure) in caplog.text


# Тест обробки помилки
def test_missing_token_is_a_503_not_a_raw_500(monkeypatch, caplog):
    monkeypatch.setattr(mentors, "MAILTRAP_API_TOKEN", None)

    with caplog.at_level(logging.ERROR, logger=mentors.__name__):
        with pytest.raises(ServiceUnavailableError):
            _send()

    assert "MAILTRAP_API_TOKEN" in caplog.text


def test_bug_in_our_code_is_not_masked_as_provider_outage(mailtrap_client):
    mailtrap_client.send.side_effect = TypeError("bad mail field")

    with pytest.raises(TypeError):
        _send()


def test_recipient_email_is_not_logged_on_success(mailtrap_client, caplog):
    with caplog.at_level(logging.INFO, logger=mentors.__name__):
        _send()

    assert "Invitation email sent" in caplog.text
    assert RECIPIENT not in caplog.text
