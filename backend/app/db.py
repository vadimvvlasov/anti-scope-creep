"""Database schema and engine: the tables from docs/spec.md "Data model".

The schema is created by Alembic migrations (`migrations/`); tests build it from
`metadata` directly. Column types are database-agnostic: PostgreSQL is the target,
SQLite in memory runs the test suite.
"""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Dialect,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    TypeDecorator,
    Uuid,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import StaticPool

from app.models import ContractStatus, FileType, RiskCategory, RiskLevel

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class UtcDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC datetimes in and out, on every backend.

    PostgreSQL stores `timestamptz`; SQLite has no offset support, so values are
    stored as naive UTC there and marked UTC again when read.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not stored; pass a UTC-aware datetime.")
        value = value.astimezone(UTC)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _enum(enum_class: type[StrEnum], name: str) -> Enum:
    """A VARCHAR + CHECK constraint holding the enum values (no native enum types)."""
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )


users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("role", String(16), nullable=False),
    Column("created_at", UtcDateTime, nullable=False),
    CheckConstraint("role = 'user'", name="role"),
)

contracts = Table(
    "contracts",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("filename", String(255), nullable=False),
    Column("title", String(250), nullable=False),
    Column("file_type", _enum(FileType, "file_type"), nullable=False),
    Column("file_size", Integer, nullable=True),
    Column("source_text", Text, nullable=False),
    Column("status", _enum(ContractStatus, "status"), nullable=False),
    Column("created_at", UtcDateTime, nullable=False),
    Column("updated_at", UtcDateTime, nullable=False),
    Column("analyzed_at", UtcDateTime, nullable=True),
    Column("analysis_started_at", UtcDateTime, nullable=True),
    Column("analysis_run_id", Uuid, nullable=True),
    Index("ix_contracts_user_id_created_at", "user_id", "created_at"),
)

risk_findings = Table(
    "risk_findings",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "contract_id", Uuid, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    ),
    Column("category", _enum(RiskCategory, "category"), nullable=False),
    Column("risk_level", _enum(RiskLevel, "risk_level"), nullable=False),
    Column("quoted_text", Text, nullable=False),
    Column("explanation", Text, nullable=False),
)

email_drafts = Table(
    "email_drafts",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "contract_id", Uuid, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, unique=True
    ),
    Column("subject", String(200), nullable=False),
    Column("body", Text, nullable=False),
    Column("created_at", UtcDateTime, nullable=False),
)


def build_engine(database_url: str) -> Engine:
    """Create the engine for DATABASE_URL (e.g. `postgresql+psycopg://...`)."""
    if database_url in ("sqlite://", "sqlite:///:memory:"):
        # One shared connection, so every session sees the same in-memory database.
        engine = create_engine(
            database_url, poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    elif make_url(database_url).drivername == "postgresql+psycopg":
        # Neon's pooled endpoint is PgBouncer in transaction mode, which cannot keep
        # server-side prepared statements; idle computes are suspended, so ping first.
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=5,
            connect_args={"prepare_threshold": None},
        )
    else:
        engine = create_engine(database_url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        # SQLite ignores foreign keys (and so ON DELETE CASCADE) unless asked per connection.
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
