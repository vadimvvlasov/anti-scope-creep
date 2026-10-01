"""Contract use cases: status flow, the stale-analysis rule, and response mapping."""

import math
from datetime import timedelta
from uuid import UUID, uuid4

from app.context import AppContext
from app.errors import AppError, ErrorCode
from app.extraction import ContractInput
from app.models import (
    ContractDetail,
    ContractPage,
    ContractRecord,
    ContractStatus,
    ContractSummary,
    EmailDraft,
    EmailDraftRecord,
    Finding,
    FindingRecord,
    RiskLevel,
    RiskSummary,
)
from app.runner import AnalysisRunner
from app.store import ContractBusyError

_RISK_ORDER = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}


class ContractService:
    def __init__(self, context: AppContext, runner: AnalysisRunner):
        self._store = context.store
        self._clock = context.clock
        self._stale_after = timedelta(seconds=context.settings.analysis_stale_after_seconds)
        self._runner = runner

    def create(self, user_id: UUID, data: ContractInput) -> ContractDetail:
        now = self._clock()
        contract = ContractRecord(
            id=uuid4(),
            user_id=user_id,
            filename=data.filename,
            title=data.title,
            file_type=data.file_type,
            file_size=data.file_size,
            source_text=data.source_text,
            status=ContractStatus.UPLOADED,
            created_at=now,
            updated_at=now,
        )
        self._store.add_contract(contract)
        return self._start_analysis(user_id, contract.id)

    def list_page(self, user_id: UUID, page: int, page_size: int) -> ContractPage:
        self._fail_stale(user_id)
        records, total = self._store.list_contracts(user_id, (page - 1) * page_size, page_size)
        return ContractPage(
            items=[self._summary(record) for record in records],
            total_count=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size),
        )

    def get(self, user_id: UUID, contract_id: UUID) -> ContractDetail:
        self._fail_stale(user_id)
        return self._detail(self._require(self._store.get_contract(user_id, contract_id)))

    def rename(self, user_id: UUID, contract_id: UUID, title: str) -> ContractDetail:
        self._fail_stale(user_id)
        record = self._store.rename_contract(user_id, contract_id, title, self._clock())
        return self._detail(self._require(record))

    def retry(self, user_id: UUID, contract_id: UUID) -> ContractDetail:
        self._fail_stale(user_id)
        return self._start_analysis(user_id, contract_id)

    def delete(self, user_id: UUID, contract_id: UUID) -> None:
        self._fail_stale(user_id)
        try:
            deleted = self._store.delete_contract(user_id, contract_id)
        except ContractBusyError:
            raise AppError(ErrorCode.CONTRACT_ANALYSIS_IN_PROGRESS) from None
        if not deleted:
            raise AppError(ErrorCode.CONTRACT_NOT_FOUND)

    def _start_analysis(self, user_id: UUID, contract_id: UUID) -> ContractDetail:
        run_id = uuid4()
        try:
            record = self._store.start_analysis(user_id, contract_id, run_id, self._clock())
        except ContractBusyError:
            raise AppError(ErrorCode.ANALYSIS_IN_PROGRESS) from None
        record = self._require(record)
        self._runner.schedule(record.id, run_id)
        return self._detail(record)

    def _fail_stale(self, user_id: UUID) -> None:
        now = self._clock()
        self._store.fail_stale_analyses(user_id, now - self._stale_after, now)

    @staticmethod
    def _require(record: ContractRecord | None) -> ContractRecord:
        if record is None:
            raise AppError(ErrorCode.CONTRACT_NOT_FOUND)
        return record

    def _summary(self, record: ContractRecord) -> ContractSummary:
        summary = risk_summary(record, self._store.get_findings(record.id))
        return ContractSummary(
            **_summary_fields(record),
            overall_risk_level=summary.overall_risk_level if summary else None,
        )

    def _detail(self, record: ContractRecord) -> ContractDetail:
        findings = self._store.get_findings(record.id)
        summary = risk_summary(record, findings)
        return ContractDetail(
            **_summary_fields(record),
            overall_risk_level=summary.overall_risk_level if summary else None,
            risk_summary=summary,
            findings=[_finding(f) for f in sort_findings(findings)] if summary else [],
            email_draft=_email(self._store.get_email_draft(record.id)) if summary else None,
        )


def risk_summary(record: ContractRecord, findings: list[FindingRecord]) -> RiskSummary | None:
    """Derived from the last successful analysis; None before the first one."""
    if record.analyzed_at is None:
        return None
    counts = {level: sum(f.risk_level == level for f in findings) for level in RiskLevel}
    overall = next((level for level in _RISK_ORDER if counts[level]), RiskLevel.LOW)
    return RiskSummary(
        overall_risk_level=overall,
        high_count=counts[RiskLevel.HIGH],
        medium_count=counts[RiskLevel.MEDIUM],
        low_count=counts[RiskLevel.LOW],
    )


def sort_findings(findings: list[FindingRecord]) -> list[FindingRecord]:
    return sorted(findings, key=lambda f: _RISK_ORDER[f.risk_level])


def _summary_fields(record: ContractRecord) -> dict:
    return {
        "id": record.id,
        "title": record.title,
        "filename": record.filename,
        "file_type": record.file_type,
        "file_size": record.file_size,
        "status": record.status,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "analyzed_at": record.analyzed_at,
    }


def _finding(record: FindingRecord) -> Finding:
    return Finding(
        id=record.id,
        category=record.category,
        risk_level=record.risk_level,
        quoted_text=record.quoted_text,
        explanation=record.explanation,
    )


def _email(record: EmailDraftRecord | None) -> EmailDraft | None:
    if record is None:
        return None
    return EmailDraft(id=record.id, subject=record.subject, body=record.body, created_at=record.created_at)
