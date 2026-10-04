# Запуск API
 
```bash
pip install -r requirements.txt
uvicorn src.api.main:app --reload --port 3000
python -m src.api.main   # згенерувати docs/api/openapi-generated.yaml без запуску сервера
```
 
- Swagger UI: http://localhost:3000/api-docs
- Специфікація OpenAPI (JSON, генерується автоматично з коду): http://localhost:3000/openapi.json
- Специфікація OpenAPI (YAML): [`docs/api/openapi-generated.yaml`](../../docs/api/openapi-generated.yaml) — оновлюється при кожному запуску сервера

Дані зберігаються в пам'яті (`store.py`) — це заглушка для демонстрації
Code-First підходу.

# MCP-сервер

`src/api/mcp_server.py` генерує MCP-сервер з FastAPI-застосунку (`FastMCP.from_fastapi`):
кожна кінцева точка стає інструментом, який AI-агент (Claude Code, Claude Desktop, Cursor)
може викликати. Назва інструмента — `operationId` (`list_cards`, `create_card`, `move_card`, ...),
опис і параметри беруться з анотацій API. Окремо запускати uvicorn не потрібно — запити
обробляються застосунком у тому ж процесі.

```bash
python -m src.api.mcp_server   # stdio-транспорт
```

Підключення до Claude Code (з кореня репозиторію):

```bash
claude mcp add interview-board -- python -m src.api.mcp_server
```

Для Claude Desktop / Cursor — у конфігурацію MCP-серверів:

```json
{
  "mcpServers": {
    "interview-board": {
      "command": "python",
      "args": ["-m", "src.api.mcp_server"],
      "cwd": "/шлях/до/Monkey-Business-project"
    }
  }
}
```

Демо-дошка для перевірки: `board_id = 11111111-1111-1111-1111-111111111111`.
