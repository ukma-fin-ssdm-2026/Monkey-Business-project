"""
Валідатори бізнес-правил для карток та вакансій (US-003).

Інструмент: Claude Code
Застосування: Лаб 9, R4 — звуження except Exception до ValueError з логуванням.
Верифікація: tests/test_validators.py і tests/reliability/test_url_validator.py.
"""

from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

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
    normalized = hostname.strip().lower().rstrip(".")
    return not (_is_private_ip(normalized) or _is_localhost_name(normalized))


def validate_vacancy_url(url: str | None) -> bool:
    """Перевіряє коректність посилання на вакансію або тестове завдання."""
    if not url or not isinstance(url, str):
        return False
    cleaned = url.strip()
    try:
        parsed = urlparse(cleaned)
        hostname = parsed.hostname
    except ValueError as exc:
        # Malformed input such as "http://[::1" is rejected; any other exception
        # is a defect in this validator and must surface, not look like bad input.
        logger.info("Rejected unparsable vacancy URL: %s", exc)
        return False
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False
    return _is_safe_host(hostname)
