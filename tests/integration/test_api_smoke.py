"""Integration smoke tests for Flask inference API (requires trained artifacts)."""

from __future__ import annotations

import os
import sys
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


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["model_loaded"] is True
    assert data["model_version"]
    assert data["status"] == "ok"


def test_ready(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ready"] is True
    assert data["model_version"]


def test_overview_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Know what a cloud server may cost" in resp.data


def test_estimate_page(client):
    resp = client.get("/estimate")
    assert resp.status_code == 200
    assert b"Cost estimate" in resp.data


def test_metrics(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "http_requests_total" in body
    assert "model_loaded" in body


def test_api_predict_success(client):
    resp = client.post("/api/predict", json=SAMPLE_PAYLOAD)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert isinstance(data["prediction"], float)
    assert data["model_version"]
    assert data["request_id"]
    assert "latency_ms" in data
    assert "cache_hit" in data
    assert resp.headers.get("X-Request-Id")


def test_api_predict_cache_hit(client):
    first = client.post("/api/predict", json=SAMPLE_PAYLOAD)
    second = client.post("/api/predict", json=SAMPLE_PAYLOAD)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json()["cache_hit"] is True
    assert first.get_json()["prediction"] == second.get_json()["prediction"]


def test_api_predict_validation(client):
    resp = client.post("/api/predict", json={"cpu_usage": 1})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_request_id_propagation(client):
    resp = client.get("/ready", headers={"X-Request-Id": "test-req-123"})
    assert resp.headers.get("X-Request-Id") == "test-req-123"
