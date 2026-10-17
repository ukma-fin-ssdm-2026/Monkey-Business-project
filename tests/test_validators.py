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
