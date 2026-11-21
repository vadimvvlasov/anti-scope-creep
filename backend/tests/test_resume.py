"""Analyses a shutdown interrupted are taken up again when the backend starts (docs/spec.md "Stale analysis rule")."""

import asyncio
import time
from uuid import UUID

from app.analyzer import StubAnalyzer
from app.runner import resume_interrupted_analyses, run_analysis
from tests.conftest import Harness
from tests.samples import ENGLISH_CONTRACT


class OrderRecordingAnalyzer(StubAnalyzer):
    def __init__(self) -> None:
        self.texts: list[str] = []

    def analyze(self, source_text: str):
        self.texts.append(source_text)
        return super().analyze(source_text)


def _interrupted(harness: Harness, headers: dict, text: str = ENGLISH_CONTRACT, title: str = "Contract") -> str:
    """A contract left in `analyzing` by a process that is gone: scheduled, never run."""
    harness.use_recording_runner()
    return harness.create_contract(headers, text=text, title=title)["id"]


def _status(harness: Harness, headers: dict, contract_id: str) -> dict:
    response = harness.client.get(f"/contracts/{contract_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_an_interrupted_analysis_is_resumed_and_ends_done() -> None:
    harness = Harness()
    headers = harness.register()
    contract_id = _interrupted(harness, headers)
    assert _status(harness, headers, contract_id)["status"] == "analyzing"

    asyncio.run(resume_interrupted_analyses(harness.context))

    detail = _status(harness, headers, contract_id)
    assert detail["status"] == "done"
    assert detail["findings"]


def test_the_oldest_runs_first_and_one_at_a_time() -> None:
    analyzer = OrderRecordingAnalyzer()
    harness = Harness(analyzer=analyzer)
    headers = harness.register()
    older = _interrupted(harness, headers, text=ENGLISH_CONTRACT + " first", title="first")
    harness.clock.advance(30)
    newer = _interrupted(harness, headers, text=ENGLISH_CONTRACT + " second", title="second")

    asyncio.run(resume_interrupted_analyses(harness.context))

    assert [text.rsplit(" ", 1)[-1] for text in analyzer.texts] == ["first", "second"]
    assert _status(harness, headers, older)["status"] == "done"
    assert _status(harness, headers, newer)["status"] == "done"


def test_a_late_commit_of_the_old_run_changes_nothing() -> None:
    harness = Harness()
    headers = harness.register()
    runner = harness.use_recording_runner()
    contract_id = harness.create_contract(headers)["id"]
    _, old_run = runner.scheduled[0]

    found = harness.context.store.restart_interrupted_analyses(3, harness.clock())
    assert found.runs and found.runs[0][1] != old_run

    run_analysis(harness.context, UUID(contract_id), old_run)  # the process that was shut down finishing late
    assert _status(harness, headers, contract_id)["status"] == "analyzing"


def test_a_contract_resumed_too_often_is_failed_and_keeps_its_earlier_results() -> None:
    harness = Harness()
    headers = harness.register()
    contract_id = harness.create_contract(headers)["id"]  # done: the default runner ran it
    earlier = _status(harness, headers, contract_id)
    assert earlier["status"] == "done"
    harness.use_recording_runner()
    assert harness.client.post(f"/contracts/{contract_id}/retry", headers=headers).status_code == 202

    store = harness.context.store
    for _ in range(3):
        assert store.restart_interrupted_analyses(3, harness.clock()).runs
    found = store.restart_interrupted_analyses(3, harness.clock())

    assert found.runs == [] and found.failed == 1
    failed = _status(harness, headers, contract_id)
    assert failed["status"] == "failed"
    assert failed["analyzed_at"] == earlier["analyzed_at"]
    assert failed["findings"] == earlier["findings"]


def test_a_new_start_by_the_user_resets_the_count() -> None:
    harness = Harness()
    headers = harness.register()
    contract_id = _interrupted(harness, headers)
    store = harness.context.store
    _, run_id = store.restart_interrupted_analyses(3, harness.clock()).runs[0]
    assert store.get_contract_for_analysis(UUID(contract_id), run_id).analysis_resumes == 1

    store.fail_analysis(UUID(contract_id), run_id, harness.clock())
    assert harness.client.post(f"/contracts/{contract_id}/retry", headers=headers).status_code == 202
    started = harness.context.store.restart_interrupted_analyses(3, harness.clock()).runs[0][1]
    assert store.get_contract_for_analysis(UUID(contract_id), started).analysis_resumes == 1


def test_a_waiting_contract_does_not_go_stale() -> None:
    harness = Harness(stale_after=600)
    headers = harness.register()
    contract_id = _interrupted(harness, headers)
    store = harness.context.store
    _, run_id = store.restart_interrupted_analyses(3, harness.clock()).runs[0]

    harness.clock.advance(590)
    assert store.touch_analyses([run_id], harness.clock()) == 1
    harness.clock.advance(590)  # 1180 s after the restart, 590 s after the last touch

    assert _status(harness, headers, contract_id)["status"] == "analyzing"


def test_a_resume_that_hangs_still_goes_stale() -> None:
    harness = Harness(stale_after=600)
    headers = harness.register()
    contract_id = _interrupted(harness, headers)
    harness.context.store.restart_interrupted_analyses(3, harness.clock())

    harness.clock.advance(601)

    assert _status(harness, headers, contract_id)["status"] == "failed"


def test_resuming_can_be_turned_off() -> None:
    harness = Harness(max_resumes=0)
    headers = harness.register()
    contract_id = _interrupted(harness, headers)

    asyncio.run(resume_interrupted_analyses(harness.context))

    assert _status(harness, headers, contract_id)["status"] == "analyzing"


def test_nothing_to_resume_is_a_quiet_no_op() -> None:
    harness = Harness()
    headers = harness.register()
    contract_id = harness.create_contract(headers)["id"]  # done

    asyncio.run(resume_interrupted_analyses(harness.context))

    assert _status(harness, headers, contract_id)["status"] == "done"


def test_a_start_of_the_app_resumes_what_was_left() -> None:
    from fastapi.testclient import TestClient

    harness = Harness()
    headers = harness.register()
    contract_id = _interrupted(harness, headers)

    with TestClient(harness.app) as started:  # the lifespan runs: this is the start of the backend
        for _ in range(100):
            if started.get(f"/contracts/{contract_id}", headers=headers).json()["status"] != "analyzing":
                break
            time.sleep(0.05)

    assert _status(harness, headers, contract_id)["status"] == "done"
