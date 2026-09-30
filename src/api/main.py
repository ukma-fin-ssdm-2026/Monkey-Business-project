"""
Інструмент: Claude
Застосування: Генерація конфігурації FastAPI, підключення роутерів та налаштування автогенерації OpenAPI YAML через lifespan.
Верифікація: Перевірено вручну локальним запуском сервера, підключення роутерів узгоджено командою.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
import yaml
import os

from .errors import register_error_handlers
from .routers import card_links, cards

def save_openapi_spec(app: FastAPI):
    """Автоматичне збереження OpenAPI специфікації у YAML"""
    openapi_schema = app.openapi()

    os.makedirs("docs/api", exist_ok=True)

    with open("docs/api/openapi-generated.yaml", "w", encoding="utf-8") as f:
        yaml.dump(openapi_schema, f, sort_keys=False, allow_unicode=True)
    print("✅ OpenAPI специфікація автоматично згенерована у docs/api/openapi-generated.yaml")

@asynccontextmanager
async def lifespan(app: FastAPI):
    save_openapi_spec(app)
    yield

app = FastAPI(
    title="Tech Interview Board API",
    version="0.1.0",
    description="REST API для трекера підготовки до технічних співбесід (Code-First).",
    lifespan=lifespan
)

register_error_handlers(app)

app.include_router(cards.router)
app.include_router(card_links.router)

@app.get("/health", tags=["Meta"])
def health() -> dict:
    return {"status": "ok"}