"""Feature range / drift signals at predict time (log + Prometheus)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prometheus_client import Counter

from src.logging.logger import logging

FEATURE_OOB = Counter(
    "feature_out_of_band_total",
    "Predict requests with at least one out-of-band feature",
    ["service"],
)
FEATURE_OOB_FIELDS = Counter(
    "feature_out_of_band_fields_total",
    "Out-of-band feature observations by field",
    ["service", "field"],
)

SERVICE = "cloud-cost-api"

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
    except Exception as exc:  # pragma: no cover
        logging.warning("feature monitor: failed to load training ranges: %s", exc)
    return ranges


def population_stability_index(
    expected: list[float], actual: list[float], bins: int = 10
) -> float:
    """Classic PSI between two 1-D samples (offline monitoring helper)."""
    import numpy as np

    if len(expected) < bins or len(actual) < bins:
        return 0.0
    quantiles = np.linspace(0, 1, bins + 1)
    edges = np.unique(np.quantile(expected, quantiles))
    if len(edges) < 3:
        return 0.0
    e_hist, _ = np.histogram(expected, bins=edges)
    a_hist, _ = np.histogram(actual, bins=edges)
    e_pct = np.clip(e_hist / max(e_hist.sum(), 1), 1e-4, None)
    a_pct = np.clip(a_hist / max(a_hist.sum(), 1), 1e-4, None)
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


class FeatureMonitor:
    def __init__(self, ranges: dict[str, tuple[float, float]] | None = None) -> None:
        self.ranges = ranges or _default_ranges()

    def check(self, payload: dict[str, Any]) -> list[str]:
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
                FEATURE_OOB_FIELDS.labels(service=SERVICE, field=field).inc()
        if offenders:
            FEATURE_OOB.labels(service=SERVICE).inc()
            logging.warning(
                "feature_out_of_band %s",
                json.dumps({"offenders": offenders, "details": details}),
            )
        return offenders


FEATURE_MONITOR = FeatureMonitor()
