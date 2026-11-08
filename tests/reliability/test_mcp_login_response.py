"""
Інструмент: Claude Code
Застосування: Лаб 9, R9 — ін'єкція некоректної відповіді /v1/auth/login
(HTTP 200 з не-JSON тілом, без access_token, з порожнім чи нерядковим токеном).
MCP-сервер має швидко відмовити з чіткою помилкою інтеграції без витоку тіла.
Верифікація: запуск pytest tests/reliability.
"""

from __future__ import annotations

import logging

import httpx2
import pytest

from src.api import mcp_server

SECRET_LIKE = "leaked-token-fragment"  # pragma: allowlist secret


@pytest.fixture
def login_flow(monkeypatch):
    monkeypatch.setenv("MCP_USER_EMAIL", "bot@example.com")
    monkeypatch.setenv("MCP_USER_PASSWORD", "secret")  # pragma: allowlist secret
    gen = mcp_server.LoginAuth()._login(httpx2.URL("https://api.test"))
    request = next(gen)
    return gen, request


@pytest.mark.parametrize(
    ("kwargs", "case"),
    [
        ({"content": b"<html>" + SECRET_LIKE.encode() + b"</html>"}, "non-JSON body"),
        ({"json": {"token_type": "bearer"}}, "missing access_token"),
        ({"json": {"access_token": ""}}, "empty access_token"),
        ({"json": {"access_token": 12345}}, "non-string access_token"),
        ({"json": [SECRET_LIKE]}, "JSON array instead of object"),
    ],
)
def test_malformed_login_response_fails_with_clear_error(
    login_flow, kwargs, case, caplog
):
    gen, request = login_flow

    with caplog.at_level(logging.ERROR, logger=mcp_server.__name__):
        with pytest.raises(RuntimeError) as exc_info:
            gen.send(httpx2.Response(200, request=request, **kwargs))

    message = str(exc_info.value)
    assert message == mcp_server.LOGIN_RESPONSE_INVALID_MESSAGE, case
    # Neither the client-facing error nor the log echoes the response body.
    assert SECRET_LIKE not in message
    assert SECRET_LIKE not in caplog.text
    assert caplog.records, "the integration failure must be logged"


def test_valid_login_response_returns_token(login_flow):
    gen, request = login_flow

    with pytest.raises(StopIteration) as stop:
        gen.send(
            httpx2.Response(200, request=request, json={"access_token": "ok-token"})
        )

    assert stop.value.value == "ok-token"
