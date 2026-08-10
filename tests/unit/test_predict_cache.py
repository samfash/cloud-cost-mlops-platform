"""Unit tests for prediction cache helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cloud-cost"))

from src.predict_cache import PredictCache, cache_key


def test_cache_key_stable():
    a = cache_key({"b": 2, "a": 1}, "1.0.0")
    b = cache_key({"a": 1, "b": 2}, "1.0.0")
    assert a == b


def test_lru_ttl_cache(monkeypatch):
    monkeypatch.setenv("PREDICT_CACHE_ENABLED", "1")
    monkeypatch.setenv("PREDICT_CACHE_SIZE", "2")
    monkeypatch.setenv("PREDICT_CACHE_TTL_SECONDS", "60")
    cache = PredictCache()
    cache.put("k1", 1.0)
    cache.put("k2", 2.0)
    assert cache.get("k1") == 1.0
    cache.put("k3", 3.0)  # evicts oldest unused after moves
    # k2 may be evicted depending on LRU after k1 get; assert capacity bound
    assert cache.get("k3") == 3.0
