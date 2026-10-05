"""Alembic migrations build exactly the schema in app.db, and the database enforces it."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, insert, text
from sqlalchemy.exc import IntegrityError

from app.db import build_engine, contracts, email_drafts, metadata, risk_findings, users
from tests.database import DATABASE_URLS, fresh_engine

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
NOW = datetime(2026, 10, 2, tzinfo=UTC)


def _migrate(connection, revision: str, upgrade: bool = True) -> None:
    config = Config(ALEMBIC_INI)
    config.attributes["connection"] = connection
    config.attributes["configure_logger"] = False
    (command.upgrade if upgrade else command.downgrade)(config, revision)


@pytest.fixture(params=DATABASE_URLS)
def empty_engine(request):
    engine = build_engine(request.param)
    metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    yield engine
    engine.dispose()


def test_upgrade_head_matches_models_and_downgrade_removes_everything(empty_engine):
    with empty_engine.begin() as conn:
        _migrate(conn, "head")
        assert compare_metadata(MigrationContext.configure(conn), metadata) == []

    with empty_engine.begin() as conn:
        _migrate(conn, "base", upgrade=False)
        assert set(inspect(conn).get_table_names()) <= {"alembic_version"}


@pytest.fixture(params=DATABASE_URLS)
def engine(request):
    engine = fresh_engine(request.param)
    yield engine
    engine.dispose()


def _user(conn) -> object:
    user_id = uuid4()
    conn.execute(
        insert(users).values(id=user_id, email=f"{user_id}@example.com", password_hash="h", role="user", created_at=NOW)
    )
    return user_id


def _contract_values(user_id, **overrides) -> dict:
    values = dict(
        id=uuid4(), user_id=user_id, filename="", title="t", file_type="txt", file_size=None,
        source_text="text", status="done", created_at=NOW, updated_at=NOW,
    )
    return values | overrides


def test_database_rejects_unknown_status(engine):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        # Raw SQL bypasses the Enum type, so only the CHECK constraint can stop it.
        user_id = _user(conn)
        conn.execute(insert(contracts).values(**_contract_values(user_id)))
        conn.execute(text("UPDATE contracts SET status = 'bogus'"))


def test_database_allows_one_email_draft_per_contract(engine):
    draft = dict(subject="s", body="b", created_at=NOW)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        contract = _contract_values(_user(conn))
        conn.execute(insert(contracts).values(**contract))
        conn.execute(insert(email_drafts).values(id=uuid4(), contract_id=contract["id"], **draft))
        conn.execute(insert(email_drafts).values(id=uuid4(), contract_id=contract["id"], **draft))


def test_deleting_a_contract_row_cascades_to_its_results(engine):
    with engine.begin() as conn:
        contract = _contract_values(_user(conn))
        conn.execute(insert(contracts).values(**contract))
        conn.execute(insert(email_drafts).values(id=uuid4(), contract_id=contract["id"], subject="s", body="b", created_at=NOW))
        conn.execute(text("DELETE FROM contracts"))
        assert conn.execute(text("SELECT count(*) FROM email_drafts")).scalar_one() == 0


def test_0002_backfills_suggested_change_and_offsets_of_existing_findings(empty_engine):
    with empty_engine.begin() as conn:
        _migrate(conn, "0001")
        contract = _contract_values(_user(conn), source_text="1. Fees\nInvoices are payable within 60 days.")
        conn.execute(insert(contracts).values(**contract))
        for quote in ("Invoices are payable within 60 days.", "Not in the text."):
            # Only the 0001 columns: the insert names them, so the newer ones are not needed.
            conn.execute(
                insert(risk_findings).values(
                    id=uuid4(), contract_id=contract["id"], category="unfavorable_payment_terms",
                    risk_level="medium", quoted_text=quote, explanation="why",
                )
            )
        _migrate(conn, "0002")
        rows = conn.execute(
            text("SELECT quoted_text, suggested_change, start_char, end_char FROM risk_findings ORDER BY quoted_text")
        ).all()

    assert [tuple(row) for row in rows] == [
        ("Invoices are payable within 60 days.", "Invoices are payable within 30 days of the invoice date.", 8, 44),
        ("Not in the text.", "Invoices are payable within 30 days of the invoice date.", None, None),
    ]


@pytest.mark.parametrize("offsets", [(5, None), (None, 5), (5, 5), (-1, 3)])
def test_database_rejects_invalid_offsets(engine, offsets):
    start, end = offsets
    with pytest.raises(IntegrityError), engine.begin() as conn:
        contract = _contract_values(_user(conn))
        conn.execute(insert(contracts).values(**contract))
        conn.execute(
            insert(risk_findings).values(
                id=uuid4(), contract_id=contract["id"], category="scope_creep", risk_level="low",
                quoted_text="q", explanation="e", suggested_change="s", start_char=start, end_char=end,
            )
        )
