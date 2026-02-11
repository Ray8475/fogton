from __future__ import annotations

"""Structured JSON logging for bot (vision: логгирование, мониторинг)."""

import json
import logging
import sys
import time


SERVICE = "bot"


class JsonFormatter(logging.Formatter):
    """One JSON object per line: timestamp, level, service, event, message + extras."""

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[name-defined]
        log = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "service": SERVICE,
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }
        if getattr(record, "telegram_user_id", None):
            log["telegram_user_id"] = record.telegram_user_id
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        # any extra passed via logger.info(..., extra={...})
        for k, v in record.__dict__.items():
            if k not in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "message",
                "event",
                "telegram_user_id",
                "taskName",
            ):
                if v is not None:
                    log[k] = v
        return json.dumps(log, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger for bot: JSON to stdout."""
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

