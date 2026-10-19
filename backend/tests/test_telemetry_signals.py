"""Metrics and spans of the analysis path, and the rule that no contract text reaches telemetry
(docs/architecture.md, section 6)."""

import io
import json
import logging
from dataclasses import dataclass

import httpx
import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from app import telemetry
from app.groq_analyzer import GroqAnalyzer
from app.groq_client import GroqError
from app.runner import run_analysis
from tests.conftest import Harness
from tests.fakes import FailingAnalyzer
from tests.test_groq_analyzer import CONTRACT as LLM_CONTRACT
from tests.test_groq_analyzer import SECRETS, FakeClient, finding
from tests.test_groq_client import MESSAGES, SCHEMA, Script, client, ok
from tests.test_runner import make_context, start


@dataclass
class Capture:
    spans: InMemorySpanExporter
    reader: InMemoryMetricReader
    logs: io.StringIO

    def points(self, name: str) -> dict[tuple, float]:
        """Data points of one metric as {sorted attributes: sum, or count for a histogram}."""
        found: dict[tuple, float] = {}
        data = self.reader.get_metrics_data()
        for resource in data.resource_metrics if data else []:
            for scope in resource.scope_metrics:
                for metric in scope.metrics:
                    if metric.name != name:
                        continue
                    for point in metric.data.data_points:
                        key = tuple(sorted(point.attributes.items()))
                        found[key] = getattr(point, "value", None) if hasattr(point, "value") else point.count
        return found

    def span(self, name: str):
        return next(s for s in self.spans.get_finished_spans() if s.name == name)

    def everything(self) -> str:
        """Every span, metric and log line as one string, to search for text that must not be there."""
        parts = []
        for span in self.spans.get_finished_spans():
            parts.append(span.to_json())
        data = self.reader.get_metrics_data()
        if data:
            parts.append(data.to_json())
        parts.append(self.logs.getvalue())
        return "\n".join(parts)


@pytest.fixture
def capture(monkeypatch) -> Capture:
    spans = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(spans))
    reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[reader])
    monkeypatch.setattr(telemetry, "tracer", lambda: tracer_provider.get_tracer("test"))
    monkeypatch.setattr(telemetry, "instruments", telemetry.build_instruments(meter_provider.get_meter("test")))
    logs = io.StringIO()
    handler = logging.StreamHandler(logs)
    handler.setFormatter(telemetry.JsonFormatter())
    handler.addFilter(telemetry.ContractContextFilter())
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    yield Capture(spans, reader, logs)
    root.removeHandler(handler)
    root.setLevel(previous_level)


def usage_response(prompt: int, completion: int) -> httpx.Response:
    body = json.dumps({"text": "hi"})
    return httpx.Response(200, json={
        "choices": [{"message": {"content": body}, "finish_reason": "stop"}],
        "usage": {"total_tokens": prompt + completion, "prompt_tokens": prompt, "completion_tokens": completion},
    })


def truncated_response() -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": ""}, "finish_reason": "length"}], "usage": {"total_tokens": 10},
    })


def test_llm_attempts_tokens_and_rate_limits_are_counted(capture):
    script = Script(httpx.Response(429, headers={"retry-after": "0"}), usage_response(100, 50))
    groq, _ = client(script)

    groq.complete_json(MESSAGES, "hi", SCHEMA)

    model = "openai/gpt-oss-120b"
    assert capture.points("llm.requests") == {
        (("model", model), ("status", "rate_limited")): 1, (("model", model), ("status", "ok")): 1,
    }
    assert capture.points("llm.rate_limited") == {(("model", model),): 1}
    assert capture.points("llm.tokens") == {(("kind", "input"), ("model", model)): 100, (("kind", "output"), ("model", model)): 50}
    assert capture.points("llm.request.duration") == {(("model", model),): 2}
    span = capture.span("llm.complete_json")
    assert span.attributes["llm.schema"] == "hi" and span.attributes["llm.prompt_tokens"] == 100


def test_an_answer_cut_at_the_cap_is_counted_with_the_retry_flag(capture):
    groq, _ = client(Script(truncated_response(), truncated_response()))

    with pytest.raises(GroqError):
        groq.complete_json(MESSAGES, "hi", SCHEMA)

    model = "openai/gpt-oss-120b"
    assert capture.points("llm.output_truncated") == {
        (("model", model), ("retried", "true")): 1, (("model", model), ("retried", "false")): 1,
    }
    span = capture.span("llm.complete_json")
    assert span.status.status_code == StatusCode.ERROR and span.status.description == "GroqError"


def test_a_done_analysis_is_counted_and_traced_end_to_end(capture):
    quote = "[PARTY_A] may request unlimited revisions until fully satisfied."
    fake = FakeClient(lambda text: [finding(quote), finding("A clause the contract does not contain.", category="scope_creep")])
    harness = Harness(analyzer=GroqAnalyzer(fake))
    headers = harness.register()

    response = harness.client.post("/contracts", headers=headers, data={"title": "t", "text": LLM_CONTRACT})
    contract_id = response.json()["id"]

    assert list(capture.points("analyses")) == [(("outcome", "done"),)]
    assert capture.points("findings.dropped") == {(("reason", "quote_not_found"),): 1}
    names = {s.name for s in capture.spans.get_finished_spans()}
    assert {"analysis.run", "analysis.pseudonymize", "analysis.chunk", "analysis.verify_quotes", "analysis.email"} <= names
    run = capture.span("analysis.run")
    assert run.parent is None and run.attributes["contract.id"] == contract_id
    verifying = capture.span("analysis.verify_quotes")
    assert verifying.attributes["findings.returned"] == 2 and verifying.attributes["findings.kept"] == 1
    analysis_spans = [s for s in capture.spans.get_finished_spans() if s.name.startswith("analysis.")]
    assert {s.context.trace_id for s in analysis_spans} == {run.context.trace_id}


def test_a_failed_analysis_is_counted_and_its_span_marked(capture):
    context = make_context(FailingAnalyzer())
    contract_id, run_id = start(context)

    run_analysis(context, contract_id, run_id)

    assert list(capture.points("analyses")) == [(("outcome", "failed"),)]
    span = capture.span("analysis.run")
    assert span.status.status_code == StatusCode.ERROR and span.status.description == "analysis_failed"


def test_a_stale_analysis_is_counted_when_the_rule_fires(capture, harness, auth_headers):
    harness.use_recording_runner()
    contract_id = harness.create_contract(auth_headers)["id"]
    harness.clock.advance(601)

    harness.client.get(f"/contracts/{contract_id}", headers=auth_headers)

    assert capture.points("analyses") == {(("outcome", "stale"),): 1}


def test_api_errors_are_counted_by_code(capture, harness, auth_headers):
    harness.client.get("/contracts/00000000-0000-0000-0000-000000000000", headers=auth_headers)

    assert capture.points("api.errors") == {(("code", "CONTRACT_NOT_FOUND"),): 1}


def test_no_contract_text_reaches_spans_metrics_or_logs(capture):
    quote = "[PARTY_A] may request unlimited revisions until fully satisfied."
    fake = FakeClient(lambda text: [
        finding(quote, explanation="zebra explanation: you may keep revising for free.",
                suggested_change="zebra suggestion: limit revisions to two rounds."),
        finding("A clause the contract does not contain: zebra hallucination.", category="scope_creep"),
    ], email={"subject": "zebra subject: Changes", "body": "Hi [PARTY_A],\n\n- zebra email body"})
    harness = Harness(analyzer=GroqAnalyzer(fake))
    headers = harness.register()

    response = harness.client.post(
        "/contracts", headers=headers, data={"title": "zebra title", "text": LLM_CONTRACT},
    )
    assert response.status_code == 202, response.text

    everything = capture.everything()
    assert "analysis.run" in everything and "Dropped a" in everything  # the capture saw the run and its drop logs
    must_not_appear = [
        *SECRETS, "unlimited revisions until fully satisfied", "Invoices are payable within 90 days",
        "zebra explanation", "zebra suggestion", "zebra hallucination", "zebra subject", "zebra email body",
        "zebra title", "limit revisions to two rounds", "PARTY_A",
    ]
    leaked = [text for text in must_not_appear if text in everything]
    assert leaked == []


def test_every_counter_series_starts_at_zero_so_the_first_event_is_an_increase(capture):
    from app.errors import ErrorCode

    telemetry.init_series("some-model")

    assert capture.points("analyses") == {(("outcome", o),): 0 for o in telemetry.ANALYSIS_OUTCOMES}
    assert capture.points("api.errors") == {(("code", str(code)),): 0 for code in ErrorCode}
    assert capture.points("findings.dropped") == {(("reason", r),): 0 for r in telemetry.DROP_REASONS}
    assert set(capture.points("llm.requests")) == {
        (("model", "some-model"), ("status", s)) for s in telemetry.LLM_STATUSES}
    assert capture.points("llm.output_truncated") == {
        (("model", "some-model"), ("retried", r)): 0 for r in ("true", "false")}
    assert capture.points("llm.rate_limited") == {(("model", "some-model"),): 0}

    telemetry.record_analysis("failed")
    assert capture.points("analyses")[(("outcome", "failed"),)] == 1


def test_a_stub_deployment_creates_no_llm_series(capture):
    telemetry.init_series("")

    assert capture.points("llm.requests") == {} and capture.points("llm.tokens") == {}
    assert capture.points("analyses")  # the analysis and error series still exist


def test_the_label_values_used_in_the_code_are_all_pre_created():
    import re
    from pathlib import Path

    import httpx

    from app.groq_client import _attempt_status

    statuses = {_attempt_status(r) for r in (
        None, httpx.Response(200), httpx.Response(429), httpx.Response(503), httpx.Response(404),
        httpx.Response(400, json={"error": {"code": "json_validate_failed", "message": "Failed to validate JSON"}}))}
    assert statuses <= set(telemetry.LLM_STATUSES)
    source = Path(__file__).parent.parent.joinpath("app", "groq_analyzer.py").read_text(encoding="utf-8")
    assert set(re.findall(r'record_finding_dropped\("(\w+)"\)', source)) == set(telemetry.DROP_REASONS)
    runner = Path(__file__).parent.parent.joinpath("app", "runner.py").read_text(encoding="utf-8")
    used = set(re.findall(r'return "(\w+)"', runner)) | {"done"}
    assert used <= set(telemetry.ANALYSIS_OUTCOMES)
