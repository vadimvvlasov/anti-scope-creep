"""Analysis execution: the runner interface and the background analysis job.

The runner decides *where* a job runs (FastAPI BackgroundTasks in the MVP; a task
queue later). The job decides *what* happens and commits only under its run ID.
"""

import logging
from collections.abc import Iterable
from typing import Protocol
from uuid import UUID, uuid4

from fastapi import BackgroundTasks

from app.analyzer import AnalysisResult, FindingDraft
from app.context import AppContext
from app.models import EmailDraftRecord, FindingRecord
from app.quotes import locate_quote

logger = logging.getLogger(__name__)


class AnalysisRunner(Protocol):
    def schedule(self, contract_id: UUID, run_id: UUID) -> None: ...


class BackgroundTasksRunner:
    """Runs the job in-process after the response is sent."""

    def __init__(self, background_tasks: BackgroundTasks, context: AppContext):
        self._background_tasks = background_tasks
        self._context = context

    def schedule(self, contract_id: UUID, run_id: UUID) -> None:
        self._background_tasks.add_task(run_analysis, self._context, contract_id, run_id)


def run_analysis(context: AppContext, contract_id: UUID, run_id: UUID) -> None:
    """Analyze one contract for one run. Never raises."""
    store = context.store
    contract = store.get_contract_for_analysis(contract_id, run_id)
    if contract is None:
        logger.info("Analysis run %s for contract %s is no longer current", run_id, contract_id)
        return
    try:
        raw = context.analyzer.analyze(contract.source_text)
        # Re-validate: an analyzer may build its result without validation.
        result = AnalysisResult.model_validate(raw.model_dump())
    except Exception:
        logger.exception("Analysis failed for contract %s", contract_id)
        store.fail_analysis(contract_id, run_id, context.clock())
        return
    now = context.clock()
    findings = place_findings(contract_id, contract.source_text, result.findings)
    email = (
        EmailDraftRecord(id=uuid4(), contract_id=contract_id, created_at=now, **result.email_draft.model_dump())
        if result.email_draft
        else None
    )
    if not store.complete_analysis(contract_id, run_id, findings, email, now):
        logger.info("Discarded result of superseded run %s for contract %s", run_id, contract_id)


def place_findings(
    contract_id: UUID, source_text: str, drafts: Iterable[FindingDraft]
) -> list[FindingRecord]:
    """Finding records for one contract, with the offsets of their quotes in its text."""
    records = []
    for draft in drafts:
        start, end = locate_quote(source_text, draft.quoted_text)
        records.append(
            FindingRecord(
                id=uuid4(), contract_id=contract_id, start_char=start, end_char=end, **draft.model_dump()
            )
        )
    return records
