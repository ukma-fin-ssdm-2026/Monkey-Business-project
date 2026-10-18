"""
TDD: Модульні тести для валідатора URL вакансій (US-003).
"""

from __future__ import annotations

import pytest

from src.api.validators import validate_vacancy_url


def test_validate_vacancy_url_rejects_empty_and_non_string():
    assert validate_vacancy_url(None) is False
    assert validate_vacancy_url("") is False
    assert validate_vacancy_url("   ") is False


def test_validate_vacancy_url_requires_http_or_https_scheme():
    assert validate_vacancy_url("https://jobs.example.com/vacancies/123") is True
    assert validate_vacancy_url("http://company.org/careers") is True
    assert validate_vacancy_url("ftp://files.example.com/job.pdf") is False
    assert validate_vacancy_url("javascript:alert(1)") is False
    assert validate_vacancy_url("not-a-valid-url") is False


def test_validate_vacancy_url_rejects_localhost_and_internal_ips():
    assert validate_vacancy_url("http://localhost/admin") is False
    assert validate_vacancy_url("http://127.0.0.1:8000/internal") is False
    assert validate_vacancy_url("http://0.0.0.0/secret") is False
    assert validate_vacancy_url("https://dou.ua/vacancies/senior-python") is True


# Три тести нижче вбивають мутантів, що вижили після mutmut на validators.py
# (див. docs/testing/testing-strategy.md, розділ «Бонуси»).
def test_validate_vacancy_url_rejects_truthy_non_string():
    assert validate_vacancy_url(12345) is False
    assert validate_vacancy_url(["https://example.com"]) is False


def test_validate_vacancy_url_rejects_url_without_host():
    assert validate_vacancy_url("https://") is False
    assert validate_vacancy_url("http:///path/only") is False


def test_validate_vacancy_url_rejects_unparseable_url():
    assert validate_vacancy_url("http://[::1") is False
