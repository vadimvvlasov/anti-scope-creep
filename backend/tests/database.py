"""Test databases: SQLite in memory by default, PostgreSQL when TEST_DATABASE_URL is set.

Example: TEST_DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/asc_test
The PostgreSQL database is wiped by the tests that use it; never point it at real data.
"""

import os

import pytest
from sqlalchemy.engine import Engine

from app.db import build_engine, metadata
from app.store import SqlStore

SQLITE_MEMORY_URL = "sqlite://"
POSTGRES_URL = os.environ.get("TEST_DATABASE_URL", "")

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
