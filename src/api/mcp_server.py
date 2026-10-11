"""
Інструмент: Claude
Застосування: Генерація MCP-сервера з FastAPI-застосунку через FastMCP.from_fastapi.
Верифікація: Перевірено вручну списком інструментів і викликами list_cards /
create_card через MCP-клієнт.

MCP-сервер, згенерований з API.

Кожна кінцева точка FastAPI стає MCP-інструментом: назва — ім'я функції-обробника
= operationId (list_cards, create_card, ...), опис і схема
параметрів — з анотацій та OpenAPI.
Нові кінцеві точки з'являються як інструменти автоматично, без змін у цьому файлі.

Запуск (stdio, для Claude Code / Claude Desktop / Cursor):
    python -m src.api.mcp_server
"""

from fastmcp import FastMCP

from .main import app

# Requests go to the app in-process via ASGI, so no running HTTP server is needed.
mcp = FastMCP.from_fastapi(app, name="Tech Interview Board API")

if __name__ == "__main__":
    mcp.run()
