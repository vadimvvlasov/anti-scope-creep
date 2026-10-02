"""Initial schema: users, contracts, risk_findings, email_drafts (docs/spec.md "Data model").

Revision ID: 0001
Revises:
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FILE_TYPES = ("pdf", "txt")
STATUSES = ("uploaded", "analyzing", "done", "failed")
CATEGORIES = (
    "scope_creep",
    "unlimited_revisions",
    "one_sided_termination",
    "ip_transfer_before_payment",
    "uncapped_liability",
    "unfavorable_payment_terms",
)
RISK_LEVELS = ("high", "medium", "low")


def _one_of(column: str, values: tuple[str, ...], table: str) -> sa.CheckConstraint:
    allowed = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({allowed})", name=op.f(f"ck_{table}_{column}"))


def _utc(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    _create_users()
    _create_contracts()
    _create_risk_findings()
    _create_email_drafts()


def _create_users() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        _utc("created_at"),
        sa.CheckConstraint("role = 'user'", name=op.f("ck_users_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )


def _create_contracts() -> None:
    op.create_table(
        "contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        _utc("created_at"),
        _utc("updated_at"),
        _utc("analyzed_at", nullable=True),
        _utc("analysis_started_at", nullable=True),
        sa.Column("analysis_run_id", sa.Uuid(), nullable=True),
        _one_of("file_type", FILE_TYPES, "contracts"),
        _one_of("status", STATUSES, "contracts"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_contracts_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contracts")),
    )
    op.create_index("ix_contracts_user_id_created_at", "contracts", ["user_id", "created_at"])


def _create_risk_findings() -> None:
    op.create_table(
        "risk_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("quoted_text", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        _one_of("category", CATEGORIES, "risk_findings"),
        _one_of("risk_level", RISK_LEVELS, "risk_findings"),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            name=op.f("fk_risk_findings_contract_id_contracts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_findings")),
    )
    op.create_index(op.f("ix_risk_findings_contract_id"), "risk_findings", ["contract_id"])


def _create_email_drafts() -> None:
    op.create_table(
        "email_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        _utc("created_at"),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            name=op.f("fk_email_drafts_contract_id_contracts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_drafts")),
        sa.UniqueConstraint("contract_id", name=op.f("uq_email_drafts_contract_id")),
    )


def downgrade() -> None:
    op.drop_table("email_drafts")
    op.drop_index(op.f("ix_risk_findings_contract_id"), table_name="risk_findings")
    op.drop_table("risk_findings")
    op.drop_index("ix_contracts_user_id_created_at", table_name="contracts")
    op.drop_table("contracts")
    op.drop_table("users")
