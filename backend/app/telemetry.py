"""Telemetry: JSON logs with trace ids, and OpenTelemetry export (docs/architecture.md, section 6).

Logs are always JSON on stdout. Export is on only when OTEL_EXPORTER_OTLP_ENDPOINT is set; the
exporters read the endpoint and OTEL_EXPORTER_OTLP_HEADERS from the environment, so moving from
the local stack to Grafana Cloud changes only those two variables.

Nothing here records a request or response body, a prompt, a model answer or contract text:
only ids, sizes, counts, model names, token usage and error codes may go into a span, a metric
or a log record.
"""

import contextvars
import json
import logging
import sys
from collections.abc import Callable
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
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode, Tracer

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


def setup_telemetry(settings: Settings) -> Callable[[], None] | None:
    """Providers for traces, metrics and logs, plus the HTTPX instrumentation.

    Returns the function that flushes and stops the exporters (for the lifespan shutdown), or None
    when export is off.
    """
    if not settings.otel_endpoint:
        return None
    resource = Resource.create({"service.name": SERVICE_NAME, "service.version": settings.version})
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)
    meter_provider = MeterProvider(resource=resource, metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())])
    metrics.set_meter_provider(meter_provider)
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(logger_provider)
    log_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
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
