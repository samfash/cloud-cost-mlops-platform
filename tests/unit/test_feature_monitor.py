"""Unit tests for feature range monitor."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cloud-cost"))

from src.feature_monitor import FeatureMonitor


def test_in_band_ok():
    mon = FeatureMonitor({"cpu_usage": (0.0, 100.0)})
    assert mon.check({"cpu_usage": 40}) == []


def test_out_of_band():
    mon = FeatureMonitor({"cpu_usage": (0.0, 100.0)})
    assert "cpu_usage" in mon.check({"cpu_usage": 150})
