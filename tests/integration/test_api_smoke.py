"""Integration smoke tests for Flask inference API (requires trained artifacts)."""

import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
CC = ROOT / "cloud-cost"
sys.path.insert(0, str(CC))


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


def test_home(client):
    resp = client.get("/")
    assert resp.status_code == 200
