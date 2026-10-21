"""Exceptions in telemetry: where they failed goes out, what they said does not.

An exception message can hold contract text (a title, a clause that a handler put into it), and
Grafana Cloud is a third party (docs/architecture.md, section 6). The on-call agent still needs the
type and the frames, so those are kept.
"""

import io
import json
import logging

import pytest
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app import telemetry

SECRET = "zebra clause: the Freelancer assigns all IP before payment"


def render_contract_title(title: str) -> None:
    """The kind of code that puts user text into an exception message."""
    raise ValueError(f"cannot render {title}")


def failing_call() -> None:
    render_contract_title(SECRET)


def formatted_traceback() -> str:
    import traceback

    try:
        failing_call()
    except ValueError:
        return traceback.format_exc()
    raise AssertionError("unreachable")


def test_the_frames_say_where_it_failed_and_not_what_it_said():
    frames = telemetry.exception_frames(formatted_traceback())

    assert "test_telemetry_exceptions.py" in frames
    assert "in render_contract_title" in frames and "in failing_call" in frames
    assert "zebra" not in frames and "ValueError" not in frames  # no message, no final `Type: message` line
    assert "raise ValueError" not in frames  # no source lines either
    assert all(" in " in line and ":" in line for line in frames.splitlines())


def test_only_the_newest_frames_are_kept():
    text = "".join(f'  File "/app/m{n}.py", line {n}, in f{n}\n    code\n' for n in range(30))
    frames = telemetry.exception_frames(text).splitlines()
    assert len(frames) == telemetry.MAX_EXCEPTION_FRAMES
    assert frames[-1] == "/app/m29.py:29 in f29"


def test_the_scrubbed_attributes_keep_the_type_and_drop_the_message():
    scrubbed = telemetry.scrubbed_exception_attributes({
        "exception.type": "ValueError", "exception.message": SECRET,
        "exception.stacktrace": formatted_traceback(), "exception.escaped": False,
    })
    assert scrubbed["exception.type"] == "ValueError"
    assert "exception.message" not in scrubbed
    assert scrubbed["exception.escaped"] is False
    assert "zebra" not in json.dumps(scrubbed)


def test_a_server_span_exports_the_type_and_frames_of_an_unhandled_exception():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(telemetry.ExceptionScrubber())  # as in setup_telemetry, before the exporter
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # The instrumentation relies on the default of start_as_current_span: record the exception it sees.
    with pytest.raises(ValueError):
        with provider.get_tracer("test").start_as_current_span("POST /contracts/{id}/export"):
            failing_call()

    (span,) = exporter.get_finished_spans()
    (event,) = [e for e in span.events if e.name == "exception"]
    assert event.attributes["exception.type"] == "ValueError"
    assert "exception.message" not in event.attributes
    assert "in render_contract_title" in event.attributes["exception.stacktrace"]
    assert span.status.description == "ValueError"  # the SDK writes `ValueError: <message>` by default
    assert "zebra" not in span.to_json()


def test_a_span_without_exceptions_is_left_alone():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(telemetry.ExceptionScrubber())
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with provider.get_tracer("test").start_as_current_span("ok") as span:
        span.add_event("checkpoint", {"rows": 3})
    (finished,) = exporter.get_finished_spans()
    assert [(e.name, dict(e.attributes)) for e in finished.events] == [("checkpoint", {"rows": 3})]


def test_the_exported_log_record_has_the_type_and_frames_but_the_stdout_log_keeps_the_traceback():
    exporter = InMemoryLogRecordExporter()
    provider = LoggerProvider()
    provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    stdout = io.StringIO()
    stdout_handler = logging.StreamHandler(stdout)
    stdout_handler.setFormatter(telemetry.JsonFormatter())
    logger = logging.getLogger("test.exceptions")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handlers = [stdout_handler, telemetry.ScrubbedLoggingHandler(level=logging.INFO, logger_provider=provider)]
    for handler in handlers:
        logger.addHandler(handler)
    try:
        try:
            failing_call()
        except ValueError:
            logger.exception("Unhandled error")
    finally:
        for handler in handlers:
            logger.removeHandler(handler)

    (record,) = exporter.get_finished_logs()
    attributes = record.log_record.attributes
    assert record.log_record.body == "Unhandled error"
    assert attributes["exception.type"] == "ValueError"
    assert "in render_contract_title" in attributes["exception.stacktrace"]
    assert "exception.message" not in attributes
    assert "zebra" not in f"{record.log_record.body} {dict(attributes)}"
    # The operator's own stdout log is not a third party: it still has the full traceback.
    assert "cannot render zebra clause" in json.loads(stdout.getvalue())["exception"]
