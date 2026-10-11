"""
Інструмент: Claude
Застосування: Налаштування середовища Alembic: адреса БД з DATABASE_URL і
метадані таблиць з repositories/sql.py для автогенерації міграцій.
Верифікація: Перевірено upgrade/downgrade та `alembic check` проти PostgreSQL
у Docker Compose.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from src.api.db import database_url
from src.api.repositories.sql import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
