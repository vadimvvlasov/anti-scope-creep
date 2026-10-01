"""Status flow over the API: retry, keep-until-success, run-ID check, stale rule."""

from dataclasses import replace

from app.runner import run_analysis
from tests.conftest import Harness, assert_error
from tests.fakes import FailingAnalyzer


def get(harness, headers, contract_id):
    return harness.client.get(f"/contracts/{contract_id}", headers=headers).json()


def retry(harness, headers, contract_id):
    return harness.client.post(f"/contracts/{contract_id}/retry", headers=headers)


def run_scheduled(harness, runner, index=-1):
    contract_id, run_id = runner.scheduled[index]
    run_analysis(harness.context, contract_id, run_id)


def test_failed_analysis_sets_failed_without_results():
    harness = Harness(analyzer=FailingAnalyzer())
    headers = harness.register()
    contract_id = harness.create_contract(headers)["id"]

    body = get(harness, headers, contract_id)

    assert body["status"] == "failed"
    assert body["analyzed_at"] is None
    assert body["risk_summary"] is None
    assert body["findings"] == []


def test_retry_keeps_previous_results_while_analyzing_and_replaces_on_success(harness, auth_headers):
    contract_id = harness.create_contract(auth_headers)["id"]
    first = get(harness, auth_headers, contract_id)
    runner = harness.use_recording_runner()
    harness.clock.advance(60)

    response = retry(harness, auth_headers, contract_id)

    assert response.status_code == 202
    during = response.json()
    assert during["status"] == "analyzing"
    assert during["findings"] == first["findings"]
    assert during["email_draft"] == first["email_draft"]
    assert during["analyzed_at"] == first["analyzed_at"]

    run_scheduled(harness, runner)
    after = get(harness, auth_headers, contract_id)
    assert after["status"] == "done"
    assert after["analyzed_at"] != first["analyzed_at"]
    assert {f["id"] for f in after["findings"]}.isdisjoint({f["id"] for f in first["findings"]})


def test_failed_retry_preserves_previous_results(harness, auth_headers):
    contract_id = harness.create_contract(auth_headers)["id"]
    first = get(harness, auth_headers, contract_id)
    runner = harness.use_recording_runner()
    retry(harness, auth_headers, contract_id)

    contract, run_id = runner.scheduled[-1]
    run_analysis(replace(harness.context, analyzer=FailingAnalyzer()), contract, run_id)

    after = get(harness, auth_headers, contract_id)
    assert after["status"] == "failed"
    assert after["findings"] == first["findings"]
    assert after["email_draft"] == first["email_draft"]
    assert after["analyzed_at"] == first["analyzed_at"]
    assert after["risk_summary"] == first["risk_summary"]


def test_retry_while_analyzing_is_409(harness, auth_headers):
    harness.use_recording_runner()
    contract_id = harness.create_contract(auth_headers)["id"]

    assert_error(retry(harness, auth_headers, contract_id), 409, "ANALYSIS_IN_PROGRESS")


def test_retry_after_failure_succeeds():
    harness = Harness(analyzer=FailingAnalyzer())
    headers = harness.register()
    contract_id = harness.create_contract(headers)["id"]
    runner = harness.use_recording_runner()

    response = retry(harness, headers, contract_id)

    assert response.status_code == 202
    assert response.json()["status"] == "analyzing"
    assert len(runner.scheduled) == 1


def test_late_task_from_superseded_run_commits_nothing(harness, auth_headers):
    runner = harness.use_recording_runner()
    contract_id = harness.create_contract(auth_headers)["id"]
    harness.clock.advance(601)
    assert get(harness, auth_headers, contract_id)["status"] == "failed"  # stale
    retry(harness, auth_headers, contract_id)

    run_scheduled(harness, runner, index=0)  # the lost first task finally finishes

    body = get(harness, auth_headers, contract_id)
    assert body["status"] == "analyzing"
    assert body["findings"] == []
    run_scheduled(harness, runner, index=1)
    assert get(harness, auth_headers, contract_id)["status"] == "done"


def test_stale_analysis_becomes_failed_on_read(harness, auth_headers):
    harness.use_recording_runner()
    contract_id = harness.create_contract(auth_headers)["id"]

    harness.clock.advance(600)
    assert get(harness, auth_headers, contract_id)["status"] == "analyzing"
    harness.clock.advance(1)
    assert get(harness, auth_headers, contract_id)["status"] == "failed"


def stale_contract(harness, headers) -> str:
    harness.use_recording_runner()
    contract_id = harness.create_contract(headers)["id"]
    harness.clock.advance(601)
    return contract_id


def test_stale_rule_applies_to_list(harness, auth_headers):
    stale_contract(harness, auth_headers)
    items = harness.client.get("/contracts", headers=auth_headers).json()["items"]
    assert items[0]["status"] == "failed"


def test_stale_rule_applies_to_rename(harness, auth_headers):
    contract_id = stale_contract(harness, auth_headers)
    response = harness.client.patch(
        f"/contracts/{contract_id}", json={"title": "Renamed"}, headers=auth_headers
    )
    assert response.json()["status"] == "failed"


def test_stale_rule_unblocks_retry(harness, auth_headers):
    contract_id = stale_contract(harness, auth_headers)
    response = retry(harness, auth_headers, contract_id)
    assert response.status_code == 202
    assert response.json()["status"] == "analyzing"


def test_stale_rule_unblocks_delete(harness, auth_headers):
    contract_id = stale_contract(harness, auth_headers)
    assert harness.client.delete(f"/contracts/{contract_id}", headers=auth_headers).status_code == 204


def test_stale_failure_keeps_previous_results(harness, auth_headers):
    contract_id = harness.create_contract(auth_headers)["id"]
    first = get(harness, auth_headers, contract_id)
    harness.use_recording_runner()
    retry(harness, auth_headers, contract_id)
    harness.clock.advance(601)

    body = get(harness, auth_headers, contract_id)

    assert body["status"] == "failed"
    assert body["findings"] == first["findings"]
    assert body["analyzed_at"] == first["analyzed_at"]


def test_stale_threshold_comes_from_settings():
    harness = Harness(stale_after=30)
    headers = harness.register()
    harness.use_recording_runner()
    contract_id = harness.create_contract(headers)["id"]

    harness.clock.advance(31)

    assert get(harness, headers, contract_id)["status"] == "failed"
