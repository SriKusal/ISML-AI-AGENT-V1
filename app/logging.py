"""Structured logging for ISML AI AGENT.

Provides two formatters:
- JSONFormatter  — machine-readable structured JSON (used in production / file)
- PlainFormatter — human-readable text (used in terminal during development)

Every log record includes:
- timestamp, level, logger name, message
- correlation_id  (from contextvars, set per HTTP request)
- duration_ms     (optional, set by timed helpers)
- phase           (optional, set by workflow nodes)
- extra fields    passed as keyword arguments to logger calls
"""

import json
import logging
import sys
import time
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Context variable — stores the current request correlation ID
# ---------------------------------------------------------------------------
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Emits one JSON object per log line for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get("-"),
        }

        # Optional structured fields attached via logger.info("...", extra={...})
        for field in ("duration_ms", "phase", "node", "provider", "topic",
                      "resources_count", "error_type"):
            if hasattr(record, field):
                log_obj[field] = getattr(record, field)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    """Human-readable formatter that includes correlation_id."""

    FORMAT = "%(asctime)s [%(correlation_id)s] %(name)s %(levelname)s - %(message)s"

    def format(self, record: logging.LogRecord) -> str:
        record.correlation_id = correlation_id_var.get("-")
        return super().format(record)


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Return a named logger with stdout (plain) and file (JSON) handlers.

    Safe to call multiple times for the same name — handlers are only
    added once.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level if level is not None else logging.INFO)

    if not logger.handlers:
        # Terminal — plain readable format
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(
            PlainFormatter(PlainFormatter.FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(stream_handler)

        # File — structured JSON for log analysis
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


# ---------------------------------------------------------------------------
# Timing helper
# ---------------------------------------------------------------------------

class NodeTimer:
    """Context manager that logs node execution time.

    Usage::

        with NodeTimer(logger, "evaluate_resources"):
            ... do work ...
    """

    def __init__(self, logger: logging.Logger, node_name: str) -> None:
        self._logger = logger
        self._node = node_name
        self._start: float = 0.0

    def __enter__(self) -> "NodeTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = round((time.perf_counter() - self._start) * 1000, 2)
        if exc_type:
            self._logger.warning(
                "Node '%s' failed after %.0fms",
                self._node, duration_ms,
                extra={"node": self._node, "duration_ms": duration_ms},
            )
        else:
            self._logger.info(
                "Node '%s' completed in %.0fms",
                self._node, duration_ms,
                extra={"node": self._node, "duration_ms": duration_ms},
            )
