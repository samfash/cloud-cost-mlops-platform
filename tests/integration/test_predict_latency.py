"""Lightweight latency smoke for /api/predict (warm path)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CC = ROOT / "cloud-cost"
sys.path.insert(0, str(CC))

SAMPLE_PAYLOAD = {
    "timestamp": "1/1/2024 0:00",
    "cpu_usage": 43.71,
    "memory_usage": 95.56,
    "net_io": 379.4,
    "disk_io": 638.79,
    "RAM_GB": 1,
    "vCPU": 1,
    "latency_ms": 228.02,
    "throughput": 1380.99,
    "utilization": 69.64,
    "cloud_provider": "Azure",
    "region": "us-east",
    "vm_type": "t2.micro",
    "target": "scale_up",
}


@pytest.fixture(scope="module")
def client():
    head = CC / "artifacts" / "model_bundle" / "HEAD"
    if not head.is_file():
        pytest.skip("Train and package first: python main.py")
    os.chdir(CC)
    from app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_warm_predict_under_budget(client):
    # Warm once
    client.post("/api/predict", json=SAMPLE_PAYLOAD)
    started = time.perf_counter()
    resp = client.post("/api/predict", json=SAMPLE_PAYLOAD)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    assert resp.status_code == 200
    # Local RF warm path (often cache hit) should be well under 250ms wall time.
    assert elapsed_ms < 250.0
