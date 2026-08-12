"""
backend/app/logger.py
─────────────────────
Shared JSON logger factory.
Every node calls get_logger(__name__) at the top of its logger.py.

Log format (always JSON, always to stdout):
{
    "time":    "2024-01-15T10:23:44.123Z",
    "node":    "ats_analyzer",
    "level":   "ERROR",
    "message": "Resume parse failed",
    "file":    "resume_parser.py",
    "line":    42,
    "error_code": "ATS_001",      ← from extra= kwarg
    "resume_id":  "abc-123"       ← from extra= kwarg
}

Usage in any node:
    from app.logger import get_logger
    logger = get_logger("ats_analyzer")
    logger.info("Scoring started", extra={"extra": {"resume_id": resume_id}})
    logger.error("Parse failed",   extra={"extra": {"error_code": "ATS_001", "file": filename}})
"""
import logging
import sys
import json
from datetime import datetime, timezone


class _JSONFormatter(logging.Formatter):
    """Formats every log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict = {
            "time":    datetime.now(timezone.utc).isoformat(),
            "node":    record.name,
            "level":   record.levelname,
            "message": record.getMessage(),
            "file":    record.filename,
            "line":    record.lineno,
        }

        # Merge any extra context the caller passed in
        # Usage: logger.info("msg", extra={"extra": {"key": "value"}})
        extra = getattr(record, "extra", None)
        if extra and isinstance(extra, dict):
            log_obj.update(extra)

        # Attach exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


def get_logger(node_name: str) -> logging.Logger:
    """
    Get a JSON-structured logger for a node.

    Args:
        node_name: The node identifier, e.g. "ats_analyzer", "data_adzuna".
                   This becomes the "node" field in every log line.

    Returns:
        A configured logger instance. Safe to call multiple times —
        handlers are only added once.
    """
    logger = logging.getLogger(node_name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False  # Don't bubble to root logger

    # Level from env via settings (lazy import to avoid circular)
    try:
        from app.config import settings
        level = getattr(logging, settings.log_level.upper(), logging.DEBUG)
    except Exception:
        level = logging.DEBUG

    logger.setLevel(level)
    return logger


# ── Convenience: app-wide logger ──────────────────────────────────
app_logger = get_logger("career_os")
