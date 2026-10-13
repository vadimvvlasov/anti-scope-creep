"""Per-user analysis caps (security finding MR-2): one running at a time, a daily limit."""

from app.config import Settings
from tests.conftest import Harness, assert_error


def limited(max_running: int = 1, daily_limit: int = 5) -> tuple[Harness, dict]:
    harness = Harness(max_running=max_running, daily_limit=daily_limit)
    return harness, harness.register()


def test_a_second_upload_while_one_is_running_is_429_and_stores_nothing():
    harness, headers = limited()
    harness.use_recording_runner()
    harness.create_contract(headers)

    assert_error(harness.paste(headers), 429, "ANALYSIS_ALREADY_RUNNING")
    assert harness.client.get("/contracts", headers=headers).json()["total_count"] == 1


def test_the_running_cap_is_per_user():
    harness, headers = limited()
    harness.use_recording_runner()
    harness.create_contract(headers)

    other = harness.register("other@example.com")
    assert harness.paste(other).status_code == 202


def test_a_finished_analysis_frees_the_slot():
    harness, headers = limited()
    harness.create_contract(headers)  # the stub analyzer finishes in the background task

    assert harness.paste(headers).status_code == 202


def test_a_stale_analysis_frees_the_slot():
    harness, headers = limited()
    harness.use_recording_runner()
    harness.create_contract(headers)
    harness.clock.advance(601)

    assert harness.paste(headers).status_code == 202


def test_retry_counts_against_both_caps():
    harness, headers = limited(daily_limit=2)
    contract = harness.create_contract(headers)
    assert harness.client.post(f"/contracts/{contract['id']}/retry", headers=headers).status_code == 202

    error = assert_error(
        harness.client.post(f"/contracts/{contract['id']}/retry", headers=headers),
        429,
        "DAILY_ANALYSIS_LIMIT_REACHED",
    )
    assert "2 analyses in 24 hours" in error["message"]


def test_retry_of_the_running_contract_stays_409():
    harness, headers = limited()
    harness.use_recording_runner()
    contract = harness.create_contract(headers)

    response = harness.client.post(f"/contracts/{contract['id']}/retry", headers=headers)
    assert_error(response, 409, "ANALYSIS_IN_PROGRESS")


def test_the_daily_limit_is_a_rolling_24_hours_and_survives_deletes():
    harness, headers = limited(daily_limit=2)
    for _ in range(2):
        contract = harness.create_contract(headers)
        assert harness.client.delete(f"/contracts/{contract['id']}", headers=headers).status_code == 204

    assert_error(harness.paste(headers), 429, "DAILY_ANALYSIS_LIMIT_REACHED")
    harness.clock.advance(24 * 3600 + 1)
    assert harness.paste(headers).status_code == 202


def test_zero_turns_the_caps_off():
    harness, headers = limited(max_running=0, daily_limit=0)
    harness.use_recording_runner()
    for _ in range(7):
        harness.create_contract(headers)


def test_settings_read_the_caps_from_the_environment():
    env = {"DATABASE_URL": "sqlite://", "JWT_SECRET": "x" * 32}
    default = Settings.from_env(env)
    assert (default.analysis_max_running_per_user, default.analysis_daily_limit_per_user) == (1, 5)
    custom = Settings.from_env(env | {"ANALYSIS_MAX_RUNNING_PER_USER": "2", "ANALYSIS_DAILY_LIMIT_PER_USER": "0"})
    assert (custom.analysis_max_running_per_user, custom.analysis_daily_limit_per_user) == (2, 0)


def test_the_service_records_one_start_per_analysis():
    harness, headers = limited(max_running=0, daily_limit=0)
    harness.use_recording_runner()
    harness.create_contract(headers)
    harness.create_contract(headers)
    user_id = harness.store.get_user_by_email("user@example.com").id

    assert harness.store.count_analysis_starts(user_id, harness.clock().replace(year=2000)) == 2
