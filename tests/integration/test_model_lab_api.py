"""HTTP smoke tests for the model lab API."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

regina = shutil.which("regina")


@pytest.fixture(scope="module")
def client():
    from model_lab.app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "model-lab"


def test_ready(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.get_json()["ready"] is True


def test_metrics(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"model_lab_http_requests_total" in resp.data


@pytest.mark.skipif(regina is None, reason="regina-rexx not installed")
def test_select(client):
    resp = client.post("/api/select", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["chosen"]["trial_id"] == "trial_200"
    assert data["request_id"]


def test_select_invalid_body(client):
    resp = client.post("/api/select", data="not-json", content_type="application/json")
    assert resp.status_code in {400, 500}
