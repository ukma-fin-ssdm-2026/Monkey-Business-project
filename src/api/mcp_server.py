"""
Інструмент: Claude
Застосування: Генерація MCP-сервера з FastAPI-застосунку через FastMCP.from_fastapi;
автентифікація MCP-сервера в API від імені налаштованого користувача.
Верифікація: Перевірено вручну списком інструментів і викликами list_cards /
create_card / list_stages / create_note через MCP-клієнт, зокрема повторний
вхід після недійсного токена та помилки за відсутніх або невірних облікових даних.

MCP-сервер, згенерований з API.

Кожна кінцева точка FastAPI стає MCP-інструментом: назва — ім'я функції-обробника
= operationId (list_cards, create_card, ...), опис і схема
параметрів — з анотацій та OpenAPI.
Нові кінцеві точки з'являються як інструменти автоматично, без змін у цьому файлі.

Ендпоінти дошки вимагають JWT (FR-001, SEC-2), тому сервер входить через
/v1/auth/login від імені користувача з MCP_USER_EMAIL / MCP_USER_PASSWORD і додає
Bearer-токен до кожного запиту. Агент діє з правами цього користувача: перевірки
RBAC не обходяться. Ендпоінти автентифікації як інструменти не публікуються —
агенту не потрібні ні пароль, ні токен.

Запуск (stdio, для Claude Code / Claude Desktop / Cursor):
    DATABASE_URL=... MCP_USER_EMAIL=... MCP_USER_PASSWORD=... python -m src.api.mcp_server
"""

from __future__ import annotations

import os
from collections.abc import Generator

import httpx2
from fastmcp import FastMCP
from fastmcp.server.providers.openapi import MCPType, RouteMap

from .main import app

LOGIN_PATH = "/v1/auth/login"


class LoginAuth(httpx2.Auth):
    """Bearer-автентифікація з токеном, отриманим через /v1/auth/login."""

    requires_request_body = True
    requires_response_body = True

    def __init__(self) -> None:
        self._token: str | None = None

    def auth_flow(
        self, request: httpx2.Request
    ) -> Generator[httpx2.Request, httpx2.Response, None]:
        if self._token is not None:
            request.headers["Authorization"] = f"Bearer {self._token}"
        response = yield request
        # Log in on the first 401 and again once the 24 h token (SEC-2) expires;
        # endpoints without auth, such as /health, work without credentials.
        if response.status_code == 401:
            self._token = yield from self._login(request.url)
            request.headers["Authorization"] = f"Bearer {self._token}"
            yield request

    def _login(
        self, url: httpx2.URL
    ) -> Generator[httpx2.Request, httpx2.Response, str]:
        email = os.getenv("MCP_USER_EMAIL")
        password = os.getenv("MCP_USER_PASSWORD")
        if not email or not password:
            raise RuntimeError(
                "Задайте MCP_USER_EMAIL і MCP_USER_PASSWORD — обліковий запис, від "
                "імені якого MCP-сервер працює з API (див. src/api/README.md)"
            )
        response = yield httpx2.Request(
            "POST", url.join(LOGIN_PATH), json={"email": email, "password": password}
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"MCP-сервер не зміг увійти як {email}: HTTP {response.status_code}"
            )
        return response.json()["access_token"]


# Requests go to the app in-process via ASGI, so no running HTTP server is needed.
mcp = FastMCP.from_fastapi(
    app,
    name="Tech Interview Board API",
    route_maps=[RouteMap(tags={"Authentication"}, mcp_type=MCPType.EXCLUDE)],
    httpx_client_kwargs={"auth": LoginAuth()},
)

if __name__ == "__main__":
    mcp.run()
