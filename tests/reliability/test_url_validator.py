"""
Інструмент: Claude Code
Застосування: Лаб 9, R4 — тести вузького catch у validate_vacancy_url:
некоректний URL безпечно відхиляється й логується, а дефект валідатора не
маскується під невалідний ввід.
Верифікація: запуск pytest tests/reliability.
"""

from __future__ import annotations

import logging

import pytest

from src.api import validators


@pytest.mark.parametrize(
    "url",
    ["http://[::1", "http://[invalid-ipv6/path", "https://[", "http://[::1]x/"],
)
def test_unparsable_url_is_rejected_and_logged(url, caplog):
    with caplog.at_level(logging.INFO, logger=validators.__name__):
        assert validators.validate_vacancy_url(url) is False
    assert "unparsable vacancy URL" in caplog.text


def test_validator_defect_is_not_masked_as_invalid_input(monkeypatch):
    """Fault injection: the host check breaks with a programming error."""

    def broken_host_check(_hostname):
        raise AttributeError("bug inside validator")

    monkeypatch.setattr(validators, "_is_safe_host", broken_host_check)

    with pytest.raises(AttributeError, match="bug inside validator"):
        validators.validate_vacancy_url("https://dou.ua/vacancies/1")


def test_valid_public_url_still_accepted():
    assert validators.validate_vacancy_url("https://dou.ua/vacancies/1") is True
