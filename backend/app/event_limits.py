"""Spam limits for the public analytics endpoint (docs/analytics.md).

`POST /events` needs no login, so anyone could fill the `events` table. Two fixed windows
cap it: events per client IP per minute, and events per UTC day in total. Over a limit the
event is dropped quietly; the endpoint still answers 204, so a caller learns nothing.
Counters live in memory, per process: a restart resets them, which is fine for this purpose.
The IP is used only for counting and is never stored.
"""

import threading
from datetime import datetime

from fastapi import Request

PER_IP_PER_MINUTE = 30
PER_DAY = 5_000


class EventLimiter:
    def __init__(self, per_ip_per_minute: int = PER_IP_PER_MINUTE, per_day: int = PER_DAY):
        self._per_ip_per_minute = per_ip_per_minute
        self._per_day = per_day
        self._minute = ""
        self._per_ip: dict[str, int] = {}
        self._day = ""
        self._today = 0
        self._lock = threading.Lock()

    def allow(self, ip: str, now: datetime) -> bool:
        minute, day = now.strftime("%Y-%m-%dT%H:%M"), now.strftime("%Y-%m-%d")
        with self._lock:
            if minute != self._minute:
                self._minute, self._per_ip = minute, {}
            if day != self._day:
                self._day, self._today = day, 0
            if self._today >= self._per_day or self._per_ip.get(ip, 0) >= self._per_ip_per_minute:
                return False
            self._per_ip[ip] = self._per_ip.get(ip, 0) + 1
            self._today += 1
            return True


def client_ip(request: Request) -> str:
    """The visitor's IP behind the Lightsail load balancer.

    The balancer appends the address it saw to X-Forwarded-For, so the last entry is the
    one a client cannot forge; earlier entries are whatever the client sent.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded.strip():
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else ""
