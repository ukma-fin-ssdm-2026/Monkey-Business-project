# Інструмент: Claude
# Застосування: Образ Backend API (FastAPI + Uvicorn) з міграціями Alembic при старті;
# запуск від непривілейованого користувача app (SonarCloud docker:S6471, Лаб 8).
# Верифікація: Перевірено вручну збірку образу та запуск через docker compose;
# після переходу на app: id -u у контейнері не 0, міграції, /health і запис
# docs/api/openapi-generated.yaml працюють.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.lock .
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.lock

# app owns only docs/api: lifespan in src/api/main.py rewrites the OpenAPI spec
# there on every start. Code and packages stay root-owned and read-only for app.
RUN useradd --system --no-create-home app \
    && mkdir -p docs/api \
    && chown app docs/api

COPY alembic.ini .
COPY migrations ./migrations
COPY src ./src

USER app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000"]
