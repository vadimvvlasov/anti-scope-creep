"""Alembic environment: migrates MIGRATIONS_DATABASE_URL, or DATABASE_URL if it is unset.

Run from backend/: `DATABASE_URL=... uv run alembic upgrade head`. On Neon, set
MIGRATIONS_DATABASE_URL to the direct endpoint: the pooled one cannot run migrations.
Tests pass an open connection in `config.attributes["connection"]` instead.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

from app.config import migrations_database_url
from app.db import build_engine, metadata

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout (`alembic upgrade head --sql`) without connecting."""
    context.configure(url=migrations_database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = build_engine(migrations_database_url())
    with engine.connect() as connection:
        _run(connection)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
