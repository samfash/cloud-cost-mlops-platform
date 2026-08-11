"""SQLite audit log for predictions (indexed) — local stand-in for Mongo/event store."""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


def audit_enabled() -> bool:
    return os.environ.get("AUDIT_LOG_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }


class PredictAuditLog:
    def __init__(self, path: Path | None = None) -> None:
        default = Path(__file__).resolve().parents[1] / "artifacts" / "ops" / "predict_audit.db"
        raw = os.environ.get("AUDIT_LOG_PATH", "").strip()
        self.path = Path(raw) if raw else default
        self._lock = threading.Lock()
        self._ready = False

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def ensure_schema(self) -> None:
        if self._ready or not audit_enabled():
            return
        with self._lock:
            if self._ready:
                return
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS predict_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at REAL NOT NULL,
                        request_id TEXT,
                        endpoint TEXT NOT NULL,
                        model_version TEXT,
                        variant TEXT,
                        prediction REAL,
                        predicted_latency_ms REAL,
                        cache_hit INTEGER,
                        latency_ms REAL,
                        status TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_predict_events_request_id
                        ON predict_events(request_id);
                    CREATE INDEX IF NOT EXISTS idx_predict_events_created_at
                        ON predict_events(created_at);
                    CREATE INDEX IF NOT EXISTS idx_predict_events_status
                        ON predict_events(status);
                    """
                )
                conn.commit()
                self._ready = True
            finally:
                conn.close()

    def write(self, event: dict[str, Any]) -> None:
        if not audit_enabled():
            return
        self.ensure_schema()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO predict_events (
                        created_at, request_id, endpoint, model_version, variant,
                        prediction, predicted_latency_ms, cache_hit, latency_ms, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        float(event.get("created_at", time.time())),
                        event.get("request_id"),
                        event.get("endpoint", "unknown"),
                        event.get("model_version"),
                        event.get("variant"),
                        event.get("prediction"),
                        event.get("predicted_latency_ms"),
                        1 if event.get("cache_hit") else 0,
                        event.get("latency_ms"),
                        event.get("status", "success"),
                    ),
                )
                conn.commit()
            finally:
                conn.close()


AUDIT_LOG = PredictAuditLog()
