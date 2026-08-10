"""In-process LRU/TTL cache for identical prediction payloads."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import OrderedDict
from threading import Lock
from typing import Any

from prometheus_client import Counter, Gauge

CACHE_HITS = Counter(
    "predict_cache_hits_total",
    "Prediction cache hits",
    ["service"],
)
CACHE_MISSES = Counter(
    "predict_cache_misses_total",
    "Prediction cache misses",
    ["service"],
)
CACHE_SIZE = Gauge(
    "predict_cache_entries",
    "Current prediction cache entries",
    ["service"],
)

SERVICE = "cloud-cost-api"


def _cache_enabled() -> bool:
    return os.environ.get("PREDICT_CACHE_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }


def _max_entries() -> int:
    try:
        return max(0, int(os.environ.get("PREDICT_CACHE_SIZE", "1024")))
    except ValueError:
        return 1024


def _ttl_seconds() -> float:
    try:
        return max(0.0, float(os.environ.get("PREDICT_CACHE_TTL_SECONDS", "300")))
    except ValueError:
        return 300.0


def cache_key(payload: dict[str, Any], model_version: str | None) -> str:
    """Stable key from canonical JSON + model version."""
    normalized = {str(k): payload[k] for k in sorted(payload)}
    blob = json.dumps(
        {"v": model_version or "", "p": normalized},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class PredictCache:
    def __init__(self) -> None:
        self._store: OrderedDict[str, tuple[float, float]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> float | None:
        if not _cache_enabled() or _max_entries() <= 0:
            return None
        ttl = _ttl_seconds()
        now = time.monotonic()
        with self._lock:
            item = self._store.get(key)
            if item is None:
                CACHE_MISSES.labels(service=SERVICE).inc()
                return None
            stored_at, value = item
            if ttl > 0 and (now - stored_at) > ttl:
                del self._store[key]
                CACHE_SIZE.labels(service=SERVICE).set(len(self._store))
                CACHE_MISSES.labels(service=SERVICE).inc()
                return None
            self._store.move_to_end(key)
            CACHE_HITS.labels(service=SERVICE).inc()
            return value

    def put(self, key: str, value: float) -> None:
        if not _cache_enabled() or _max_entries() <= 0:
            return
        with self._lock:
            self._store[key] = (time.monotonic(), value)
            self._store.move_to_end(key)
            while len(self._store) > _max_entries():
                self._store.popitem(last=False)
            CACHE_SIZE.labels(service=SERVICE).set(len(self._store))

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            CACHE_SIZE.labels(service=SERVICE).set(0)


PREDICT_CACHE = PredictCache()
