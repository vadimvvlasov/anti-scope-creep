"""Engine settings for Neon's pooled endpoint (docs/architecture.md, section 3)."""

import pytest

from app.db import build_engine
from tests.database import POSTGRES_URL


def test_postgres_engine_uses_a_small_pool_with_pre_ping():
    engine = build_engine("postgresql+psycopg://u:p@db.invalid:5432/asc")
    assert engine.pool.size() == 5
    assert engine.pool._pre_ping is True


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_DATABASE_URL is not set")
def test_postgres_connections_disable_server_side_prepared_statements():
    engine = build_engine(POSTGRES_URL)
    with engine.connect() as conn:
        assert conn.connection.dbapi_connection.prepare_threshold is None
    engine.dispose()
