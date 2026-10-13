"""Product analytics: POST /events stores typed funnel events and drops spam quietly."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import events
from app.event_limits import EventLimiter
from tests.conftest import Harness, assert_error

VISITOR = "0b6f6c2e-6a43-4c1e-9f3e-0d2b2c1a9e11"
PAGEVIEW = {"event": "pageview", "distinct_id": VISITOR, "properties": {"path": "/", "utm_source": "reddit"}}


def stored(harness: Harness) -> list[dict]:
    with harness.store._engine.connect() as conn:
        rows = conn.execute(select(events).order_by(events.c.received_at)).all()
    return [dict(row._mapping) for row in rows]


def test_an_event_is_stored_without_login(harness, client):
    response = client.post("/events", json=PAGEVIEW)

    assert response.status_code == 204
    assert response.content == b""
    [row] = stored(harness)
    assert (row["event"], row["distinct_id"], row["properties"]) == (
        "pageview", VISITOR, {"path": "/", "utm_source": "reddit"},
    )
    assert row["received_at"] == harness.clock.now


def test_only_the_properties_sent_are_stored_with_their_types(harness, client):
    body = {"event": "pro_waitlist_joined", "distinct_id": VISITOR,
            "properties": {"placement": "header", "price_usd": 19}}
    assert client.post("/events", json=body).status_code == 204
    assert stored(harness)[0]["properties"] == {"placement": "header", "price_usd": 19}


def test_properties_may_be_left_out(harness, client):
    assert client.post("/events", json={"event": "signup_completed", "distinct_id": VISITOR}).status_code == 204
    assert stored(harness)[0]["properties"] == {}


@pytest.mark.parametrize(
    "body",
    [
        {**PAGEVIEW, "event": "$pageview"},
        {**PAGEVIEW, "event": "contract_text"},
        {**PAGEVIEW, "distinct_id": ""},
        {**PAGEVIEW, "distinct_id": "x" * 65},
        {**PAGEVIEW, "distinct_id": "someone@example.com"},
        {**PAGEVIEW, "properties": {"contract": "Client may request unlimited revisions"}},
        {**PAGEVIEW, "properties": {"Path": "/"}},
        {**PAGEVIEW, "properties": {"path": "x" * 101}},
        {**PAGEVIEW, "properties": {"path": {"a": 1}}},
        {**PAGEVIEW, "properties": {"format": "xlsx"}},
        {**PAGEVIEW, "properties": {"price_usd": -1}},
        {**PAGEVIEW, "extra": 1},
        {"distinct_id": VISITOR},
    ],
)
def test_anything_outside_the_event_schema_is_rejected(harness, client, body):
    assert_error(client.post("/events", json=body), 422, "VALIDATION_ERROR")
    assert stored(harness) == []


def test_events_over_the_per_ip_limit_are_dropped_quietly():
    harness = Harness()
    harness.app.state.context.event_limiter._per_ip_per_minute = 2
    for _ in range(3):
        assert harness.client.post("/events", json=PAGEVIEW).status_code == 204
    assert len(stored(harness)) == 2


NOW = datetime(2026, 10, 13, 12, 0, 30, tzinfo=UTC)


def test_the_per_ip_window_is_one_minute():
    limiter = EventLimiter(per_ip_per_minute=1, per_day=100)
    assert limiter.allow("1.1.1.1", NOW)
    assert not limiter.allow("1.1.1.1", NOW)
    assert limiter.allow("2.2.2.2", NOW)
    assert limiter.allow("1.1.1.1", NOW + timedelta(minutes=1))


def test_the_daily_cap_counts_every_ip_and_resets_at_midnight_utc():
    limiter = EventLimiter(per_ip_per_minute=100, per_day=2)
    assert limiter.allow("1.1.1.1", NOW)
    assert limiter.allow("2.2.2.2", NOW)
    assert not limiter.allow("3.3.3.3", NOW + timedelta(hours=1))
    assert limiter.allow("3.3.3.3", NOW + timedelta(days=1))


def test_the_last_forwarded_address_is_the_one_counted():
    harness = Harness()
    harness.app.state.context.event_limiter._per_ip_per_minute = 1
    post = lambda forwarded: harness.client.post(  # noqa: E731
        "/events", json=PAGEVIEW, headers={"X-Forwarded-For": forwarded}
    )
    post("9.9.9.9, 1.1.1.1")
    # A forged first entry does not buy a fresh quota: the balancer's entry is the same.
    post("8.8.8.8, 1.1.1.1")
    post("2.2.2.2")
    assert len(stored(harness)) == 2
