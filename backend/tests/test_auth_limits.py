"""Login and registration attempt limits (docs/spec.md "Authentication rate limits")."""

from datetime import UTC, datetime

from app.auth_limits import LOGIN_FAILURES_PER_EMAIL, LOGIN_PER_IP, REGISTER_PER_IP, WindowCounter
from app.config import Settings
from tests.conftest import Harness, assert_error

PASSWORD = "password123"


def login(harness: Harness, email: str, password: str, ip: str = "203.0.113.1"):
    return harness.client.post("/auth/login", json={"email": email, "password": password},
                               headers={"X-Forwarded-For": ip})


def register(harness: Harness, email: str, ip: str = "203.0.113.1"):
    return harness.client.post("/auth/register", json={"email": email, "password": PASSWORD},
                               headers={"X-Forwarded-For": ip})


def test_registration_is_limited_per_ip_and_window(harness):
    for n in range(REGISTER_PER_IP):
        assert register(harness, f"user{n}@example.com").status_code == 201
    error = assert_error(register(harness, "one-more@example.com"), 429, "TOO_MANY_ATTEMPTS")
    assert "email" not in error["message"].lower()
    assert register(harness, "other-ip@example.com", ip="198.51.100.7").status_code == 201
    harness.clock.advance(60 * 60)
    assert register(harness, "next-hour@example.com").status_code == 201


def test_duplicate_registrations_count_too(harness):
    assert register(harness, "taken@example.com").status_code == 201
    for _ in range(REGISTER_PER_IP - 1):
        assert_error(register(harness, "taken@example.com"), 409, "EMAIL_ALREADY_EXISTS")
    assert_error(register(harness, "taken@example.com"), 429, "TOO_MANY_ATTEMPTS")


def test_failed_logins_lock_the_email_even_with_the_right_password(harness):
    harness.register("victim@example.com", PASSWORD)
    for _ in range(LOGIN_FAILURES_PER_EMAIL):
        assert_error(login(harness, "victim@example.com", "wrong-password"), 401, "INVALID_CREDENTIALS")
    assert_error(login(harness, "victim@example.com", PASSWORD), 429, "TOO_MANY_ATTEMPTS")
    # From another address too: the lock is on the email.
    assert_error(login(harness, " Victim@Example.com ", PASSWORD, ip="198.51.100.7"), 429, "TOO_MANY_ATTEMPTS")
    harness.clock.advance(15 * 60)
    assert login(harness, "victim@example.com", PASSWORD).status_code == 200


def test_an_unknown_email_is_limited_the_same_way(harness):
    harness.register("known@example.com", PASSWORD)
    responses = {}
    for email in ("known@example.com", "nobody@example.com"):
        for _ in range(LOGIN_FAILURES_PER_EMAIL):
            login(harness, email, "wrong-password", ip=f"198.51.100.{len(responses) + 10}")
        responses[email] = login(harness, email, "wrong-password", ip=f"198.51.100.{len(responses) + 20}")
    known, unknown = responses.values()
    assert known.status_code == unknown.status_code == 429
    assert known.json() == unknown.json()


def test_successful_logins_do_not_lock_the_email(harness):
    harness.register("busy@example.com", PASSWORD)
    for n in range(LOGIN_FAILURES_PER_EMAIL + 2):
        assert login(harness, "busy@example.com", PASSWORD, ip=f"198.51.100.{n}").status_code == 200


def test_logins_are_limited_per_ip(harness):
    harness.register("a@example.com", PASSWORD)
    for _ in range(LOGIN_PER_IP):
        assert login(harness, "a@example.com", PASSWORD).status_code == 200
    assert_error(login(harness, "a@example.com", PASSWORD), 429, "TOO_MANY_ATTEMPTS")
    assert login(harness, "a@example.com", PASSWORD, ip="198.51.100.9").status_code == 200


def test_limits_come_from_settings_and_zero_turns_them_off():
    env = {"DATABASE_URL": "x"}
    default = Settings.from_env(env)
    assert (default.auth_login_per_ip, default.auth_login_failures_per_email, default.auth_register_per_ip) == (
        LOGIN_PER_IP, LOGIN_FAILURES_PER_EMAIL, REGISTER_PER_IP)
    off = Settings.from_env({**env, "AUTH_REGISTER_PER_IP": "0", "AUTH_LOGIN_PER_IP": "0"})
    assert (off.auth_register_per_ip, off.auth_login_per_ip) == (0, 0)


def test_a_zero_limit_never_fills():
    now = datetime(2026, 11, 17, tzinfo=UTC)
    counter = WindowCounter(0, 60)
    for _ in range(100):
        counter.add("203.0.113.1", now)
    assert not counter.full("203.0.113.1", now)
