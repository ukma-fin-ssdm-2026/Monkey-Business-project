"""
Валідатори бізнес-правил для карток та вакансій (US-003).
"""

from __future__ import annotations


def validate_vacancy_url(url: str | None) -> bool:
    if not url or not isinstance(url, str) or not url.strip():
        return False
    return True
