"""
Валідатори бізнес-правил для карток та вакансій (US-003).
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"http", "https"})


def _is_localhost_name(host: str) -> bool:
    """RFC 6761: localhost і всі його піддомени вказують на loopback."""
    return host == "localhost" or host.endswith(".localhost")


def _is_private_ip(host: str) -> bool:
    """is_private охоплює також loopback (127.0.0.1, ::1), 0.0.0.0 і link-local."""
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def _is_safe_host(hostname: str | None) -> bool:
    """Перевіряє, чи не є хост внутрішньою або забороненою локальною адресою."""
    if not hostname:
        return False
    normalized = hostname.strip().lower()
    return not (_is_private_ip(normalized) or _is_localhost_name(normalized))


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
