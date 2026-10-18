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
    assert validate_vacancy_url(123) is False
    assert validate_vacancy_url([]) is False


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


@pytest.mark.parametrize(
    "url",
    ["https:///path-without-host", "http://", "HTTP://LOCALHOST/admin"],
    ids=["no-host", "scheme-only", "uppercase-localhost"],
)
def test_validate_vacancy_url_rejects_missing_or_blocked_host(url):
    assert validate_vacancy_url(url) is False


def test_validate_vacancy_url_returns_false_for_unparsable_url():
    # urlparse raises ValueError for an invalid IPv6 literal; the validator must not crash.
    assert validate_vacancy_url("http://[invalid-ipv6/path") is False


def test_validate_vacancy_url_ignores_surrounding_whitespace():
    assert validate_vacancy_url("  https://dou.ua/vacancies/1  ") is True
