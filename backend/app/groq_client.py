"""Groq chat completions with strict structured output (docs/architecture.md, section 4).

One call = one request for a JSON object that matches a schema. The client spaces requests
with the shared token-bucket limiter, retries 429 and 5xx with exponential backoff
(honoring `retry-after`), and never logs the API key, the request or the response body:
they contain (pseudonymized) contract text. Logs carry only status, attempt, model,
token counts and timing.
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

from app.ratelimit import TokenBucketLimiter

logger = logging.getLogger(__name__)

API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_DELAY_SECONDS = 60.0
CHARS_PER_TOKEN = 4

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

    def __repr__(self) -> str:
        return f"GroqClient(model={self._model!r})"

    def complete_json(self, messages: list[dict[str, str]], schema_name: str, schema: dict[str, Any]) -> GroqResult:
        """One JSON object matching `schema`. Raises GroqError when retries run out, on a
        non-retryable status, or when the content is not a JSON object."""
        body = {
            "model": self._model,
            "messages": messages,
            "reasoning_effort": "low",
            "max_completion_tokens": self._max_completion_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        }
        estimate = _estimate_tokens(messages) + self._max_completion_tokens
        last = "no attempt"
        for attempt in range(1, self._max_attempts + 1):
            self._limiter.acquire(estimate)
            started = time.monotonic()
            response, last = self._post(body)
            if response is not None and response.status_code == 200:
                return self._parse(response, attempt, started)
            if response is not None and response.status_code not in RETRY_STATUSES:
                raise GroqError(f"Groq returned HTTP {response.status_code}: {_error_message(response)}")
            logger.warning("Groq %s attempt %d failed: %s", self._model, attempt, last)
            if attempt < self._max_attempts:
                self._sleep(self._delay(attempt, response))
        raise GroqError(f"Groq request failed after {self._max_attempts} attempts (last: {last})")

    def _post(self, body: dict[str, Any]) -> tuple[httpx.Response | None, str]:
        try:
            response = self._http.post(API_URL, json=body, headers=self._headers)
        except httpx.TransportError as error:
            return None, type(error).__name__
        return response, f"HTTP {response.status_code}"

    def _parse(self, response: httpx.Response, attempt: int, started: float) -> GroqResult:
        try:
            payload = response.json()
            content = json.loads(payload["choices"][0]["message"]["content"])
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise GroqError("Groq response is not a JSON object") from error
        if not isinstance(content, dict):
            raise GroqError("Groq response is not a JSON object")
        tokens = (payload.get("usage") or {}).get("total_tokens")
        elapsed_ms = round((time.monotonic() - started) * 1000)
        logger.info("Groq %s attempt %d: HTTP 200, %s tokens, %d ms", self._model, attempt, tokens, elapsed_ms)
        return GroqResult(content=content, total_tokens=tokens)

    def _delay(self, attempt: int, response: httpx.Response | None) -> float:
        retry_after = response.headers.get("retry-after") if response is not None else None
        try:
            delay = float(retry_after) if retry_after else self._base_delay * 2 ** (attempt - 1)
        except ValueError:
            delay = self._base_delay * 2 ** (attempt - 1)
        return min(max(delay, 0.0), MAX_DELAY_SECONDS)


def _estimate_tokens(messages: list[dict[str, str]]) -> int:
    return math.ceil(sum(len(m.get("content", "")) for m in messages) / CHARS_PER_TOKEN)


def _error_message(response: httpx.Response) -> str:
    """The provider's short error message only: the error body may also carry the failed
    generation (model output), which must not end up in logs or exceptions."""
    try:
        message = str(response.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return "no error message"
    return message[:200]
