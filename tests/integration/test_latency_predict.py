"""Integration: latency model endpoint + cost predict without latency_ms."""

from pathlib import Path
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cloud-cost"))

SAMPLE = {
    "timestamp": "1/1/2024 0:00",
    "cpu_usage": 43.71,
    "memory_usage": 95.56,
    "net_io": 379.4,
    "disk_io": 638.79,
    "RAM_GB": 1,
    "vCPU": 1,
    "throughput": 1380.99,
    "utilization": 69.64,
    "cloud_provider": "Azure",
    "region": "us-east",
    "vm_type": "t2.micro",
    "target": "scale_up",
}


@pytest.fixture(scope="module")
def client():
    from app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_latency_endpoint(client):
    resp = client.post("/api/predict/latency", json=SAMPLE)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["predicted_latency_ms"] > 0
    assert "offline_metrics" in data


def test_cost_predict_fills_latency(client):
    resp = client.post("/api/predict", json=SAMPLE)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["latency_ms_source"] == "model"
    assert "predicted_latency_ms" in data
    assert isinstance(data["prediction"], float)


def test_async_batch_job(client):
    resp = client.post(
        "/api/predict/batch/async",
        json={"instances": [SAMPLE, {**SAMPLE, "latency_ms": 228.02}]},
    )
    assert resp.status_code == 202, resp.get_data(as_text=True)
    job_id = resp.get_json()["job_id"]
    for _ in range(50):
        status = client.get(f"/api/jobs/{job_id}")
        body = status.get_json()
        if body["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)
    assert body["status"] == "succeeded"
    assert body["result"]["count"] == 2
