"""Unit tests for optional API key and rate-limit guards."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flask import Flask, jsonify

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cloud-cost"))

from src.api_guards import _LIMITER, register_api_guards  # noqa: E402


@pytest.fixture
def guarded_app(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("RATE_LIMIT_PER_MINUTE", raising=False)
    _LIMITER._hits.clear()
    app = Flask("guard-test")

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    @app.get("/ready")
    def ready():
        return jsonify({"ready": True})

    @app.post("/api/predict")
    def api_predict():
        return jsonify({"status": "success"})

    register_api_guards(app)
    app.config["TESTING"] = True
    return app


def test_open_by_default(guarded_app):
    client = guarded_app.test_client()
    assert client.get("/ready").status_code == 200
    assert client.post("/api/predict").status_code == 200


def test_api_key_protects_predict_not_ready(monkeypatch, guarded_app):
    monkeypatch.setenv("API_KEY", "secret-token")
    # Re-register is unnecessary; guards read env at request time.
    client = guarded_app.test_client()
    assert client.get("/ready").status_code == 200
    denied = client.post("/api/predict")
    assert denied.status_code == 401
    ok = client.post("/api/predict", headers={"X-API-Key": "secret-token"})
    assert ok.status_code == 200
    bearer = client.post(
        "/api/predict", headers={"Authorization": "Bearer secret-token"}
    )
    assert bearer.status_code == 200


def test_rate_limit(monkeypatch, guarded_app):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    client = guarded_app.test_client()
    assert client.post("/api/predict").status_code == 200
    assert client.post("/api/predict").status_code == 200
    limited = client.post("/api/predict")
    assert limited.status_code == 429
    # Probes remain available.
    assert client.get("/health").status_code == 200
