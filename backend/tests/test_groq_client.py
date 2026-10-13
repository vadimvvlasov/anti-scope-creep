"""GroqClient against a scripted transport: no network, no real key."""

import json
import logging

import httpx
import pytest
from pydantic import BaseModel, Field

from app.analyzer import AnalysisResult, FindingDraft
from app.groq_client import API_URL, GroqClient, GroqError, strict_json_schema
from app.ratelimit import TokenBucketLimiter

KEY = "gsk_test_key_never_logged"
CONTRACT = "The Contractor [PARTY_B] shall be liable without limitation."
SCHEMA = {
    "type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False,
}
MESSAGES = [{"role": "system", "content": "Find risks."}, {"role": "user", "content": CONTRACT}]


def ok(content: object = None, tokens: int = 150) -> httpx.Response:
    body = json.dumps({"text": "hi"} if content is None else content)
    return httpx.Response(200, json={"choices": [{"message": {"content": body}}], "usage": {"total_tokens": tokens}})


class Script:
    """Returns the scripted responses in order and records the requests."""

    def __init__(self, *responses: httpx.Response | Exception):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class RecordingLimiter(TokenBucketLimiter):
    def __init__(self) -> None:
        super().__init__(8_000, 30)
        self.acquired: list[int] = []

    def acquire(self, tokens: int) -> float:
        self.acquired.append(tokens)
        return 0.0


def client(script: Script, sleeps: list[float] | None = None, **kwargs) -> tuple[GroqClient, RecordingLimiter]:
    limiter = RecordingLimiter()
    groq = GroqClient(
        KEY, limiter, http=httpx.Client(transport=httpx.MockTransport(script)),
        sleep=(sleeps.append if sleeps is not None else lambda s: None), **kwargs,
    )
    return groq, limiter


def test_a_request_asks_for_strict_json_with_low_reasoning():
    script = Script(ok())
    groq, limiter = client(script)

    result = groq.complete_json(MESSAGES, "hi", SCHEMA)

    assert result.content == {"text": "hi"} and result.total_tokens == 150
    request = script.requests[0]
    assert str(request.url) == API_URL
    assert request.headers["Authorization"] == f"Bearer {KEY}"
    body = json.loads(request.content)
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["reasoning_effort"] == "low"
    assert body["response_format"] == {
        "type": "json_schema", "json_schema": {"name": "hi", "strict": True, "schema": SCHEMA},
    }
    assert limiter.acquired == [len("Find risks." + CONTRACT) // 4 + 1 + 2_000]


def test_api_url_sends_the_same_request_to_another_endpoint():
    script = Script(ok())
    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    groq, _ = client(script, api_url=url, model="gemini-3.5-flash-lite")

    groq.complete_json(MESSAGES, "hi", SCHEMA)

    request = script.requests[0]
    assert str(request.url) == url and json.loads(request.content)["model"] == "gemini-3.5-flash-lite"


def test_temperature_is_sent_only_when_set():
    default, zero = Script(ok()), Script(ok())
    client(default)[0].complete_json(MESSAGES, "hi", SCHEMA)
    client(zero, temperature=0.0)[0].complete_json(MESSAGES, "hi", SCHEMA)

    assert "temperature" not in json.loads(default.requests[0].content)
    assert json.loads(zero.requests[0].content)["temperature"] == 0.0


def test_reasoning_effort_is_low_unless_set():
    default, medium = Script(ok()), Script(ok())
    client(default)[0].complete_json(MESSAGES, "hi", SCHEMA)
    client(medium, reasoning_effort="medium")[0].complete_json(MESSAGES, "hi", SCHEMA)

    assert json.loads(default.requests[0].content)["reasoning_effort"] == "low"
    assert json.loads(medium.requests[0].content)["reasoning_effort"] == "medium"


def test_an_error_wrapped_in_a_list_keeps_its_message():
    error = [{"error": {"code": 400, "message": "User location is not supported for the API use."}}]
    groq, _ = client(Script(httpx.Response(400, json=error)))

    with pytest.raises(GroqError, match="User location is not supported"):
        groq.complete_json(MESSAGES, "hi", SCHEMA)


def test_429_waits_for_retry_after_then_succeeds():
    script = Script(httpx.Response(429, headers={"retry-after": "7"}), ok())
    sleeps: list[float] = []
    groq, limiter = client(script, sleeps)

    assert groq.complete_json(MESSAGES, "hi", SCHEMA).content == {"text": "hi"}
    assert sleeps == [7.0]
    assert len(limiter.acquired) == 2  # every attempt goes through the limiter


def test_5xx_and_network_errors_back_off_exponentially():
    script = Script(httpx.Response(503), httpx.ConnectError("down"), httpx.Response(502), ok())
    sleeps: list[float] = []
    groq, _ = client(script, sleeps)

    groq.complete_json(MESSAGES, "hi", SCHEMA)
    assert sleeps == [2.0, 4.0, 8.0]


def test_retries_run_out_after_five_attempts():
    script = Script(*[httpx.Response(429) for _ in range(5)])
    sleeps: list[float] = []
    groq, _ = client(script, sleeps)

    with pytest.raises(GroqError, match="after 5 attempts .*HTTP 429"):
        groq.complete_json(MESSAGES, "hi", SCHEMA)
    assert len(script.requests) == 5 and len(sleeps) == 4
    assert max(sleeps) <= 60


def test_a_schema_error_fails_at_once_without_the_failed_generation():
    error = {"error": {"message": "Generated JSON does not match the expected schema.",
                       "failed_generation": CONTRACT}}
    script = Script(httpx.Response(400, json=error))
    groq, _ = client(script)

    with pytest.raises(GroqError) as raised:
        groq.complete_json(MESSAGES, "hi", SCHEMA)
    assert "does not match the expected schema" in str(raised.value)
    assert CONTRACT not in str(raised.value)
    assert len(script.requests) == 1


def test_a_rejected_key_is_not_retried():
    script = Script(httpx.Response(401, json={"error": {"message": "Invalid API Key"}}))
    groq, _ = client(script)
    with pytest.raises(GroqError, match="HTTP 401"):
        groq.complete_json(MESSAGES, "hi", SCHEMA)
    assert len(script.requests) == 1


@pytest.mark.parametrize("content", ["not json", "[1, 2]"])
def test_content_that_is_not_a_json_object_fails(content):
    response = httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    groq, _ = client(Script(response))
    with pytest.raises(GroqError, match="not a JSON object"):
        groq.complete_json(MESSAGES, "hi", SCHEMA)


def cut(partial: str = '{"findings": [{"category": "scope') -> httpx.Response:
    """An answer stopped at the output cap: unfinished JSON, finish_reason "length"."""
    return httpx.Response(200, json={"choices": [{"message": {"content": partial}, "finish_reason": "length"}],
                                     "usage": {"total_tokens": 2_500, "completion_tokens": 2_000}})


def test_a_result_reports_output_tokens_and_finish_reason():
    response = httpx.Response(200, json={"choices": [{"message": {"content": '{"text": "hi"}'}, "finish_reason": "stop"}],
                                         "usage": {"total_tokens": 900, "completion_tokens": 300}})
    groq, _ = client(Script(response))

    result = groq.complete_json(MESSAGES, "hi", SCHEMA)

    assert (result.completion_tokens, result.finish_reason, result.max_completion_tokens) == (300, "stop", 2_000)


def test_a_cut_answer_is_asked_again_with_twice_the_budget():
    script = Script(cut(), ok())
    groq, limiter = client(script)

    result = groq.complete_json(MESSAGES, "hi", SCHEMA)

    assert result.content == {"text": "hi"} and result.max_completion_tokens == 4_000
    assert [json.loads(r.content)["max_completion_tokens"] for r in script.requests] == [2_000, 4_000]
    assert limiter.acquired[1] - limiter.acquired[0] == 2_000  # the limiter reserves the bigger budget


def test_a_second_cut_fails_and_the_partial_answer_is_never_parsed():
    groq, _ = client(Script(cut(), cut()))
    with pytest.raises(GroqError, match="cut at max_completion_tokens=4000"):
        groq.complete_json(MESSAGES, "hi", SCHEMA)


def test_a_budget_already_at_the_retry_cap_is_not_retried():
    script = Script(cut())
    groq, _ = client(script, max_completion_tokens=8_000)
    with pytest.raises(GroqError, match="cut at max_completion_tokens=8000"):
        groq.complete_json(MESSAGES, "hi", SCHEMA)
    assert len(script.requests) == 1


def test_logs_carry_no_key_and_no_contract_text(caplog):
    caplog.set_level(logging.DEBUG)
    groq, _ = client(Script(httpx.Response(429, headers={"retry-after": "1"}), ok()))
    groq.complete_json(MESSAGES, "hi", SCHEMA)

    assert "attempt 1 failed: HTTP 429" in caplog.text and "HTTP 200, 150 tokens" in caplog.text
    assert KEY not in caplog.text and CONTRACT not in caplog.text
    assert KEY not in repr(groq)


def test_a_missing_key_is_a_configuration_error():
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        GroqClient("", RecordingLimiter())


class Inner(BaseModel):
    note: str | None = Field(default=None, max_length=10)


class Outer(BaseModel):
    title: str = Field(min_length=1)
    items: list[Inner]


def test_strict_schema_inlines_references_and_requires_every_property():
    schema = strict_json_schema(Outer)

    assert "$defs" not in json.dumps(schema) and "$ref" not in json.dumps(schema)
    assert schema["required"] == ["title", "items"] and schema["additionalProperties"] is False
    assert "title" in schema["properties"]  # a property named like a keyword is kept
    inner = schema["properties"]["items"]["items"]
    assert inner["required"] == ["note"] and inner["additionalProperties"] is False
    assert inner["properties"]["note"] == {"anyOf": [{"type": "string"}, {"type": "null"}]}
    assert "minLength" not in json.dumps(schema) and "maxLength" not in json.dumps(schema)


def test_strict_schema_of_the_analysis_result_keeps_the_six_categories():
    schema = strict_json_schema(AnalysisResult)
    finding = schema["properties"]["findings"]["items"]
    assert set(finding["required"]) == set(FindingDraft.model_fields)
    assert len(finding["properties"]["category"]["enum"]) == 6
