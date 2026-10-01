"""Analysis execution: the runner interface and the background analysis job.

The runner decides *where* a job runs (FastAPI BackgroundTasks in the MVP; a task
queue later). The job decides *what* happens and commits only under its run ID.
"""

import logging
from typing import Protocol
from uuid import UUID, uuid4

from fastapi import BackgroundTasks

from app.analyzer import AnalysisResult
from app.context import AppContext
from app.models import EmailDraftRecord, FindingRecord

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
    findings = [
        FindingRecord(id=uuid4(), contract_id=contract_id, **finding.model_dump())
        for finding in result.findings
    ]
    email = (
        EmailDraftRecord(id=uuid4(), contract_id=contract_id, created_at=now, **result.email_draft.model_dump())
        if result.email_draft
        else None
    )
    if not store.complete_analysis(contract_id, run_id, findings, email, now):
        logger.info("Discarded result of superseded run %s for contract %s", run_id, contract_id)
