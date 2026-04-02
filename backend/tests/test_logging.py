"""Tests for structured logging — JSON format, trace_id propagation."""

import json
import logging
import io

from backend.logging_config import JSONFormatter, TraceContext, setup_logging


class TestJSONFormatter:
    def test_basic_log_entry(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        entry = json.loads(output)

        assert entry["level"] == "INFO"
        assert entry["event"] == "Test message"
        assert entry["logger"] == "test"
        assert "timestamp" in entry
        assert "trace_id" in entry

    def test_trace_id_included(self):
        TraceContext.set("test-trace-123")
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Warning message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        entry = json.loads(output)

        assert entry["trace_id"] == "test-trace-123"
        TraceContext.clear()

    def test_error_exception_included(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Something failed",
                args=(),
                exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        entry = json.loads(output)

        assert "error" in entry
        assert "ValueError" in entry["error"]


class TestTraceContext:
    def test_set_and_get(self):
        TraceContext.set("trace-abc")
        assert TraceContext.get() == "trace-abc"
        TraceContext.clear()

    def test_clear(self):
        TraceContext.set("trace-abc")
        TraceContext.clear()
        assert TraceContext.get() is None

    def test_default_is_none(self):
        TraceContext.clear()
        assert TraceContext.get() is None
