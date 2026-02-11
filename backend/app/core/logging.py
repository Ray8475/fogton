"""Structured JSON logging for API (vision: логгирование, мониторинг)."""
from __future__ import annotations

import json
import logging
import sys
import time
from uuid import uuid4


SERVICE = "api"


class JsonFormatter(logging.Formatter):
    """One JSON object per line: timestamp, level, service, event, message + extras."""

    def format(self, record: logging.LogRecord) -> str:
        log = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "service": SERVICE,
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }
        if getattr(record, "request_id", None):
            log["request_id"] = record.request_id
        if getattr(record, "telegram_user_id", None):
            log["telegram_user_id"] = record.telegram_user_id
        if getattr(record, "tx_hash", None):
            log["tx_hash"] = record.tx_hash
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        # any extra passed via logger.info(..., extra={...})
        for k, v in record.__dict__.items():
            if k not in (
                "name", "msg", "args", "created", "filename", "funcName", "levelname",
                "levelno", "lineno", "module", "msecs", "pathname", "process",
                "processName", "relativeCreated", "stack_info", "exc_info", "message",
                "taskName", "event", "request_id", "telegram_user_id", "tx_hash",
            ):
                if v is not None:
                    log[k] = v
        return json.dumps(log, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger for app: JSON to stdout."""
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(JsonFormatter())
        root.addHandler(h)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
