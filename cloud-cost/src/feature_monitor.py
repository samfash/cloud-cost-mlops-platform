"""Lightweight log-only feature range checks at predict time (drift signal)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.logging.logger import logging

# Numeric features commonly present on the wire / after form submit.
_NUMERIC_FIELDS = (
    "cpu_usage",
    "memory_usage",
    "net_io",
    "disk_io",
    "RAM_GB",
    "vCPU",
    "latency_ms",
    "throughput",
    "utilization",
)


def _default_ranges() -> dict[str, tuple[float, float]]:
    """Conservative operating bands derived from Cloud_Dataset scale."""
    return {
        "cpu_usage": (0.0, 100.0),
        "memory_usage": (0.0, 100.0),
        "net_io": (0.0, 5000.0),
        "disk_io": (0.0, 5000.0),
        "RAM_GB": (0.25, 256.0),
        "vCPU": (1.0, 128.0),
        "latency_ms": (0.0, 10000.0),
        "throughput": (0.0, 100000.0),
        "utilization": (0.0, 100.0),
    }


def load_training_ranges(dataset_csv: Path | None = None) -> dict[str, tuple[float, float]]:
    """Optionally tighten bands from the training CSV percentiles (p01–p99)."""
    ranges = _default_ranges()
    if dataset_csv is None or not dataset_csv.is_file():
        return ranges
    try:
        import pandas as pd

        df = pd.read_csv(dataset_csv)
        for col in _NUMERIC_FIELDS:
            if col not in df.columns:
                continue
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if series.empty:
                continue
            low = float(series.quantile(0.01))
            high = float(series.quantile(0.99))
            if high > low:
                ranges[col] = (low, high)
    except Exception as exc:  # pragma: no cover - best-effort
        logging.warning("feature monitor: failed to load training ranges: %s", exc)
    return ranges


class FeatureMonitor:
    def __init__(self, ranges: dict[str, tuple[float, float]] | None = None) -> None:
        self.ranges = ranges or _default_ranges()

    def check(self, payload: dict[str, Any]) -> list[str]:
        """Return list of out-of-band feature names; also logs a JSON warning."""
        offenders: list[str] = []
        details: dict[str, Any] = {}
        for field in _NUMERIC_FIELDS:
            if field not in payload:
                continue
            try:
                value = float(payload[field])
            except (TypeError, ValueError):
                continue
            low, high = self.ranges.get(field, (None, None))
            if low is None or high is None:
                continue
            if value < low or value > high:
                offenders.append(field)
                details[field] = {"value": value, "expected": [low, high]}
        if offenders:
            logging.warning(
                "feature_out_of_band %s",
                json.dumps({"offenders": offenders, "details": details}),
            )
        return offenders


FEATURE_MONITOR = FeatureMonitor()
