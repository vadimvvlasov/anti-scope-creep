from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks

from app.analyzer import AnalysisResult, FindingDraft, StubAnalyzer
from app.config import Settings
from app.context import AppContext
from app.models import ContractRecord, ContractStatus, FileType, RiskLevel, UserRecord
from app.runner import BackgroundTasksRunner, run_analysis
from tests.database import memory_store
from tests.fakes import FailingAnalyzer, FakeClock

USER_ID = uuid4()


class InvalidResultAnalyzer:
    """Builds a result that skips validation: a medium finding without an email."""

    def analyze(self, source_text: str) -> AnalysisResult:
        finding = FindingDraft(
            category="scope_creep", risk_level=RiskLevel.MEDIUM, quoted_text="q", explanation="e"
        )
        return AnalysisResult.model_construct(findings=[finding], email_draft=None)


def make_context(analyzer=None) -> AppContext:
    return AppContext(
        settings=Settings(jwt_secret="x", seed_demo_data=False),
        store=memory_store(),
        analyzer=analyzer or StubAnalyzer(),
        clock=FakeClock(),
    )


def start(context: AppContext):
    now = datetime.now(UTC)
    contract = ContractRecord(
        id=uuid4(),
        user_id=USER_ID,
        filename="",
        title="t",
        file_type=FileType.TXT,
        file_size=None,
        source_text="text",
        status=ContractStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    context.store.add_user(UserRecord(id=USER_ID, email="u@example.com", password_hash="h", created_at=now))
    context.store.add_contract(contract)
    run_id = uuid4()
    context.store.start_analysis(USER_ID, contract.id, run_id, now)
    return contract.id, run_id


def test_successful_run_stores_findings_and_email():
    context = make_context()
    contract_id, run_id = start(context)

    run_analysis(context, contract_id, run_id)

    contract = context.store.get_contract(USER_ID, contract_id)
    assert contract.status == ContractStatus.DONE
    assert contract.analyzed_at == context.clock()
    assert len(context.store.get_findings(contract_id)) == 3
    assert context.store.get_email_draft(contract_id).subject == "Proposed changes to the agreement"


@pytest.mark.parametrize("analyzer", [FailingAnalyzer(), InvalidResultAnalyzer()])
def test_failed_or_invalid_run_marks_contract_failed_and_commits_nothing(analyzer):
    context = make_context(analyzer)
    contract_id, run_id = start(context)

    run_analysis(context, contract_id, run_id)

    contract = context.store.get_contract(USER_ID, contract_id)
    assert contract.status == ContractStatus.FAILED
    assert contract.analyzed_at is None
    assert context.store.get_findings(contract_id) == []
    assert context.store.get_email_draft(contract_id) is None


def test_superseded_run_commits_nothing():
    context = make_context()
    contract_id, old_run = start(context)
    context.store.fail_analysis(contract_id, old_run, context.clock())

    run_analysis(context, contract_id, old_run)

    assert context.store.get_contract(USER_ID, contract_id).status == ContractStatus.FAILED
    assert context.store.get_findings(contract_id) == []


def test_run_for_deleted_contract_is_a_no_op():
    context = make_context()
    run_analysis(context, uuid4(), uuid4())


def test_background_tasks_runner_schedules_the_job():
    context = make_context()
    contract_id, run_id = start(context)
    tasks = BackgroundTasks()

    BackgroundTasksRunner(tasks, context).schedule(contract_id, run_id)

    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.func is run_analysis
    assert task.args == (context, contract_id, run_id)
