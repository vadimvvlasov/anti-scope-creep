"""Product analytics events (docs/analytics.md).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("distinct_id", sa.String(length=64), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    op.create_index("ix_events_received_at", "events", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_events_received_at", table_name="events")
    op.drop_table("events")
