"""Attempt limits for login and registration (docs/spec.md "Authentication rate limits").

The backend has no WAF in front of it, so password guessing and sign-up spam are capped here:

- login: attempts per client IP, and failed attempts per email, in a 15-minute window;
- registration: attempts per client IP in a 1-hour window.

Each limit is a server setting (AUTH_LOGIN_PER_IP, AUTH_LOGIN_FAILURES_PER_EMAIL,
AUTH_REGISTER_PER_IP); 0 turns it off, as the local stack does for the e2e tests.

An email that does not exist is counted like one that does, and the error is the same, so the
limit tells a caller nothing about which accounts exist. Fixed windows, counters in memory per
process (a restart resets them), like the analytics spam limits; the IP and the email are only
counted, never stored or logged.
"""

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings

LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_PER_IP = 20
LOGIN_FAILURES_PER_EMAIL = 5
REGISTER_WINDOW_SECONDS = 60 * 60
REGISTER_PER_IP = 5


class WindowCounter:
    """Counts per key in fixed windows; all counts reset when a new window starts."""

    def __init__(self, limit: int, window_seconds: int):
        self._limit = limit
        self._window = window_seconds
        self._bucket = -1
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def _roll(self, now: datetime) -> None:
        bucket = int(now.timestamp()) // self._window
        if bucket != self._bucket:
            self._bucket, self._counts = bucket, {}

    def full(self, key: str, now: datetime) -> bool:
        if self._limit <= 0:  # off
            return False
        with self._lock:
            self._roll(now)
            return self._counts.get(key, 0) >= self._limit

    def add(self, key: str, now: datetime) -> None:
        with self._lock:
            self._roll(now)
            self._counts[key] = self._counts.get(key, 0) + 1


@dataclass
class AuthLimiter:
    login_ip: WindowCounter
    login_email: WindowCounter
    register_ip: WindowCounter

    @classmethod
    def default(cls) -> "AuthLimiter":
        return cls.of(LOGIN_PER_IP, LOGIN_FAILURES_PER_EMAIL, REGISTER_PER_IP)

    @classmethod
    def of(cls, login_per_ip: int, login_failures_per_email: int, register_per_ip: int) -> "AuthLimiter":
        return cls(
            WindowCounter(login_per_ip, LOGIN_WINDOW_SECONDS),
            WindowCounter(login_failures_per_email, LOGIN_WINDOW_SECONDS),
            WindowCounter(register_per_ip, REGISTER_WINDOW_SECONDS),
        )

    @classmethod
    def from_settings(cls, settings: "Settings") -> "AuthLimiter":
        return cls.of(settings.auth_login_per_ip, settings.auth_login_failures_per_email,
                      settings.auth_register_per_ip)

    def login_allowed(self, ip: str, email: str, now: datetime) -> bool:
        """Checked before the password, so a locked email is refused even with the right password."""
        return not (self.login_ip.full(ip, now) or self.login_email.full(email, now))

    def register_allowed(self, ip: str, now: datetime) -> bool:
        return not self.register_ip.full(ip, now)
