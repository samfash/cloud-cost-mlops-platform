"""Optional API key and rate-limit guards (disabled by default — no client impact)."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque

from flask import Flask, jsonify, request

# Endpoints that stay open for probes / browsers even when API_KEY is set.
_OPEN_ENDPOINTS = frozenset(
    {
        "health",
        "ready",
        "metrics",
        "home",
        "overview",
        "model_card",
        "static",
    }
)


def _configured_api_key() -> str | None:
    key = os.environ.get("API_KEY", "").strip()
    return key or None


def _rate_limit_per_minute() -> int:
    raw = os.environ.get("RATE_LIMIT_PER_MINUTE", "0").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


class _SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_s: float = 60.0) -> bool:
        if limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and (now - bucket[0]) > window_s:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


_LIMITER = _SlidingWindowLimiter()


def register_api_guards(app: Flask) -> None:
    """Attach optional API_KEY and RATE_LIMIT_PER_MINUTE enforcement."""

    @app.before_request
    def _guard():  # type: ignore[no-untyped-def]
        endpoint = request.endpoint or ""
        if endpoint in _OPEN_ENDPOINTS or request.method == "OPTIONS":
            return None

        api_key = _configured_api_key()
        if api_key is not None:
            presented = request.headers.get("X-API-Key", "").strip()
            if not presented:
                auth = request.headers.get("Authorization", "")
                if auth.lower().startswith("bearer "):
                    presented = auth[7:].strip()
            if presented != api_key:
                return jsonify({"error": "unauthorized"}), 401

        limit = _rate_limit_per_minute()
        if limit > 0:
            client = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
            client = client.split(",")[0].strip()
            bucket_key = f"{client}:{endpoint}"
            if not _LIMITER.allow(bucket_key, limit):
                return (
                    jsonify({"error": "rate limit exceeded", "limit_per_minute": limit}),
                    429,
                )
        return None
