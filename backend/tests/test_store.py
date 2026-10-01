from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models import (
    ContractRecord,
    ContractStatus,
    EmailDraftRecord,
    FileType,
    FindingRecord,
    RiskCategory,
    RiskLevel,
    UserRecord,
)
from app.store import ContractBusyError, DuplicateEmailError, InMemoryStore

NOW = datetime(2026, 9, 29, 10, 0, tzinfo=UTC)


def make_user(email="a@example.com"):
    return UserRecord(id=uuid4(), email=email, password_hash="hash", created_at=NOW)


def make_contract(user_id, created_at=NOW, status=ContractStatus.DONE):
    return ContractRecord(
        id=uuid4(),
        user_id=user_id,
        filename="",
        title="Contract",
        file_type=FileType.TXT,
        file_size=None,
        source_text="text",
        status=status,
        created_at=created_at,
        updated_at=created_at,
    )


def make_finding(contract_id, level=RiskLevel.HIGH):
    return FindingRecord(
        id=uuid4(),
        contract_id=contract_id,
        category=RiskCategory.UNCAPPED_LIABILITY,
        risk_level=level,
        quoted_text="quote",
        explanation="why",
    )


def make_email(contract_id):
    return EmailDraftRecord(id=uuid4(), contract_id=contract_id, subject="s", body="b", created_at=NOW)


@pytest.fixture
def store():
    return InMemoryStore()


@pytest.fixture
def user(store):
    user = make_user()
    store.add_user(user)
    return user


def test_duplicate_email_is_rejected(store, user):
    with pytest.raises(DuplicateEmailError):
        store.add_user(make_user(email=user.email))


def test_contract_of_another_user_is_invisible(store, user):
    other = make_user("b@example.com")
    store.add_user(other)
    contract = make_contract(other.id)
    store.add_contract(contract)

    assert store.get_contract(user.id, contract.id) is None
    assert store.rename_contract(user.id, contract.id, "x", NOW) is None
    assert store.start_analysis(user.id, contract.id, uuid4(), NOW) is None
    assert store.delete_contract(user.id, contract.id) is False
    assert store.list_contracts(user.id, 0, 10) == ([], 0)


def test_returned_records_are_copies(store, user):
    contract = make_contract(user.id)
    store.add_contract(contract)
    store.get_contract(user.id, contract.id).title = "mutated"
    assert store.get_contract(user.id, contract.id).title == "Contract"


def test_list_is_newest_first_and_paginated(store, user):
    contracts = [make_contract(user.id, NOW - timedelta(days=d)) for d in range(5)]
    for contract in reversed(contracts):
        store.add_contract(contract)

    items, total = store.list_contracts(user.id, offset=2, limit=2)

    assert total == 5
    assert [c.id for c in items] == [contracts[2].id, contracts[3].id]


def test_start_analysis_sets_run_and_rejects_when_analyzing(store, user):
    contract = make_contract(user.id)
    store.add_contract(contract)
    run_id = uuid4()

    started = store.start_analysis(user.id, contract.id, run_id, NOW)

    assert started.status == ContractStatus.ANALYZING
    assert started.analysis_run_id == run_id
    assert started.analysis_started_at == NOW
    with pytest.raises(ContractBusyError):
        store.start_analysis(user.id, contract.id, uuid4(), NOW)


def test_delete_cascades_and_rejects_when_analyzing(store, user):
    contract = make_contract(user.id)
    store.add_contract(contract)
    run_id = uuid4()
    store.start_analysis(user.id, contract.id, run_id, NOW)

    with pytest.raises(ContractBusyError):
        store.delete_contract(user.id, contract.id)

    store.complete_analysis(contract.id, run_id, [make_finding(contract.id)], make_email(contract.id), NOW)
    assert store.delete_contract(user.id, contract.id) is True
    assert store.get_findings(contract.id) == []
    assert store.get_email_draft(contract.id) is None


def test_complete_analysis_replaces_results_atomically(store, user):
    contract = make_contract(user.id)
    store.add_contract(contract)
    first_run = uuid4()
    store.start_analysis(user.id, contract.id, first_run, NOW)
    store.complete_analysis(contract.id, first_run, [make_finding(contract.id)], make_email(contract.id), NOW)

    second_run = uuid4()
    later = NOW + timedelta(minutes=1)
    store.start_analysis(user.id, contract.id, second_run, later)
    low = make_finding(contract.id, RiskLevel.LOW)
    assert store.complete_analysis(contract.id, second_run, [low], None, later) is True

    saved = store.get_contract(user.id, contract.id)
    assert saved.status == ContractStatus.DONE
    assert saved.analyzed_at == later
    assert store.get_findings(contract.id) == [low]
    assert store.get_email_draft(contract.id) is None


def test_task_with_superseded_run_commits_nothing(store, user):
    contract = make_contract(user.id)
    store.add_contract(contract)
    old_run = uuid4()
    store.start_analysis(user.id, contract.id, old_run, NOW)
    store.fail_analysis(contract.id, old_run, NOW)
    new_run = uuid4()
    store.start_analysis(user.id, contract.id, new_run, NOW)

    assert store.complete_analysis(contract.id, old_run, [make_finding(contract.id)], None, NOW) is False
    assert store.fail_analysis(contract.id, old_run, NOW) is False
    assert store.get_contract(user.id, contract.id).status == ContractStatus.ANALYZING
    assert store.get_findings(contract.id) == []


def test_fail_analysis_keeps_previous_results(store, user):
    contract = make_contract(user.id)
    store.add_contract(contract)
    first_run = uuid4()
    store.start_analysis(user.id, contract.id, first_run, NOW)
    finding = make_finding(contract.id)
    store.complete_analysis(contract.id, first_run, [finding], make_email(contract.id), NOW)

    retry_run = uuid4()
    store.start_analysis(user.id, contract.id, retry_run, NOW + timedelta(minutes=1))
    assert store.fail_analysis(contract.id, retry_run, NOW + timedelta(minutes=2)) is True

    saved = store.get_contract(user.id, contract.id)
    assert saved.status == ContractStatus.FAILED
    assert saved.analyzed_at == NOW
    assert store.get_findings(contract.id) == [finding]
    assert store.get_email_draft(contract.id) is not None


def test_fail_stale_analyses_only_touches_old_analyzing_contracts(store, user):
    old = make_contract(user.id)
    fresh = make_contract(user.id)
    for contract in (old, fresh):
        store.add_contract(contract)
    store.start_analysis(user.id, old.id, uuid4(), NOW - timedelta(minutes=11))
    store.start_analysis(user.id, fresh.id, uuid4(), NOW - timedelta(minutes=1))

    assert store.fail_stale_analyses(user.id, NOW - timedelta(minutes=10), NOW) == 1
    assert store.get_contract(user.id, old.id).status == ContractStatus.FAILED
    assert store.get_contract(user.id, fresh.id).status == ContractStatus.ANALYZING
