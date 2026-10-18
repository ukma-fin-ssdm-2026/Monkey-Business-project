"""Persist the login counter already used by auth.py.

Revision ID: 0003
Revises: 0002

Використання ШІ: Codex — усунення невідповідності User та UserRow.
Перевірка: регресійні тести ORM-перетворення та генерація SQL міграції.
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "failed_login_attempts")
