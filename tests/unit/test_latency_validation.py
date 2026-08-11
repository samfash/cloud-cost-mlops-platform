"""Latency payload validation and optional latency_ms on cost predict."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cloud-cost"))

from src.observability import validate_latency_payload, validate_predict_payload


BASE = {
    "cpu_usage": 1,
    "memory_usage": 1,
    "net_io": 1,
    "disk_io": 1,
    "cloud_provider": "Azure",
    "region": "us-east",
    "vm_type": "t2.micro",
    "vCPU": 1,
    "RAM_GB": 1,
    "target": "scale_up",
    "throughput": 1,
    "utilization": 1,
    "timestamp": "1/1/2024 0:00",
}


def test_cost_payload_allows_omitted_latency_when_optional():
    assert validate_predict_payload(dict(BASE), require_latency_ms=False) is None


def test_cost_payload_requires_latency_when_forced():
    err = validate_predict_payload(dict(BASE), require_latency_ms=True)
    assert err and "latency_ms" in err


def test_latency_endpoint_validation():
    assert validate_latency_payload(dict(BASE)) is None
