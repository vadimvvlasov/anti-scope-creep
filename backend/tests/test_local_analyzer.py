"""ANALYZER=local: settings, and a full analysis against a fake OpenAI-compatible server."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.analyzer import build_analyzer
from app.config import Settings
from app.groq_analyzer import GroqAnalyzer

CONTRACT = (
    "This Services Agreement sets out how the work is done and paid.\n\n"
    "Invoices are payable within 90 days of receipt.\n\n"
    "Either party may end this Agreement with 30 days written notice.\n"
)
QUOTE = "Invoices are payable within 90 days of receipt."
FINDING = {"category": "unfavorable_payment_terms", "risk_level": "high", "quoted_text": QUOTE,
           "explanation": "You wait three months for your money.",
           "suggested_change": "Invoices are payable within 30 days of receipt."}
EMAIL = {"subject": "Payment terms", "body": "Hi,\n- Could we move to 30-day payment terms?\nThanks"}


def _answer(content: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}


class _FakeLlamaServer(BaseHTTPRequestHandler):
    requests: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        schema = body["response_format"]["json_schema"]["name"]
        content = {"findings": [FINDING]} if schema == "contract_findings" else EMAIL
        payload = json.dumps(_answer(content)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:
        pass


@pytest.fixture
def fake_server() -> Iterator[str]:
    _FakeLlamaServer.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeLlamaServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
    server.shutdown()
    server.server_close()


def test_local_needs_a_url_at_startup():
    with pytest.raises(ValueError, match="LOCAL_API_URL"):
        Settings.from_env({"DATABASE_URL": "x", "ANALYZER": "local"})


def test_local_settings_defaults_and_overrides():
    env = {"DATABASE_URL": "x", "ANALYZER": "local", "LOCAL_API_URL": " http://llm:8080/v1/chat/completions "}
    settings = Settings.from_env(env)
    assert settings.analyzer == "local"
    assert settings.local_api_url == "http://llm:8080/v1/chat/completions"
    assert (settings.local_model, settings.local_timeout_seconds, settings.local_max_output_tokens) == (
        "bonsai-2-27b", 900.0, 16_000)
    custom = Settings.from_env({**env, "LOCAL_MODEL": "other", "LOCAL_TIMEOUT": "120", "LOCAL_MAX_OUTPUT_TOKENS": "8000"})
    assert (custom.local_model, custom.local_timeout_seconds, custom.local_max_output_tokens) == ("other", 120.0, 8000)


def test_local_key_is_not_in_repr():
    settings = Settings(jwt_secret="x", analyzer="local", local_api_url="http://llm", local_api_key="secret-key")
    assert "secret-key" not in repr(settings)


def test_local_analyzer_runs_a_full_analysis_on_the_fake_server(fake_server):
    analyzer = build_analyzer(Settings(jwt_secret="x", analyzer="local", local_api_url=fake_server))
    assert isinstance(analyzer, GroqAnalyzer)
    result = analyzer.analyze(CONTRACT)
    assert [(f.category.value, f.risk_level.value, f.quoted_text) for f in result.findings] == [
        ("unfavorable_payment_terms", "high", QUOTE)]
    assert result.email_draft is not None and result.email_draft.subject == "Payment terms"
    sent = _FakeLlamaServer.requests
    assert [r["body"]["response_format"]["json_schema"]["name"] for r in sent] == ["contract_findings", "client_email"]
    first = sent[0]
    assert first["path"] == "/v1/chat/completions"
    assert first["auth"] == "Bearer none"
    assert (first["body"]["model"], first["body"]["reasoning_effort"], first["body"]["max_completion_tokens"]) == (
        "bonsai-2-27b", "medium", 16_000)


def test_local_api_key_is_sent_when_set(fake_server):
    settings = Settings(jwt_secret="x", analyzer="local", local_api_url=fake_server, local_api_key="k")
    build_analyzer(settings).analyze(CONTRACT)
    assert {r["auth"] for r in _FakeLlamaServer.requests} == {"Bearer k"}


def test_local_client_fails_fast_instead_of_waiting_for_retries():
    settings = Settings(jwt_secret="x", analyzer="local", local_api_url="http://llm", local_timeout_seconds=600)
    client = build_analyzer(settings)._client
    assert client._retry_read_timeouts is False
    timeout = client._http.timeout
    assert (timeout.read, timeout.connect) == (600, 10.0)
