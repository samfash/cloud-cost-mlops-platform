"""Batch predict API smoke."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CC = ROOT / "cloud-cost"
sys.path.insert(0, str(CC))

SAMPLE = {
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
    if not (CC / "artifacts" / "model_bundle" / "HEAD").is_file():
        pytest.skip("Train and package first")
    os.chdir(CC)
    from app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_batch_predict(client):
    resp = client.post("/api/predict/batch", json={"instances": [SAMPLE, SAMPLE]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["count"] == 2
    assert data["results"][0]["status"] == "success"
    assert isinstance(data["results"][0]["prediction"], float)


def test_model_card(client):
    resp = client.get("/ops/model-card")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["task"] == "regression"
    assert data["precision_recall_applicable"] is False
    assert "offline_metrics" in data
