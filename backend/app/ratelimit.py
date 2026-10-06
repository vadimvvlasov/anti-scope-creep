"""Client-side rate limiting for the LLM provider (docs/architecture.md, section 4).

Two token buckets, one for tokens per minute and one for requests per minute, refill
continuously. A request waits until both have room, so the backend stays below the
provider's limits instead of collecting 429 responses. One limiter is shared by every
analysis in the process: background tasks run in threads, so it is thread-safe.
"""

import threading
import time
from collections.abc import Callable

SECONDS_PER_MINUTE = 60.0


class TokenBucketLimiter:
    def __init__(
        self,
        tokens_per_minute: int,
        requests_per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if tokens_per_minute < 1 or requests_per_minute < 1:
            raise ValueError("limits must be positive")
        self._capacity = (float(tokens_per_minute), float(requests_per_minute))
        self._available = list(self._capacity)
        self._clock = clock
        self._sleep = sleep
        self._updated = clock()
        self._lock = threading.Lock()

    def acquire(self, tokens: int) -> float:
        """Block until `tokens` and one request fit the budget; return the seconds waited.

        A request larger than the whole per-minute budget waits for a full bucket: the
        provider decides whether it is accepted.
        """
        needed = (min(float(tokens), self._capacity[0]), 1.0)
        waited = 0.0
        while True:
            with self._lock:
                self._refill()
                wait = max(self._wait_for(i, needed[i]) for i in range(2))
                if wait <= 0:
                    self._available = [self._available[i] - needed[i] for i in range(2)]
                    return waited
            self._sleep(wait)
            waited += wait

    def _refill(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._updated)
        self._updated = now
        for i, capacity in enumerate(self._capacity):
            self._available[i] = min(capacity, self._available[i] + elapsed * capacity / SECONDS_PER_MINUTE)

    def _wait_for(self, index: int, amount: float) -> float:
        missing = amount - self._available[index]
        return missing * SECONDS_PER_MINUTE / self._capacity[index] if missing > 0 else 0.0
