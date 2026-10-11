import json

import pytest

from app.groq_client import GroqError, GroqResult
from evaluation import runner


class FakeClient:
    """Answers the findings call with one quote from the contract (or an invented one) and the email call."""

    def __init__(self, quote):
        self.quote = quote

    def complete_json(self, messages, schema_name, schema):
        if schema_name == "client_email":
            return GroqResult({"subject": "Changes", "body": "Please consider the changes."}, 50)
        finding = {"category": "unfavorable_payment_terms", "risk_level": "high", "quoted_text": self.quote,
                   "explanation": "Long payment term.", "suggested_change": "Net 30."}
        return GroqResult({"findings": [finding]}, 1000)


@pytest.fixture
def p1():
    return next(r for r in runner.load_gold("freelance") if r["id"] == "freelance:P1")


def test_a_found_quote_is_kept_with_offsets_and_calls_are_recorded(p1):
    entry = runner.analyze_record(p1, FakeClient("Invoices are payable Net 90."))
    [finding] = entry["findings"]
    assert finding["start"] is not None and finding["risk_level"] == "high" and entry["email"]
    assert [c["schema"] for c in entry["calls"]][-1] == "client_email" and not entry["dropped"]


def test_an_invented_quote_is_dropped_with_its_reason(p1):
    entry = runner.analyze_record(p1, FakeClient("Payment is due in 365 days."))
    assert entry["findings"] == [] and {"category": "unfavorable_payment_terms", "reason": "quote_not_found"} in entry["dropped"]


def test_run_caches_each_contract_and_skips_it_next_time(tmp_path, monkeypatch, p1):
    monkeypatch.setattr(runner, "load_gold", lambda name: [p1])
    assert runner.run("freelance", tmp_path, FakeClient("Invoices are payable Net 90."), log=lambda _: None) == 1
    assert runner.run("freelance", tmp_path, FakeClient("x"), log=lambda _: None) == 0
    cached = json.loads(runner.cache_path(tmp_path, p1["id"]).read_text())
    assert cached["id"] == "freelance:P1" and len(cached["findings"]) == 1


class RejectingClient:
    def __init__(self, message):
        self.message = message

    def complete_json(self, messages, schema_name, schema):
        raise GroqError(self.message)


def test_groq_rejecting_invalid_json_is_cached_as_a_model_failure(p1):
    entry = runner.analyze_record(p1, RejectingClient("Groq returned HTTP 400: Failed to validate JSON. Please adjust your prompt."))
    assert entry["error"]["type"] == "invalid_json" and "findings" not in entry


def test_other_provider_errors_stop_the_run(p1):
    with pytest.raises(GroqError):
        runner.analyze_record(p1, RejectingClient("Groq returned HTTP 429: rate limit"))
