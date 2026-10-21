"""Telemetry: JSON logs with trace ids, and OpenTelemetry export (docs/architecture.md, section 6).

Logs are always JSON on stdout. Export is on only when OTEL_EXPORTER_OTLP_ENDPOINT is set; the
exporters read the endpoint and OTEL_EXPORTER_OTLP_HEADERS from the environment, so moving from
the local stack to Grafana Cloud changes only those two variables.

Nothing here records a request or response body, a prompt, a model answer or contract text:
only ids, sizes, counts, model names, token usage and error codes may go into a span, a metric
or a log record.
"""

import contextvars
import copy
import json
import logging
import re
import sys
import traceback
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.engine import Engine
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.metrics import Counter, Histogram, Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, Status, StatusCode, Tracer

from app.config import Settings

SERVICE_NAME = "anti-scope-creep-backend"
# Probes and the version check would drown the traces.
UNTRACED_URLS = "/health,/health/ready,/version"

# The contract an analysis is working on; set by run_analysis, read by the log filter.
contract_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("contract_id", default=None)

_HANDLER_MARKER = "_asc_json_handler"


class ContractContextFilter(logging.Filter):
    """Adds `contract_id` to a record when an analysis is running in this context."""

    def filter(self, record: logging.LogRecord) -> bool:
        contract_id = contract_id_var.get()
        if contract_id and not hasattr(record, "contract_id"):
            record.contract_id = contract_id
        return True


_TRACEBACK_FRAME = re.compile(r'^\s+File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<function>.+)$')
MAX_EXCEPTION_FRAMES = 12


def exception_frames(stacktrace: str | None) -> str:
    """Where a formatted traceback failed, not what it said: one `file:line in function` per frame.

    The source lines and the final `Type: message` line are dropped: an exception message can hold
    contract text (a title, a clause) that a handler put into it.
    """
    frames = []
    for line in (stacktrace or "").splitlines():
        match = _TRACEBACK_FRAME.match(line)
        if match:
            frames.append(f"{match['file']}:{match['line']} in {match['function']}")
    return "\n".join(frames[-MAX_EXCEPTION_FRAMES:])


def scrubbed_exception_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    """The `exception.*` attributes of OpenTelemetry without `exception.message`; the stack trace is cut to frames."""
    attributes = attributes or {}
    scrubbed: dict[str, Any] = {
        "exception.type": attributes.get("exception.type", ""),
        "exception.stacktrace": exception_frames(attributes.get("exception.stacktrace")),
    }
    if "exception.escaped" in attributes:
        scrubbed["exception.escaped"] = attributes["exception.escaped"]
    return scrubbed


class ExceptionScrubber(SpanProcessor):
    """Runs before the exporter and rewrites the `exception` events that the instrumentation records.

    The server span of FastAPI records every unhandled exception with its message and traceback, which
    is how contract text could reach a third party. The spans of `span()` below already record only the
    type; this does the same for the rest, keeping the type and the frames (the on-call agent reads them).
    """

    def on_end(self, span: ReadableSpan) -> None:
        status = span.status
        if status.description and ": " in status.description:  # the SDK's default is `Type: message`
            span._status = Status(status.status_code, status.description.split(": ", 1)[0])  # noqa: SLF001
        events = getattr(span, "_events", None)  # what `span.events` hands to the exporters that follow
        if events and any(item.name == "exception" for item in events):
            span._events = [  # noqa: SLF001 - the SDK has no public way to change a finished span
                Event(item.name, scrubbed_exception_attributes(item.attributes), item.timestamp)
                if item.name == "exception" else item
                for item in events
            ]


class ScrubbedLoggingHandler(LoggingHandler):
    """The OpenTelemetry log handler without exception messages: type and frames go out, on a copy of
    the record, so the JSON log on stdout (the operator's own) keeps the whole traceback."""

    def emit(self, record: logging.LogRecord) -> None:
        if record.exc_info and record.exc_info[0] is not None:
            exception_type = record.exc_info[0].__name__
            frames = exception_frames("".join(traceback.format_exception(*record.exc_info)))
            record = copy.copy(record)
            record.exc_info = None
            record.exc_text = None
            setattr(record, "exception.type", exception_type)
            setattr(record, "exception.stacktrace", frames)
        super().emit(record)


class JsonFormatter(logging.Formatter):
    """One JSON object per line: time, level, logger, message, trace and span id, contract id, code."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            entry["trace_id"] = format(span_context.trace_id, "032x")
            entry["span_id"] = format(span_context.span_id, "016x")
        for key in ("contract_id", "code"):
            value = getattr(record, key, None)
            if value:
                entry[key] = str(value)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """JSON logs on stdout for the root logger and uvicorn's; safe to call again."""
    root = logging.getLogger()
    if not any(getattr(handler, _HANDLER_MARKER, False) for handler in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler.addFilter(ContractContextFilter())
        setattr(handler, _HANDLER_MARKER, True)
        root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)
    # uvicorn formats its own lines as text; send them through the root handler instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


@dataclass(frozen=True)
class Instruments:
    """The metrics of docs/architecture.md, section 6. Labels are ids, codes, model names and
    counts, never text from a contract."""

    analyses: Counter  # analyses_total{outcome=done|failed|stale|superseded}
    analysis_duration: Histogram  # analysis_duration_seconds{outcome}
    llm_requests: Counter  # llm_requests_total{model,status}
    llm_request_duration: Histogram  # llm_request_duration_seconds{model}
    llm_tokens: Counter  # llm_tokens_total{model,kind=input|output}
    llm_rate_limited: Counter  # llm_rate_limited_total{model}
    llm_output_truncated: Counter  # llm_output_truncated_total{model,retried}
    findings_dropped: Counter  # findings_dropped_total{reason}
    api_errors: Counter  # api_errors_total{code}


def build_instruments(meter: Meter) -> Instruments:
    return Instruments(
        analyses=meter.create_counter("analyses", description="Analysis runs by outcome"),
        analysis_duration=meter.create_histogram("analysis.duration", unit="s", description="Analysis run time"),
        llm_requests=meter.create_counter("llm.requests", description="LLM HTTP attempts by status"),
        llm_request_duration=meter.create_histogram("llm.request.duration", unit="s", description="One LLM HTTP attempt"),
        llm_tokens=meter.create_counter("llm.tokens", description="LLM tokens by kind"),
        llm_rate_limited=meter.create_counter("llm.rate_limited", description="LLM attempts answered 429"),
        llm_output_truncated=meter.create_counter(
            "llm.output_truncated", description="Answers cut at the output cap; retried=true when a retry follows"
        ),
        findings_dropped=meter.create_counter("findings.dropped", description="Findings dropped by verification"),
        api_errors=meter.create_counter("api.errors", description="API error responses by code"),
    )


# Instruments made before the providers exist are proxies and bind when the provider is set,
# so importing this module needs no setup. Tests replace `instruments` and `tracer`.
instruments = build_instruments(metrics.get_meter(SERVICE_NAME))


ANALYSIS_OUTCOMES = ("done", "failed", "stale", "superseded")
LLM_STATUSES = ("ok", "rate_limited", "server_error", "network_error", "invalid_json", "client_error")
DROP_REASONS = ("quote_not_found", "placeholder_not_restored", "invalid_finding", "invalid_after_restore")


def init_series(model: str = "") -> None:
    """Creates every counter series of our own with the value 0, at startup.

    A counter that first shows up with a value has no earlier sample, so Prometheus' `increase()` and
    `rate()` count the first events of a label set as nothing: `UNAUTHORIZED=3` read as an increase of
    0 in Grafana Cloud. With a 0 exported from the start, the first real event is an increase, which
    the alerts (docs/architecture.md, section 6) and the on-call agent's context depend on. `model` is
    the LLM model name, empty when the analyzer is the stub. setup_telemetry flushes right after this,
    so the zeros are exported before any event, not 60 seconds later.
    """
    from app.errors import ErrorCode  # errors.py imports this module

    for outcome in ANALYSIS_OUTCOMES:
        instruments.analyses.add(0, {"outcome": outcome})
    for code in ErrorCode:
        instruments.api_errors.add(0, {"code": str(code)})
    for reason in DROP_REASONS:
        instruments.findings_dropped.add(0, {"reason": reason})
    if model:
        for status in LLM_STATUSES:
            instruments.llm_requests.add(0, {"model": model, "status": status})
        for kind in ("input", "output"):
            instruments.llm_tokens.add(0, {"model": model, "kind": kind})
        for retried in ("true", "false"):
            instruments.llm_output_truncated.add(0, {"model": model, "retried": retried})
        instruments.llm_rate_limited.add(0, {"model": model})


def tracer() -> Tracer:
    return trace.get_tracer(SERVICE_NAME)


@contextmanager
def span(name: str, **attributes: str | int | bool) -> Iterator[Span]:
    """A span that, on an exception, records only the exception type: a message may hold contract text."""
    with tracer().start_as_current_span(
        name, attributes=attributes, record_exception=False, set_status_on_exception=False
    ) as current:
        try:
            yield current
        except Exception as error:
            current.set_status(Status(StatusCode.ERROR, type(error).__name__))
            raise


def fail_span(current: Span, reason: str) -> None:
    """Marks a span failed with a short reason code, for a failure that was handled and not raised."""
    current.set_status(Status(StatusCode.ERROR, reason))


def record_analysis(outcome: str, seconds: float | None = None, count: int = 1) -> None:
    instruments.analyses.add(count, {"outcome": outcome})
    if seconds is not None:
        instruments.analysis_duration.record(seconds, {"outcome": outcome})


def record_llm_attempt(model: str, status: str, seconds: float) -> None:
    instruments.llm_requests.add(1, {"model": model, "status": status})
    instruments.llm_request_duration.record(seconds, {"model": model})
    if status == "rate_limited":
        instruments.llm_rate_limited.add(1, {"model": model})


def record_llm_tokens(model: str, prompt: int | None, completion: int | None) -> None:
    if prompt:
        instruments.llm_tokens.add(prompt, {"model": model, "kind": "input"})
    if completion:
        instruments.llm_tokens.add(completion, {"model": model, "kind": "output"})


def record_output_truncated(model: str, retried: bool) -> None:
    instruments.llm_output_truncated.add(1, {"model": model, "retried": str(retried).lower()})


def record_finding_dropped(reason: str) -> None:
    instruments.findings_dropped.add(1, {"reason": reason})


def record_api_error(code: str) -> None:
    instruments.api_errors.add(1, {"code": code})


def setup_telemetry(settings: Settings) -> Callable[[], None] | None:
    """Providers for traces, metrics and logs, plus the HTTPX instrumentation.

    Returns the function that flushes and stops the exporters (for the lifespan shutdown), or None
    when export is off.
    """
    if not settings.otel_endpoint:
        return None
    resource = Resource.create({"service.name": SERVICE_NAME, "service.version": settings.version})
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(ExceptionScrubber())  # before the exporter, which reads the same events
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)
    meter_provider = MeterProvider(resource=resource, metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())])
    metrics.set_meter_provider(meter_provider)
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(logger_provider)
    init_series(settings.groq_model if settings.analyzer == "groq" else "")
    # The zeros must reach Prometheus before the first event: the reader exports only every 60 seconds,
    # and an event inside the first interval would arrive as the series' first sample (no increase).
    meter_provider.force_flush(timeout_millis=3_000)
    log_handler = ScrubbedLoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    log_handler.addFilter(ContractContextFilter())
    logging.getLogger().addHandler(log_handler)
    # No hooks that read bodies: HTTPX spans carry method, URL and status only.
    HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider, meter_provider=meter_provider)

    def shutdown() -> None:
        tracer_provider.shutdown()
        meter_provider.shutdown()
        logger_provider.shutdown()

    return shutdown


def instrument_engine(engine: Engine, tracer: Tracer | None = None) -> None:
    """One span per query (`db SELECT`, `db INSERT`, ...) with the dialect and the operation only.

    Not opentelemetry-instrumentation-sqlalchemy: it refuses sqlalchemy 2.1, and it records the SQL
    text. Here neither the statement nor its parameters reach a span, since rows can hold contract
    text and history-query results (docs/architecture.md, section 6).
    """
    tracer = tracer or trace.get_tracer(SERVICE_NAME)
    system = engine.dialect.name

    @event.listens_for(engine, "before_cursor_execute")
    def start_span(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        words = statement.split(None, 1)
        operation = words[0].upper() if words else "QUERY"
        context._asc_span = tracer.start_span(f"db {operation}", attributes={"db.system": system, "db.operation": operation})

    @event.listens_for(engine, "after_cursor_execute")
    def end_span(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        span = getattr(context, "_asc_span", None)
        if span:
            span.end()

    @event.listens_for(engine, "handle_error")
    def fail_span(exception_context):  # noqa: ANN001
        span = getattr(exception_context.execution_context, "_asc_span", None)
        if span:
            span.set_status(Status(StatusCode.ERROR, type(exception_context.original_exception).__name__))
            span.end()


def instrument_app(app: FastAPI) -> None:
    """Server spans and HTTP metrics for every route except the probes."""
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=trace.get_tracer_provider(),
        meter_provider=metrics.get_meter_provider(),
        excluded_urls=UNTRACED_URLS,
    )
