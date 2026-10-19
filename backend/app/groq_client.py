"""Groq chat completions with strict structured output (docs/architecture.md, section 4).

One call = one request for a JSON object that matches a schema. The client spaces requests
with the shared token-bucket limiter, retries 429 and 5xx with exponential backoff
(honoring `retry-after`), and never logs the API key, the request or the response body:
they contain (pseudonymized) contract text. Logs carry only status, attempt, model,
token counts and timing. `api_url` points the same request at another OpenAI-compatible
endpoint; the eval uses it for Gemini (evaluation/__main__.py).

`max_completion_tokens` caps the output, reasoning included. An answer cut at that cap
(`finish_reason: "length"`) is not valid JSON, so it is asked again once with twice the
budget, up to MAX_RETRY_COMPLETION_TOKENS; a second cut fails the call. A truncated
answer is never parsed, so the cap cannot silently drop findings.

A `400` "Failed to validate JSON" (`json_validate_failed`) means this one generation broke
the schema, so it is asked again once; a second one fails the call. Every other `400`
(for example a schema outside the strict subset) fails at once: asking again cannot fix it.
"""

import json
import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel

from app import telemetry
from app.ratelimit import TokenBucketLimiter

logger = logging.getLogger(__name__)

API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_DELAY_SECONDS = 60.0
CHARS_PER_TOKEN = 4
MAX_RETRY_COMPLETION_TOKENS = 4_000
TRUNCATED = "length"
INVALID_JSON_CODE = "json_validate_failed"
INVALID_JSON_MESSAGE = "Failed to validate JSON"

# Strict mode accepts a subset of JSON Schema; length limits are validated by Pydantic afterwards.
_UNSUPPORTED_KEYWORDS = frozenset(
    {"title", "default", "examples", "format", "pattern", "minLength", "maxLength", "minItems", "maxItems"}
)


class GroqError(Exception):
    """The provider did not return a valid JSON object; the analysis fails."""


@dataclass(frozen=True)
class GroqResult:
    content: dict[str, Any]
    total_tokens: int | None
    completion_tokens: int | None = None
    finish_reason: str | None = None
    max_completion_tokens: int | None = None  # the output budget of the request that answered
    prompt_tokens: int | None = None  # Gemini: total - prompt - completion = thinking tokens


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """The model's JSON schema in the form strict mode needs: references inlined, every
    property required, no additional properties, no unsupported keywords."""
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})
    return _strict(schema, definitions)


def _strict(node: Any, definitions: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_strict(item, definitions) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        return _strict(definitions[node["$ref"].rsplit("/", 1)[-1]], definitions)
    result = {}
    for key, value in node.items():
        if key == "properties":
            result[key] = {name: _strict(prop, definitions) for name, prop in value.items()}
        elif key not in _UNSUPPORTED_KEYWORDS:
            result[key] = _strict(value, definitions)
    if result.get("type") == "object":
        result["required"] = list(result.get("properties", {}))
        result["additionalProperties"] = False
    return result


class GroqClient:
    def __init__(
        self,
        api_key: str,
        limiter: TokenBucketLimiter,
        model: str = DEFAULT_MODEL,
        *,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 5,
        base_delay: float = 2.0,
        max_completion_tokens: int = 2_000,
        api_url: str = API_URL,
        temperature: float | None = None,
        reasoning_effort: str = "low",
    ):
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._limiter = limiter
        self._model = model
        self._http = http or httpx.Client(timeout=60.0)
        self._sleep = sleep
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._max_completion_tokens = max_completion_tokens
        self._api_url = api_url
        self._temperature = temperature
        self._reasoning_effort = reasoning_effort

    def __repr__(self) -> str:
        return f"GroqClient(model={self._model!r})"

    def complete_json(self, messages: list[dict[str, str]], schema_name: str, schema: dict[str, Any]) -> GroqResult:
        """One JSON object matching `schema`. Raises GroqError when retries run out, on a
        non-retryable status, when the content is not a JSON object, or when the output is
        cut at the token cap twice."""
        with telemetry.span("llm.complete_json", **{"llm.model": self._model, "llm.schema": schema_name}) as current:
            result = self._complete(messages, schema_name, schema)
            current.set_attribute("llm.finish_reason", str(result.finish_reason))
            if result.prompt_tokens is not None:
                current.set_attribute("llm.prompt_tokens", result.prompt_tokens)
            if result.completion_tokens is not None:
                current.set_attribute("llm.completion_tokens", result.completion_tokens)
            return result

    def _complete(self, messages: list[dict[str, str]], schema_name: str, schema: dict[str, Any]) -> GroqResult:
        budget = self._max_completion_tokens
        result = self._request(messages, schema_name, schema, budget)
        if result.finish_reason != TRUNCATED:
            return result
        retry_budget = max(budget, min(budget * 2, MAX_RETRY_COMPLETION_TOKENS))
        if retry_budget == budget:
            telemetry.record_output_truncated(self._model, retried=False)
            raise GroqError(f"Groq output was cut at max_completion_tokens={budget}")
        telemetry.record_output_truncated(self._model, retried=True)  # a retry follows
        logger.warning("Groq %s output was cut at max_completion_tokens=%d; retrying with %d",
                       self._model, budget, retry_budget)
        result = self._request(messages, schema_name, schema, retry_budget)
        if result.finish_reason == TRUNCATED:
            telemetry.record_output_truncated(self._model, retried=False)  # failed after its retry
            raise GroqError(f"Groq output was cut at max_completion_tokens={retry_budget}")
        return result

    def _request(self, messages: list[dict[str, str]], schema_name: str, schema: dict[str, Any],
                 budget: int) -> GroqResult:
        """One request with retries on 429, 5xx and network errors, and one more try after
        a generation that failed JSON validation."""
        body = {
            "model": self._model,
            "messages": messages,
            "reasoning_effort": self._reasoning_effort,
            "max_completion_tokens": budget,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        }
        if self._temperature is not None:  # otherwise the provider's default applies
            body["temperature"] = self._temperature
        estimate = _estimate_tokens(messages) + budget
        last = "no attempt"
        invalid_json_retried = False
        for attempt in range(1, self._max_attempts + 1):
            self._limiter.acquire(estimate)
            started = time.monotonic()
            response, last = self._post(body)
            telemetry.record_llm_attempt(self._model, _attempt_status(response), time.monotonic() - started)
            if response is not None and response.status_code == 200:
                return self._parse(response, attempt, started, budget)
            if response is not None and not invalid_json_retried and _is_invalid_json(response):
                invalid_json_retried = True
                logger.warning("Groq %s attempt %d: generated JSON failed validation; asking again once",
                               self._model, attempt)
                continue
            if response is not None and response.status_code not in RETRY_STATUSES:
                raise GroqError(f"Groq returned HTTP {response.status_code}: {_error_message(response)}")
            logger.warning("Groq %s attempt %d failed: %s", self._model, attempt, last)
            if attempt < self._max_attempts:
                self._sleep(self._delay(attempt, response))
        raise GroqError(f"Groq request failed after {self._max_attempts} attempts (last: {last})")

    def _post(self, body: dict[str, Any]) -> tuple[httpx.Response | None, str]:
        try:
            response = self._http.post(self._api_url, json=body, headers=self._headers)
        except httpx.TransportError as error:
            return None, type(error).__name__
        return response, f"HTTP {response.status_code}"

    def _parse(self, response: httpx.Response, attempt: int, started: float, budget: int) -> GroqResult:
        """The JSON object of a 200 response; a cut answer comes back empty with its finish
        reason instead of being parsed."""
        try:
            payload = response.json()
            choice = payload["choices"][0]
            finish_reason = choice.get("finish_reason")
            content = {} if finish_reason == TRUNCATED else json.loads(choice["message"]["content"])
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
            raise GroqError("Groq response is not a JSON object") from error
        if not isinstance(content, dict):
            raise GroqError("Groq response is not a JSON object")
        usage = payload.get("usage") or {}
        tokens, completion = usage.get("total_tokens"), usage.get("completion_tokens")
        elapsed_ms = round((time.monotonic() - started) * 1000)
        logger.info("Groq %s attempt %d: HTTP 200, %s tokens (%s output of %d), finish %s, %d ms",
                    self._model, attempt, tokens, completion, budget, finish_reason, elapsed_ms)
        telemetry.record_llm_tokens(self._model, usage.get("prompt_tokens"), completion)
        return GroqResult(content=content, total_tokens=tokens, completion_tokens=completion,
                          finish_reason=finish_reason, max_completion_tokens=budget,
                          prompt_tokens=usage.get("prompt_tokens"))

    def _delay(self, attempt: int, response: httpx.Response | None) -> float:
        retry_after = response.headers.get("retry-after") if response is not None else None
        try:
            delay = float(retry_after) if retry_after else self._base_delay * 2 ** (attempt - 1)
        except ValueError:
            delay = self._base_delay * 2 ** (attempt - 1)
        return min(max(delay, 0.0), MAX_DELAY_SECONDS)


def _attempt_status(response: httpx.Response | None) -> str:
    """The `status` label of one HTTP attempt: a small closed set, never a message."""
    if response is None:
        return "network_error"
    code = response.status_code
    if code == 200:
        return "ok"
    if code == 429:
        return "rate_limited"
    if code >= 500:
        return "server_error"
    return "invalid_json" if _is_invalid_json(response) else "client_error"


def _estimate_tokens(messages: list[dict[str, str]]) -> int:
    return math.ceil(sum(len(m.get("content", "")) for m in messages) / CHARS_PER_TOKEN)


def _is_invalid_json(response: httpx.Response) -> bool:
    """A 400 for one generation that broke the schema, recognized by the error code or,
    if the code is missing, by the start of the message."""
    if response.status_code != 400:
        return False
    try:
        payload = response.json()
        if isinstance(payload, list) and payload:
            payload = payload[0]
        error = payload["error"]
        return (error.get("code") == INVALID_JSON_CODE
                or str(error.get("message", "")).startswith(INVALID_JSON_MESSAGE))
    except (ValueError, KeyError, TypeError, AttributeError):
        return False


def _error_message(response: httpx.Response) -> str:
    """The provider's short error message only: the error body may also carry the failed
    generation (model output), which must not end up in logs or exceptions. Gemini wraps
    the error object in a one-element list."""
    try:
        payload = response.json()
        if isinstance(payload, list) and payload:
            payload = payload[0]
        message = str(payload["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return "no error message"
    return message[:200]
