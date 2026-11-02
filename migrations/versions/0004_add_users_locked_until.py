"""Time-limited login lockout.

Revision ID: 0004
Revises: 0003

Інструмент: Claude
Застосування: Лаб 9, R3 — блокування входу до locked_until замість вічного
блокування за лічильником.
Верифікація: SQL міграції згенеровано офлайн (alembic upgrade --sql);
тести tests/reliability/test_login_lockout.py.
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    # Under the old rule a counter at the limit meant a lock with no way out.
    # Such rows get a fresh window rather than a lock with no end time.
    op.execute("UPDATE users SET failed_login_attempts = 0")


def downgrade() -> None:
    op.drop_column("users", "locked_until")
