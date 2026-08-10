"""Serving modes: primary HEAD, optional canary/shadow against CAS probe pin."""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

from prometheus_client import Counter

from src.logging.logger import logging
from src.pipeline.prediction_pipeline import PredictionPipeline

CANARY_ROUTES = Counter(
    "predict_canary_routes_total",
    "Canary routing decisions",
    ["service", "variant"],
)
SHADOW_SCORES = Counter(
    "predict_shadow_scores_total",
    "Shadow dual-score attempts",
    ["service", "outcome"],
)

SERVICE = "cloud-cost-api"
_BUNDLE_ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "model_bundle"


def serving_mode() -> str:
    mode = os.environ.get("SERVING_MODE", "primary").strip().lower()
    return mode if mode in {"primary", "canary", "shadow"} else "primary"


def canary_percent() -> float:
    try:
        return max(0.0, min(100.0, float(os.environ.get("CANARY_PERCENT", "0"))))
    except ValueError:
        return 0.0


def _probe_version() -> str | None:
    pins_path = _BUNDLE_ROOT / "pins.json"
    if not pins_path.is_file():
        return None
    try:
        pins = json.loads(pins_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    probe = pins.get("probe")
    anchor = pins.get("anchor")
    if probe and probe != anchor:
        return str(probe)
    return None


def load_optional_probe() -> PredictionPipeline | None:
    """Load probe model when canary/shadow enabled and a distinct probe pin exists."""
    mode = serving_mode()
    if mode == "primary" or canary_percent() <= 0:
        return None
    version = _probe_version()
    if not version:
        logging.info("No distinct CAS probe pin; canary/shadow inactive.")
        return None
    try:
        return PredictionPipeline(version=version)
    except Exception as exc:
        logging.warning("Failed to load probe model %s: %s", version, exc)
        return None


def choose_variant(probe_available: bool) -> str:
    """Return 'primary' or 'canary' for response routing."""
    mode = serving_mode()
    if mode != "canary" or not probe_available or canary_percent() <= 0:
        CANARY_ROUTES.labels(service=SERVICE, variant="primary").inc()
        return "primary"
    if random.random() * 100.0 < canary_percent():
        CANARY_ROUTES.labels(service=SERVICE, variant="canary").inc()
        return "canary"
    CANARY_ROUTES.labels(service=SERVICE, variant="primary").inc()
    return "primary"


def record_shadow(outcome: str) -> None:
    SHADOW_SCORES.labels(service=SERVICE, outcome=outcome).inc()
