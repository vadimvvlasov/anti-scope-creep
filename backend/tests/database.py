"""Test databases: SQLite in memory by default, PostgreSQL when TEST_DATABASE_URL is set.

Example: TEST_DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/asc_test
The PostgreSQL database is wiped by the tests that use it; never point it at real data.
"""

import os

import pytest
from sqlalchemy.engine import Engine, make_url

from app.db import build_engine, metadata
from app.store import SqlStore

SQLITE_MEMORY_URL = "sqlite://"


def _throwaway_url(url: str) -> str:
    """The tests wipe this database, so refuse one that is not named like a test database."""
    name = (make_url(url).database or "") if url else ""
    if url and "test" not in name:
        raise RuntimeError(
            f"TEST_DATABASE_URL must point at a throwaway database whose name contains 'test', "
            f"got '{name}': the tests wipe it"
        )
    return url


POSTGRES_URL = _throwaway_url(os.environ.get("TEST_DATABASE_URL", ""))

# Parametrize database-level tests over every available backend.
DATABASE_URLS = [
    pytest.param(SQLITE_MEMORY_URL, id="sqlite"),
    pytest.param(
        POSTGRES_URL,
        id="postgres",
        marks=pytest.mark.skipif(not POSTGRES_URL, reason="TEST_DATABASE_URL is not set"),
    ),
]


def fresh_engine(url: str = SQLITE_MEMORY_URL) -> Engine:
    """An engine on an empty database with the schema from `app.db.metadata`."""
    engine = build_engine(url)
    metadata.drop_all(engine)
    metadata.create_all(engine)
    return engine


def memory_store() -> SqlStore:
    return SqlStore(fresh_engine())
