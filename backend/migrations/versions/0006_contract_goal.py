"""Store the user's goal for a contract (docs/spec.md "Contract goal").

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GOALS = ("before_signing", "negotiating", "already_signed", "just_curious")


def upgrade() -> None:
    allowed = ", ".join(f"'{value}'" for value in GOALS)
    with op.batch_alter_table("contracts") as batch:
        batch.add_column(sa.Column("goal", sa.String(length=32), nullable=True))
        batch.create_check_constraint(op.f("ck_contracts_goal"), f"goal IN ({allowed})")


def downgrade() -> None:
    with op.batch_alter_table("contracts") as batch:
        batch.drop_constraint(op.f("ck_contracts_goal"), type_="check")
        batch.drop_column("goal")
