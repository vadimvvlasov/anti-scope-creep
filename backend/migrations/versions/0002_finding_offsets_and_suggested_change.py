"""Findings get suggested_change and the start_char/end_char offsets of their quote.

Existing rows are backfilled: suggested_change from a fixed text per category, offsets
from the first exact occurrence of quoted_text in the contract's source_text (Python
string indices are the code points docs/spec.md "Finding offsets" asks for).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OFFSETS_CHECK = (
    "(start_char IS NULL AND end_char IS NULL) "
    "OR (start_char IS NOT NULL AND end_char IS NOT NULL AND start_char >= 0 AND end_char > start_char)"
)

# A frozen copy of the seed texts: a migration must not change when app code does.
SUGGESTED_CHANGES = {
    "scope_creep": "The Contractor shall perform the services listed in Exhibit A. Any additional work requires a written change order agreed by both parties, including the fee and timeline.",
    "unlimited_revisions": "The fee includes two rounds of revisions per deliverable. Further revisions will be billed at the Contractor's hourly rate.",
    "one_sided_termination": "Either party may terminate this Agreement on fourteen days' written notice. The Client shall pay for all work completed up to the termination date.",
    "ip_transfer_before_payment": "Ownership of the deliverables transfers to the Client once all invoices under this Agreement have been paid in full.",
    "uncapped_liability": "The Contractor's total liability arising out of or in connection with this Agreement shall not exceed the total fees paid under this Agreement.",
    "unfavorable_payment_terms": "Invoices are payable within 30 days of the invoice date.",
}


def upgrade() -> None:
    with op.batch_alter_table("risk_findings") as batch:
        batch.add_column(sa.Column("suggested_change", sa.Text(), nullable=True))
        batch.add_column(sa.Column("start_char", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("end_char", sa.Integer(), nullable=True))
    _backfill()
    with op.batch_alter_table("risk_findings") as batch:
        batch.alter_column("suggested_change", existing_type=sa.Text(), nullable=False)
        batch.create_check_constraint(op.f("ck_risk_findings_offsets"), OFFSETS_CHECK)


def _backfill() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT f.id, f.category, f.quoted_text, c.source_text "
            "FROM risk_findings f JOIN contracts c ON c.id = f.contract_id"
        )
    ).all()
    update = sa.text(
        "UPDATE risk_findings SET suggested_change = :change, start_char = :start, end_char = :end "
        "WHERE id = :id"
    )
    for row in rows:
        start = row.source_text.find(row.quoted_text)
        located = start >= 0 and bool(row.quoted_text)
        conn.execute(
            update,
            {
                "id": row.id,
                "change": SUGGESTED_CHANGES[row.category],
                "start": start if located else None,
                "end": start + len(row.quoted_text) if located else None,
            },
        )


def downgrade() -> None:
    with op.batch_alter_table("risk_findings") as batch:
        batch.drop_constraint(op.f("ck_risk_findings_offsets"), type_="check")
        batch.drop_column("end_char")
        batch.drop_column("start_char")
        batch.drop_column("suggested_change")
