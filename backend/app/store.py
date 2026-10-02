"""Persistence: the store interface and its SQL implementation.

Every contract read/write takes the owner's `user_id`, so ownership is enforced at the
storage boundary. Status changes that race with background tasks are conditional
updates (`UPDATE ... WHERE status = 'analyzing' AND analysis_run_id = :run`) or run on
a row locked with `SELECT ... FOR UPDATE`, each in one transaction.
"""

from collections.abc import Sequence
from dataclasses import asdict, replace
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import Connection, Row, delete, func, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.db import contracts, email_drafts, risk_findings, users
from app.models import (
    ContractRecord,
    ContractStatus,
    EmailDraftRecord,
    FindingRecord,
    UserRecord,
)


class DuplicateEmailError(Exception):
    """A user with this email already exists."""


class ContractBusyError(Exception):
    """The contract is `analyzing`, so the requested change is not allowed."""


class Store(Protocol):
    def ping(self) -> bool: ...

    def add_user(self, user: UserRecord) -> None: ...

    def get_user(self, user_id: UUID) -> UserRecord | None: ...

    def get_user_by_email(self, email: str) -> UserRecord | None: ...

    def add_contract(self, contract: ContractRecord) -> None: ...

    def get_contract(self, user_id: UUID, contract_id: UUID) -> ContractRecord | None: ...

    def get_contract_for_analysis(self, contract_id: UUID, run_id: UUID) -> ContractRecord | None: ...

    def list_contracts(
        self, user_id: UUID, offset: int, limit: int
    ) -> tuple[list[ContractRecord], int]: ...

    def rename_contract(
        self, user_id: UUID, contract_id: UUID, title: str, now: datetime
    ) -> ContractRecord | None: ...

    def start_analysis(
        self, user_id: UUID, contract_id: UUID, run_id: UUID, now: datetime
    ) -> ContractRecord | None: ...

    def delete_contract(self, user_id: UUID, contract_id: UUID) -> bool: ...

    def fail_stale_analyses(
        self, user_id: UUID, started_before: datetime, now: datetime
    ) -> int: ...

    def complete_analysis(
        self,
        contract_id: UUID,
        run_id: UUID,
        findings: Sequence[FindingRecord],
        email_draft: EmailDraftRecord | None,
        now: datetime,
    ) -> bool: ...

    def fail_analysis(self, contract_id: UUID, run_id: UUID, now: datetime) -> bool: ...

    def get_findings(self, contract_id: UUID) -> list[FindingRecord]: ...

    def get_email_draft(self, contract_id: UUID) -> EmailDraftRecord | None: ...


class SqlStore:
    """Store backed by SQLAlchemy Core. Each method is one transaction."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def ping(self) -> bool:
        with self._engine.connect() as conn:
            conn.execute(select(1))
        return True

    # -- users ---------------------------------------------------------------

    def add_user(self, user: UserRecord) -> None:
        try:
            with self._engine.begin() as conn:
                conn.execute(insert(users).values(**asdict(user)))
        except IntegrityError as exc:
            raise DuplicateEmailError(user.email) from exc

    def get_user(self, user_id: UUID) -> UserRecord | None:
        return self._one_user(users.c.id == user_id)

    def get_user_by_email(self, email: str) -> UserRecord | None:
        return self._one_user(users.c.email == email)

    def _one_user(self, condition: Any) -> UserRecord | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(users).where(condition)).first()
        return UserRecord(**row._mapping) if row else None

    # -- contracts -----------------------------------------------------------

    def add_contract(self, contract: ContractRecord) -> None:
        with self._engine.begin() as conn:
            conn.execute(insert(contracts).values(**asdict(contract)))

    def get_contract(self, user_id: UUID, contract_id: UUID) -> ContractRecord | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(contracts).where(*_owned(user_id, contract_id))).first()
        return _contract(row) if row else None

    def get_contract_for_analysis(self, contract_id: UUID, run_id: UUID) -> ContractRecord | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(contracts).where(*_current_run(contract_id, run_id))).first()
        return _contract(row) if row else None

    def list_contracts(
        self, user_id: UUID, offset: int, limit: int
    ) -> tuple[list[ContractRecord], int]:
        owned = contracts.c.user_id == user_id
        page = (
            select(contracts)
            .where(owned)
            .order_by(contracts.c.created_at.desc(), contracts.c.id)
            .offset(offset)
            .limit(limit)
        )
        with self._engine.connect() as conn:
            total = conn.execute(select(func.count()).select_from(contracts).where(owned)).scalar_one()
            rows = conn.execute(page).all()
        return [_contract(row) for row in rows], total

    def rename_contract(
        self, user_id: UUID, contract_id: UUID, title: str, now: datetime
    ) -> ContractRecord | None:
        with self._engine.begin() as conn:
            row = _lock_owned(conn, user_id, contract_id)
            if row is None:
                return None
            return _update_contract(conn, row, title=title, updated_at=now)

    def start_analysis(
        self, user_id: UUID, contract_id: UUID, run_id: UUID, now: datetime
    ) -> ContractRecord | None:
        with self._engine.begin() as conn:
            row = _lock_owned(conn, user_id, contract_id)
            if row is None:
                return None
            if row.status == ContractStatus.ANALYZING:
                raise ContractBusyError(contract_id)
            return _update_contract(
                conn,
                row,
                status=ContractStatus.ANALYZING,
                analysis_started_at=now,
                analysis_run_id=run_id,
                updated_at=now,
            )

    def delete_contract(self, user_id: UUID, contract_id: UUID) -> bool:
        with self._engine.begin() as conn:
            row = _lock_owned(conn, user_id, contract_id)
            if row is None:
                return False
            if row.status == ContractStatus.ANALYZING:
                raise ContractBusyError(contract_id)
            # Findings and the email draft go with it: ON DELETE CASCADE.
            conn.execute(delete(contracts).where(contracts.c.id == contract_id))
            return True

    # -- analysis results ------------------------------------------------------

    def fail_stale_analyses(self, user_id: UUID, started_before: datetime, now: datetime) -> int:
        stale = update(contracts).where(
            contracts.c.user_id == user_id,
            contracts.c.status == ContractStatus.ANALYZING,
            contracts.c.analysis_started_at < started_before,
        )
        with self._engine.begin() as conn:
            return conn.execute(stale.values(status=ContractStatus.FAILED, updated_at=now)).rowcount

    def complete_analysis(
        self,
        contract_id: UUID,
        run_id: UUID,
        findings: Sequence[FindingRecord],
        email_draft: EmailDraftRecord | None,
        now: datetime,
    ) -> bool:
        done = {"status": ContractStatus.DONE, "analyzed_at": now, "updated_at": now}
        with self._engine.begin() as conn:
            if not _update_current_run(conn, contract_id, run_id, done):
                return False
            conn.execute(delete(risk_findings).where(risk_findings.c.contract_id == contract_id))
            conn.execute(delete(email_drafts).where(email_drafts.c.contract_id == contract_id))
            if findings:
                conn.execute(insert(risk_findings), [asdict(finding) for finding in findings])
            if email_draft is not None:
                conn.execute(insert(email_drafts).values(**asdict(email_draft)))
            return True

    def fail_analysis(self, contract_id: UUID, run_id: UUID, now: datetime) -> bool:
        failed = {"status": ContractStatus.FAILED, "updated_at": now}
        with self._engine.begin() as conn:
            return _update_current_run(conn, contract_id, run_id, failed)

    def get_findings(self, contract_id: UUID) -> list[FindingRecord]:
        query = (
            select(risk_findings)
            .where(risk_findings.c.contract_id == contract_id)
            .order_by(risk_findings.c.category, risk_findings.c.id)
        )
        with self._engine.connect() as conn:
            return [FindingRecord(**row._mapping) for row in conn.execute(query)]

    def get_email_draft(self, contract_id: UUID) -> EmailDraftRecord | None:
        query = select(email_drafts).where(email_drafts.c.contract_id == contract_id)
        with self._engine.connect() as conn:
            row = conn.execute(query).first()
        return EmailDraftRecord(**row._mapping) if row else None


def _owned(user_id: UUID, contract_id: UUID) -> tuple[Any, ...]:
    return contracts.c.id == contract_id, contracts.c.user_id == user_id


def _current_run(contract_id: UUID, run_id: UUID) -> tuple[Any, ...]:
    """A task may commit only while the contract is still `analyzing` under its run."""
    return (
        contracts.c.id == contract_id,
        contracts.c.status == ContractStatus.ANALYZING,
        contracts.c.analysis_run_id == run_id,
    )


def _lock_owned(conn: Connection, user_id: UUID, contract_id: UUID) -> Row | None:
    query = select(contracts).where(*_owned(user_id, contract_id)).with_for_update()
    return conn.execute(query).first()


def _update_contract(conn: Connection, row: Row, **values: Any) -> ContractRecord:
    conn.execute(update(contracts).where(contracts.c.id == row.id).values(**values))
    return replace(_contract(row), **values)


def _update_current_run(
    conn: Connection, contract_id: UUID, run_id: UUID, values: dict[str, Any]
) -> bool:
    result = conn.execute(update(contracts).where(*_current_run(contract_id, run_id)).values(**values))
    return result.rowcount == 1


def _contract(row: Row) -> ContractRecord:
    return ContractRecord(**row._mapping)
