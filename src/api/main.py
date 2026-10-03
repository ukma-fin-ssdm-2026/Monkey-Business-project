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

    with SPEC_PATH.open("w", encoding="utf-8") as f:
        yaml.dump(openapi_schema, f, sort_keys=False, allow_unicode=True)
    print(f"✅ OpenAPI специфікація автоматично згенерована у {SPEC_PATH}")

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
)

register_error_handlers(app)

app.include_router(cards.router)
app.include_router(card_links.router)

@app.get("/health", tags=["Meta"])
def health() -> dict:
    return {"status": "ok"}

if __name__ == "__main__":
    save_openapi_spec(app)
