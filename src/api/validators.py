"""
Валідатори бізнес-правил для карток та вакансій (US-003).
"""

from __future__ import annotations

from urllib.parse import urlparse


def validate_vacancy_url(url: str | None) -> bool:
    """Перевіряє коректність посилання на вакансію або тестове завдання."""
    if not url or not isinstance(url, str):
        return False
    cleaned = url.strip()
    try:
        parsed = urlparse(cleaned)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False
