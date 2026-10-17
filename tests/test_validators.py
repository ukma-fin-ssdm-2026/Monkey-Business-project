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
