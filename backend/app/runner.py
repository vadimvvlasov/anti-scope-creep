"""Analysis execution: the runner interface and the background analysis job.

The runner decides *where* a job runs (FastAPI BackgroundTasks in the MVP; a task
queue later). The job decides *what* happens and commits only under its run ID.
"""

import logging
import time
from collections.abc import Iterable
from typing import Protocol
from uuid import UUID, uuid4

from fastapi import BackgroundTasks
from starlette.concurrency import run_in_threadpool

from app.analyzer import AnalysisResult, FindingDraft
from app.context import AppContext
from app.models import EmailDraftRecord, FindingRecord
from app.quotes import locate_quote
from app import telemetry
from app.telemetry import contract_id_var

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
    token = contract_id_var.set(str(contract_id))  # every log line of this run carries the contract id
    started = time.monotonic()
    try:
        with telemetry.span("analysis.run", **{"contract.id": str(contract_id)}) as current:
            outcome = _run_analysis(context, contract_id, run_id)
            if outcome == "failed":
                telemetry.fail_span(current, "analysis_failed")
        telemetry.record_analysis(outcome, time.monotonic() - started)
    finally:
        contract_id_var.reset(token)


async def resume_interrupted_analyses(context: AppContext) -> None:
    """At the start of the backend, take up again what a shutdown interrupted, one analysis at a time.

    The model has one slot, so they run in order, the oldest first. While one runs, the others'
    stale clocks are restarted, so the stale rule does not fail a contract that is only waiting.
    A contract resumed `analysis_max_resumes` times already goes to `failed` instead (a contract that
    crashes the backend must not loop). Never raises.
    """
    store, now = context.store, context.clock
    max_resumes = context.settings.analysis_max_resumes
    if max_resumes <= 0:
        return
    try:
        found = await run_in_threadpool(store.restart_interrupted_analyses, max_resumes, now())
        if found.failed:
            telemetry.record_analysis("failed", count=found.failed)
        if not found.runs:
            return
        logger.info("Resuming %d interrupted analyses, %d given up", len(found.runs), found.failed)
        telemetry.record_analysis("resumed", count=len(found.runs))
        waiting = [run_id for _, run_id in found.runs]
        for contract_id, run_id in found.runs:
            await run_in_threadpool(store.touch_analyses, waiting, now())
            await run_in_threadpool(run_analysis, context, contract_id, run_id)
            waiting.remove(run_id)
    except Exception:
        logger.exception("Resuming interrupted analyses failed", extra={"code": "resume_failed"})


def _run_analysis(context: AppContext, contract_id: UUID, run_id: UUID) -> str:
    """Runs one analysis and returns its outcome: done, failed or superseded (a newer run replaced it)."""
    store = context.store
    contract = store.get_contract_for_analysis(contract_id, run_id)
    if contract is None:
        logger.info("Analysis run %s for contract %s is no longer current", run_id, contract_id)
        return "superseded"
    try:
        raw = context.analyzer.analyze(contract.source_text)
        # Re-validate: an analyzer may build its result without validation.
        result = AnalysisResult.model_validate(raw.model_dump())
    except Exception:
        logger.exception("Analysis failed for contract %s", contract_id, extra={"code": "analysis_failed"})
        store.fail_analysis(contract_id, run_id, context.clock())
        return "failed"
    now = context.clock()
    findings = place_findings(contract_id, contract.source_text, result.findings)
    email = (
        EmailDraftRecord(id=uuid4(), contract_id=contract_id, created_at=now, **result.email_draft.model_dump())
        if result.email_draft
        else None
    )
    if not store.complete_analysis(contract_id, run_id, findings, email, now):
        logger.info("Discarded result of superseded run %s for contract %s", run_id, contract_id)
        return "superseded"
    return "done"


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
