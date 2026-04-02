"""
JSON structured logging with trace_id propagation.
Every log line includes: trace_id, timestamp, level, event, context.
Stdout output — compatible with Docker/cloud log aggregation.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Optional


class TraceContext:
    """Thread-safe trace_id storage for the current execution context."""
    _trace_id: Optional[str] = None

    @classmethod
    def set(cls, trace_id: str) -> None:
        cls._trace_id = trace_id

    @classmethod
    def get(cls) -> Optional[str]:
        return cls._trace_id

    @classmethod
    def clear(cls) -> None:
        cls._trace_id = None


class JSONFormatter(logging.Formatter):
    """JSON log formatter with trace_id injection."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "trace_id": TraceContext.get(),
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["error"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_context"):
            log_entry["context"] = record.extra_context

        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure root logger with JSON formatter to stdout."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JSONFormatter())

    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance. Use module-level: logger = get_logger(__name__)"""
    return logging.getLogger(name)
