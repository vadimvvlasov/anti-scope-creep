import threading

import pytest

from app.ratelimit import TokenBucketLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def limiter(clock: FakeClock, tokens: int = 8_000, requests: int = 30) -> TokenBucketLimiter:
    return TokenBucketLimiter(tokens, requests, clock=clock, sleep=clock.sleep)


def test_requests_within_the_budget_do_not_wait():
    clock = FakeClock()
    bucket = limiter(clock)
    assert bucket.acquire(3_000) == 0
    assert bucket.acquire(3_000) == 0
    assert clock.sleeps == []


def test_a_request_over_the_token_budget_waits_for_the_refill():
    clock = FakeClock()
    bucket = limiter(clock)
    bucket.acquire(6_500)
    waited = bucket.acquire(6_500)  # 1,500 left, 5,000 missing at 8,000 per minute

    assert waited == pytest.approx(37.5)
    assert clock.now == pytest.approx(37.5)


def test_one_chunk_per_minute_for_maximum_size_requests():
    clock = FakeClock()
    bucket = limiter(clock)
    for _ in range(4):
        bucket.acquire(8_000)
    assert clock.now == pytest.approx(180.0)


def test_the_request_budget_limits_small_requests():
    clock = FakeClock()
    bucket = limiter(clock, requests=2)
    bucket.acquire(10)
    bucket.acquire(10)
    assert bucket.acquire(10) == pytest.approx(30.0)  # 2 per minute: one more after 30 s


def test_a_request_larger_than_the_budget_waits_for_a_full_bucket_only():
    clock = FakeClock()
    bucket = limiter(clock)
    bucket.acquire(4_000)
    assert bucket.acquire(20_000) == pytest.approx(30.0)


def test_idle_time_refills_but_not_beyond_capacity():
    clock = FakeClock()
    bucket = limiter(clock)
    clock.now = 3_600.0
    bucket.acquire(8_000)
    assert bucket.acquire(1) > 0


def test_concurrent_acquires_never_overspend():
    bucket = TokenBucketLimiter(1_000, 1_000)  # real clock: no thread may wait here
    results = []
    threads = [threading.Thread(target=lambda: results.append(bucket.acquire(100))) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [0.0] * 10
    assert bucket._available[0] == pytest.approx(0.0, abs=5.0)


def test_limits_must_be_positive():
    with pytest.raises(ValueError):
        TokenBucketLimiter(0, 30)
