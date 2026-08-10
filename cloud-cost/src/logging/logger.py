#!/usr/bin/env python3
"""Structured logging configured for containers (stdout) and optional file sink."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line for aggregation-friendly ops."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "lineno": record.lineno,
        }
        for key in (
            "request_id",
            "path",
            "method",
            "status",
            "latency_ms",
            "model_version",
            "service",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _configure() -> None:
    root = logging.getLogger()
    if getattr(root, "_cloud_cost_configured", False):
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    root.setLevel(getattr(logging, level_name, logging.INFO))
    root.handlers.clear()

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(JsonFormatter())
    root.addHandler(stream)

    if os.getenv("LOG_TO_FILE", "0") in {"1", "true", "TRUE", "yes"}:
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(
            log_dir, f"{datetime.now(UTC).strftime('%m_%d_%Y_%H_%M_%S')}.log"
        )
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(JsonFormatter())
        root.addHandler(file_handler)

    root._cloud_cost_configured = True  # type: ignore[attr-defined]


_configure()
