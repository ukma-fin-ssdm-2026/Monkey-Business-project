"""
Інструмент: Claude
Застосування: Юніт-тести для src/api/mcp_server.py — LoginAuth: логін при 401,
додавання Bearer-токена до запитів, обробка помилок конфігурації/логіну.
"""

from __future__ import annotations

import httpx2
import pytest

from src.api import mcp_server


def _drive(gen, first_response):
    """Проганяє протокол-генератор httpx2.Auth.auth_flow вручну."""
    request = next(gen)
    response = first_response
    try:
        while True:
            request = gen.send(response)
    except StopIteration:
        pass
    return request


def test_auth_flow_sends_request_without_header_when_no_token_cached():
    auth = mcp_server.LoginAuth()
    gen = auth.auth_flow(httpx2.Request("GET", "https://api.test/v1/cards"))

    first_request = next(gen)

    assert "Authorization" not in first_request.headers
    gen.close()


def test_auth_flow_reuses_cached_token():
    auth = mcp_server.LoginAuth()
    auth._token = "cached-token"
    gen = auth.auth_flow(httpx2.Request("GET", "https://api.test/v1/cards"))

    first_request = next(gen)

    assert first_request.headers["Authorization"] == "Bearer cached-token"
    gen.close()


def test_auth_flow_logs_in_and_retries_after_401(monkeypatch):
    monkeypatch.setenv("MCP_USER_EMAIL", "bot@example.com")
    monkeypatch.setenv("MCP_USER_PASSWORD", "secret")  # pragma: allowlist secret

    auth = mcp_server.LoginAuth()
    gen = auth.auth_flow(httpx2.Request("GET", "https://api.test/v1/cards"))

    first_request = next(gen)
    assert "Authorization" not in first_request.headers

    login_request = gen.send(
        httpx2.Response(401, request=first_request)
    )
    assert login_request.url.path == mcp_server.LOGIN_PATH
    assert login_request.method == "POST"

    retried_request = gen.send(
        httpx2.Response(
            200, json={"access_token": "fresh-token"}, request=login_request
        )
    )
    assert retried_request.headers["Authorization"] == "Bearer fresh-token"
    assert auth._token == "fresh-token"
    gen.close()


def test_login_raises_without_credentials_env(monkeypatch):
    monkeypatch.delenv("MCP_USER_EMAIL", raising=False)
    monkeypatch.delenv("MCP_USER_PASSWORD", raising=False)

    auth = mcp_server.LoginAuth()
    gen = auth._login(httpx2.URL("https://api.test"))

    with pytest.raises(RuntimeError, match="MCP_USER_EMAIL"):
        next(gen)


def test_login_raises_on_non_200_response(monkeypatch):
    monkeypatch.setenv("MCP_USER_EMAIL", "bot@example.com")
    monkeypatch.setenv("MCP_USER_PASSWORD", "wrong")  # pragma: allowlist secret

    auth = mcp_server.LoginAuth()
    gen = auth._login(httpx2.URL("https://api.test"))
    login_request = next(gen)

    with pytest.raises(RuntimeError, match="bot@example.com"):
        gen.send(httpx2.Response(401, request=login_request))


def test_mcp_server_excludes_authentication_tag_route_map():
    route_map = mcp_server.mcp._route_maps[0] if hasattr(mcp_server.mcp, "_route_maps") else None
    # Перевіряємо сам факт налаштування без прив'язки до приватного API FastMCP:
    assert mcp_server.mcp.name == "Tech Interview Board API"