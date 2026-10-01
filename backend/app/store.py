"""Persistence: the store interface and its in-memory implementation.

Every contract read/write takes the owner's `user_id`, so ownership is enforced at the
storage boundary. Status changes that race with background tasks are conditional
updates (compare the current status / run ID), mirroring what a SQL `UPDATE ... WHERE`
would do once the store moves to PostgreSQL.
"""

import threading
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from typing import Protocol
from uuid import UUID

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


class InMemoryStore:
    """Thread-safe in-memory store. Returned records are copies."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._users: dict[UUID, UserRecord] = {}
        self._contracts: dict[UUID, ContractRecord] = {}
        self._findings: dict[UUID, tuple[FindingRecord, ...]] = {}
        self._emails: dict[UUID, EmailDraftRecord] = {}

    def ping(self) -> bool:
        return True

    # -- users ---------------------------------------------------------------

    def add_user(self, user: UserRecord) -> None:
        with self._lock:
            if any(existing.email == user.email for existing in self._users.values()):
                raise DuplicateEmailError(user.email)
            self._users[user.id] = replace(user)

    def get_user(self, user_id: UUID) -> UserRecord | None:
        with self._lock:
            user = self._users.get(user_id)
            return replace(user) if user else None

    def get_user_by_email(self, email: str) -> UserRecord | None:
        with self._lock:
            user = next((u for u in self._users.values() if u.email == email), None)
            return replace(user) if user else None

    # -- contracts -----------------------------------------------------------

    def add_contract(self, contract: ContractRecord) -> None:
        with self._lock:
            self._contracts[contract.id] = replace(contract)

    def _owned(self, user_id: UUID, contract_id: UUID) -> ContractRecord | None:
        contract = self._contracts.get(contract_id)
        return contract if contract and contract.user_id == user_id else None

    def get_contract(self, user_id: UUID, contract_id: UUID) -> ContractRecord | None:
        with self._lock:
            contract = self._owned(user_id, contract_id)
            return replace(contract) if contract else None

    def get_contract_for_analysis(self, contract_id: UUID, run_id: UUID) -> ContractRecord | None:
        with self._lock:
            contract = self._contracts.get(contract_id)
            if contract is None or not _owns_run(contract, run_id):
                return None
            return replace(contract)

    def list_contracts(
        self, user_id: UUID, offset: int, limit: int
    ) -> tuple[list[ContractRecord], int]:
        with self._lock:
            owned = [c for c in self._contracts.values() if c.user_id == user_id]
        owned.sort(key=lambda c: c.created_at, reverse=True)
        return [replace(c) for c in owned[offset : offset + limit]], len(owned)

    def rename_contract(
        self, user_id: UUID, contract_id: UUID, title: str, now: datetime
    ) -> ContractRecord | None:
        with self._lock:
            contract = self._owned(user_id, contract_id)
            if contract is None:
                return None
            contract.title = title
            contract.updated_at = now
            return replace(contract)

    def start_analysis(
        self, user_id: UUID, contract_id: UUID, run_id: UUID, now: datetime
    ) -> ContractRecord | None:
        with self._lock:
            contract = self._owned(user_id, contract_id)
            if contract is None:
                return None
            if contract.status == ContractStatus.ANALYZING:
                raise ContractBusyError(contract_id)
            contract.status = ContractStatus.ANALYZING
            contract.analysis_started_at = now
            contract.analysis_run_id = run_id
            contract.updated_at = now
            return replace(contract)

    def delete_contract(self, user_id: UUID, contract_id: UUID) -> bool:
        with self._lock:
            contract = self._owned(user_id, contract_id)
            if contract is None:
                return False
            if contract.status == ContractStatus.ANALYZING:
                raise ContractBusyError(contract_id)
            del self._contracts[contract_id]
            self._findings.pop(contract_id, None)
            self._emails.pop(contract_id, None)
            return True

    # -- analysis results ------------------------------------------------------

    def fail_stale_analyses(self, user_id: UUID, started_before: datetime, now: datetime) -> int:
        with self._lock:
            stale = [
                c
                for c in self._contracts.values()
                if c.user_id == user_id
                and c.status == ContractStatus.ANALYZING
                and c.analysis_started_at is not None
                and c.analysis_started_at < started_before
            ]
            for contract in stale:
                contract.status = ContractStatus.FAILED
                contract.updated_at = now
            return len(stale)

    def complete_analysis(
        self,
        contract_id: UUID,
        run_id: UUID,
        findings: Sequence[FindingRecord],
        email_draft: EmailDraftRecord | None,
        now: datetime,
    ) -> bool:
        with self._lock:
            contract = self._contracts.get(contract_id)
            if contract is None or not _owns_run(contract, run_id):
                return False
            self._findings[contract_id] = tuple(findings)
            if email_draft is None:
                self._emails.pop(contract_id, None)
            else:
                self._emails[contract_id] = email_draft
            contract.status = ContractStatus.DONE
            contract.analyzed_at = now
            contract.updated_at = now
            return True

    def fail_analysis(self, contract_id: UUID, run_id: UUID, now: datetime) -> bool:
        with self._lock:
            contract = self._contracts.get(contract_id)
            if contract is None or not _owns_run(contract, run_id):
                return False
            contract.status = ContractStatus.FAILED
            contract.updated_at = now
            return True

    def get_findings(self, contract_id: UUID) -> list[FindingRecord]:
        with self._lock:
            return list(self._findings.get(contract_id, ()))

    def get_email_draft(self, contract_id: UUID) -> EmailDraftRecord | None:
        with self._lock:
            return self._emails.get(contract_id)


def _owns_run(contract: ContractRecord, run_id: UUID) -> bool:
    """A task may commit only while the contract is still `analyzing` under its run."""
    return contract.status == ContractStatus.ANALYZING and contract.analysis_run_id == run_id
