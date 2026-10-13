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


def test_output_cut_twice_is_cached_as_a_model_failure(p1):
    entry = runner.analyze_record(p1, RejectingClient("Groq output was cut at max_completion_tokens=4000"))
    assert entry["error"]["type"] == "truncated" and "findings" not in entry


def test_each_call_records_its_output_tokens_budget_and_finish_reason(p1):
    class Reporting(FakeClient):
        def complete_json(self, messages, schema_name, schema):
            content = super().complete_json(messages, schema_name, schema).content
            return GroqResult(content, 1000, completion_tokens=250, finish_reason="stop", max_completion_tokens=2_000,
                              prompt_tokens=700)

    entry = runner.analyze_record(p1, Reporting("Invoices are payable Net 90."))
    call = entry["calls"][0]
    assert (call["output_tokens"], call["output_budget"], call["finish_reason"]) == (250, 2_000, "stop")
    assert call["prompt_tokens"] == 700


def test_other_provider_errors_stop_the_run(p1):
    with pytest.raises(GroqError):
        runner.analyze_record(p1, RejectingClient("Groq returned HTTP 429: rate limit"))


class SizeClient(FakeClient):
    """Records the length of every findings request."""

    def __init__(self):
        super().__init__("x")
        self.sizes = []

    def complete_json(self, messages, schema_name, schema):
        if schema_name != "client_email":
            self.sizes.append(len(messages[-1]["content"]))
        return super().complete_json(messages, schema_name, schema)


def test_chunk_size_is_passed_to_the_analyzer(p1):
    small, whole = SizeClient(), SizeClient()
    runner.analyze_record(p1, small, max_chunk_chars=500)
    runner.analyze_record(p1, whole, max_chunk_chars=60_000)
    assert len(small.sizes) > 1 and len(whole.sizes) == 1


class PromptClient(FakeClient):
    """Records the system prompt of every findings request."""

    def __init__(self):
        super().__init__("x")
        self.prompts = set()

    def complete_json(self, messages, schema_name, schema):
        if schema_name == "contract_findings":
            self.prompts.add(messages[0]["content"])
        return super().complete_json(messages, schema_name, schema)


def test_another_findings_prompt_reaches_the_model(p1):
    client = PromptClient()
    runner.analyze_record(p1, client, findings_prompt="Find nothing.")
    assert client.prompts == {"Find nothing."}


def test_gemini_client_uses_its_key_model_endpoint_and_output_limit():
    from evaluation.__main__ import llm_client

    client = llm_client("gemini", 8_000, env={"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-3.1-flash-lite"})
    assert client._api_url.startswith("https://generativelanguage.googleapis.com/v1beta/openai/")
    assert client._model == "gemini-3.1-flash-lite" and client._max_completion_tokens == 8_000
    assert client._limiter._capacity == (250_000.0, 10.0) and client._temperature is None
    assert llm_client("gemini", env={"GEMINI_API_KEY": "test-key"}, temperature=0.0)._temperature == 0.0
    assert client._reasoning_effort == "low"
    assert llm_client("groq", env={"GROQ_API_KEY": "test-key"}, reasoning_effort="medium")._reasoning_effort == "medium"


def test_groq_stays_the_default_provider():
    from evaluation.__main__ import llm_client

    client = llm_client(env={"GROQ_API_KEY": "test-key"})
    assert "api.groq.com" in client._api_url and client._model == "openai/gpt-oss-120b"
    assert client._max_completion_tokens == 2_000 and client._limiter._capacity == (8_000.0, 30.0)
