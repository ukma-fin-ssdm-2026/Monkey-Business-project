"""
Інструмент: Claude
Застосування: Генерація конфігурації FastAPI, підключення роутерів та налаштування автогенерації OpenAPI YAML через lifespan.
Верифікація: Перевірено вручну локальним запуском сервера, підключення роутерів узгоджено командою.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
import yaml
from pathlib import Path

from .errors import register_error_handlers
from .routers import card_links, cards

SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi-generated.yaml"

def save_openapi_spec(app: FastAPI):
    """Автоматичне збереження OpenAPI специфікації у YAML"""
    openapi_schema = app.openapi()

    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        print(f"✅ OpenAPI специфікація автоматично згенерована у {SPEC_PATH}")
    except UnicodeEncodeError:
        print(f"[OK] OpenAPI spec generated at {SPEC_PATH}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    save_openapi_spec(app)
    yield

app = FastAPI(
    title="Tech Interview Board API",
    version="0.1.0",
    description="REST API для трекера підготовки до технічних співбесід (Code-First).",
    lifespan=lifespan,
    docs_url="/api-docs",
    # Clean operationIds (list_cards instead of list_cards_v1_boards__board_id__cards_get);
    # they also become the MCP tool names in mcp_server.py, so handler names must stay unique.
    generate_unique_id_function=lambda route: route.name,
)

register_error_handlers(app)

app.include_router(cards.router, prefix="/v1")
app.include_router(card_links.router, prefix="/v1")

@app.get(
    "/health",
    tags=["Meta"],
    summary="Перевірка стану сервісу",
    description="Повертає 200, якщо сервіс працює. Використовується зовнішнім моніторингом доступності (REL-1).",
)
def health() -> dict:
    return {"status": "ok"}

if __name__ == "__main__":
    save_openapi_spec(app)
