"""JSON logs and the telemetry switch (docs/architecture.md, section 6)."""

import io
import json
import logging

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.runner import run_analysis
from app.telemetry import (
    _HANDLER_MARKER,
    ContractContextFilter,
    JsonFormatter,
    configure_logging,
    contract_id_var,
    instrument_engine,
    setup_telemetry,
)
from tests.fakes import FailingAnalyzer
from tests.test_runner import make_context, start


def record(message: str = "hello", **extra: str) -> logging.LogRecord:
    log_record = logging.LogRecord("app.test", logging.INFO, __file__, 1, message, None, None)
    for key, value in extra.items():
        setattr(log_record, key, value)
    return log_record


def test_a_line_inside_a_span_carries_its_trace_and_span_id():
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("work") as span:
        line = json.loads(JsonFormatter().format(record()))
        context = span.get_span_context()

    assert line["trace_id"] == format(context.trace_id, "032x")
    assert line["span_id"] == format(context.span_id, "016x")
    assert line["message"] == "hello" and line["level"] == "INFO" and line["logger"] == "app.test"


def test_a_line_outside_a_span_has_no_trace_id():
    line = json.loads(JsonFormatter().format(record()))

    assert "trace_id" not in line and "span_id" not in line


def test_contract_id_and_code_are_fields_and_non_ascii_text_is_kept():
    line = JsonFormatter().format(record("Договор готов", contract_id="c-1", code="analysis_failed"))

    assert json.loads(line) | {"ts": ""} == {
        "ts": "", "level": "INFO", "logger": "app.test", "message": "Договор готов",
        "contract_id": "c-1", "code": "analysis_failed",
    }
    assert "\n" not in line


def test_an_exception_goes_into_the_same_json_line():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        log_record = logging.LogRecord("app.test", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())

    line = json.loads(JsonFormatter().format(log_record))

    assert "ValueError: boom" in line["exception"]


def test_a_failed_analysis_logs_its_contract_id_and_code_and_clears_the_context():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ContractContextFilter())
    runner_logger = logging.getLogger("app.runner")
    runner_logger.addHandler(handler)
    try:
        context = make_context(FailingAnalyzer())
        contract_id, run_id = start(context)
        run_analysis(context, contract_id, run_id)
    finally:
        runner_logger.removeHandler(handler)

    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    failed = next(line for line in lines if line["message"].startswith("Analysis failed"))
    assert failed["contract_id"] == str(contract_id)
    assert failed["code"] == "analysis_failed"
    assert contract_id_var.get() is None


def test_configure_logging_installs_one_json_handler_however_often_it_runs():
    configure_logging()
    configure_logging()

    ours = [h for h in logging.getLogger().handlers if getattr(h, _HANDLER_MARKER, False)]
    assert len(ours) == 1
    assert isinstance(ours[0].formatter, JsonFormatter)


def test_export_stays_off_without_an_endpoint():
    assert setup_telemetry(Settings(jwt_secret="x")) is None
    assert Settings.from_env({"JWT_SECRET": "x" * 40, "DATABASE_URL": "sqlite://"}).otel_endpoint == ""
    on = Settings.from_env({"JWT_SECRET": "x" * 40, "DATABASE_URL": "sqlite://",
                            "OTEL_EXPORTER_OTLP_ENDPOINT": " http://lgtm:4318 "})
    assert on.otel_endpoint == "http://lgtm:4318"


def traced_engine():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    engine = create_engine("sqlite://")
    instrument_engine(engine, provider.get_tracer("test"))
    return engine, exporter


def test_a_query_gets_a_span_without_its_text_or_parameters():
    engine, exporter = traced_engine()
    with engine.connect() as connection:
        connection.execute(text("SELECT :clause"), {"clause": "ZEBRA-CONTRACT-TEXT"})

    (span,) = exporter.get_finished_spans()
    assert span.name == "db SELECT"
    assert span.attributes == {"db.system": "sqlite", "db.operation": "SELECT"}
    assert "ZEBRA" not in json.dumps(dict(span.attributes))


def test_a_failing_query_ends_its_span_with_an_error_status():
    engine, exporter = traced_engine()
    with pytest.raises(OperationalError), engine.connect() as connection:
        connection.execute(text("SELECT * FROM no_such_table"))

    (span,) = exporter.get_finished_spans()
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "OperationalError"
