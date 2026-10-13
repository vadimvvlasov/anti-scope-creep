"""Analysis starts per user, for the per-user daily analysis cap (security finding MR-2).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_starts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_analysis_starts_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_starts")),
    )
    op.create_index("ix_analysis_starts_user_id_started_at", "analysis_starts", ["user_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_analysis_starts_user_id_started_at", table_name="analysis_starts")
    op.drop_table("analysis_starts")
