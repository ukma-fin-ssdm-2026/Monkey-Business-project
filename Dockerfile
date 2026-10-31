# Інструмент: Claude
# Застосування: Образ Backend API (FastAPI + Uvicorn) з міграціями Alembic при старті.
# Верифікація: Перевірено вручну збірку образу та запуск через docker compose.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.lock .
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.lock

COPY alembic.ini .
COPY migrations ./migrations
COPY src ./src

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000"]
