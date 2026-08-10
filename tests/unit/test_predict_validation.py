"""Unit tests for predict payload validation."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cloud-cost"))

from src.observability import validate_predict_payload


def test_missing_body():
    assert validate_predict_payload(None)


def test_missing_fields():
    err = validate_predict_payload({"cpu_usage": 1})
    assert err and "Missing required fields" in err


def test_valid_with_timestamp():
    payload = {
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
        "latency_ms": 1,
        "throughput": 1,
        "utilization": 1,
        "timestamp": "1/1/2024 0:00",
    }
    assert validate_predict_payload(payload) is None
