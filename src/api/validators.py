"""
Валідатори бізнес-правил для карток та вакансій (US-003).
"""

from __future__ import annotations

from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"http", "https"})
BLOCKED_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "0.0.0.0"})


def _is_safe_host(hostname: str | None) -> bool:
    """Перевіряє, чи не є хост внутрішньою або забороненою локальною адресою."""
    if not hostname:
        return False
    normalized = hostname.strip().lower()
    return normalized not in BLOCKED_HOSTNAMES


def validate_vacancy_url(url: str | None) -> bool:
    """Перевіряє коректність посилання на вакансію або тестове завдання."""
    if not url or not isinstance(url, str):
        return False
    cleaned = url.strip()
    try:
        parsed = urlparse(cleaned)
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            return False
        return _is_safe_host(parsed.hostname)
    except Exception:
        return False
