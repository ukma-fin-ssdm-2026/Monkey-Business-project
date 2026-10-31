# Запуск API

## Docker Compose (API + PostgreSQL)

```bash
docker compose up -d --build
```

- Контейнер `api` при старті застосовує міграції (`alembic upgrade head`) і запускає uvicorn; API доступне на http://localhost:3000.
- Контейнер `db` — PostgreSQL 17. Порт опубліковано лише на `127.0.0.1`. Дані зберігаються в томі `pgdata` між перезапусками; `docker compose down -v` їх видаляє.
- Змінні (необов'язкові, можна задати у файлі `.env` у корені репозиторію): `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (за замовчуванням усі `interview_board`), `POSTGRES_PORT` (`5432`), `API_PORT` (`3000`). Якщо порт 5432 зайнятий локальним PostgreSQL: `POSTGRES_PORT=5434 docker compose up -d`.

## Локально (uvicorn з автоперезавантаженням)

```bash
pip install -r requirements.txt
docker compose up -d db
export DATABASE_URL=postgresql+psycopg://interview_board:interview_board@localhost:5432/interview_board  # pragma: allowlist secret
alembic upgrade head
uvicorn src.api.main:app --reload --port 3000
python -m src.api.main   # згенерувати docs/api/openapi-generated.yaml без запуску сервера (БД не потрібна)
```

- Swagger UI: http://localhost:3000/api-docs
- Специфікація OpenAPI (JSON, генерується автоматично з коду): http://localhost:3000/openapi.json
- Специфікація OpenAPI (YAML): [`docs/api/openapi-generated.yaml`](../../docs/api/openapi-generated.yaml) — оновлюється при кожному запуску сервера

## Шар доступу до даних

- Роутери (`routers/`) і `auth.py` працюють лише з інтерфейсами репозиторіїв (`repositories/base.py`) та доменними сутностями (`domain.py`) і не імпортують SQLAlchemy.
- Реалізація для PostgreSQL — `repositories/sql.py` (таблиці та репозиторії). Транзакція на запит і вибір реалізації — `db.py`. Щоб змінити СУБД, достатньо нової реалізації інтерфейсів і заміни `build_repositories` у `db.py`.
- Схема змінюється лише міграціями: `alembic revision --autogenerate -m "опис"` → переглянути файл у `migrations/versions/` → `alembic upgrade head`. Alembic дублює CHECK-обмеження для `Enum`-колонок: зайві `sa.CheckConstraint(...)` у згенерованій міграції треба прибрати, інакше PostgreSQL відхилить її.

# MCP-сервер

`src/api/mcp_server.py` генерує MCP-сервер з FastAPI-застосунку (`FastMCP.from_fastapi`):
кожна кінцева точка стає інструментом, який AI-агент (Claude Code, Claude Desktop, Cursor)
може викликати. Назва інструмента — `operationId` (`list_cards`, `create_card`, `move_card`, ...),
опис і параметри беруться з анотацій API. Окремо запускати uvicorn не потрібно — запити
обробляються застосунком у тому ж процесі, але йому потрібна база даних.

Інструментами стають усі кінцеві точки, крім `/v1/auth/*`: картки, посилання, етапи, нотатки
та `health`. Ендпоінти дошки вимагають JWT, тому MCP-сервер сам входить через `/v1/auth/login`
від імені облікового запису з `MCP_USER_EMAIL` / `MCP_USER_PASSWORD` і додає Bearer-токен до
кожного запиту (після закінчення 24-годинного токена — входить повторно). Агент має права
цього користувача: кандидат — повний доступ до своєї дошки, ментор — лише читання.
Без цих змінних працює тільки `health`, а решта інструментів повертає помилку з підказкою.

Підготовка:

1. Запустіть API та PostgreSQL: `docker compose up -d --build` (контейнер `api` застосовує міграції).
2. Зареєструйте кандидата, від імені якого працюватиме агент: `POST /v1/auth/register`, наприклад
   через Swagger UI (http://localhost:3000/api-docs). Разом з обліковим записом створюється його
   дошка з чотирма стандартними етапами.
3. Задайте змінні середовища: `DATABASE_URL` (як у розділі «Локально» вище), а також
   `MCP_USER_EMAIL` і `MCP_USER_PASSWORD` — email і пароль цього кандидата.

```bash
python -m src.api.mcp_server   # stdio-транспорт
```

Підключення до Claude Code (з кореня репозиторію). Агент запускає сервер окремим процесом,
тому `python` має бути інтерпретатором зі встановленими залежностями — інакше процес падає
на імпорті, а Claude Code показує лише `Failed to connect — Connection closed`:

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
claude mcp add interview-board -e DATABASE_URL="$DATABASE_URL" -e MCP_USER_EMAIL="$MCP_USER_EMAIL" -e MCP_USER_PASSWORD="$MCP_USER_PASSWORD" -- "$PWD/.venv/bin/python" -m src.api.mcp_server
claude mcp get interview-board   # Status: ✔ Connected
```

Якщо сервер уже додано без цих змінних, спершу видаліть його: `claude mcp remove interview-board -s local`.

Для Claude Desktop / Cursor — у конфігурацію MCP-серверів:

```json
{
  "mcpServers": {
    "interview-board": {
      "command": "/шлях/до/Monkey-Business-project/.venv/bin/python",
      "args": ["-m", "src.api.mcp_server"],
      "cwd": "/шлях/до/Monkey-Business-project",
      "env": {
        "DATABASE_URL": "значення DATABASE_URL з розділу вище",
        "MCP_USER_EMAIL": "<email>",
        "MCP_USER_PASSWORD": "<пароль>"
      }
    }
  }
}
```

`board_id` повертає `GET /v1/boards` («мої дошки»): кандидат отримує дошку, створену під час
реєстрації (`access: owner`), ментор — дошки, до яких прийняв запрошення (`access: mentor`).
Адміністратору список чужих дошок не повертається; він відкриває дошку за відомим `board_id`.

```bash
curl -H "Authorization: Bearer <access_token>" http://localhost:3000/v1/boards
```
