"""Request correlation and Prometheus metrics for the inference API."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable
from typing import Any

import logging

from flask import Flask, g, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

SERVICE_NAME = "cloud-cost-api"
_LOG = logging.getLogger(SERVICE_NAME)

REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "endpoint", "status"],
)
PREDICT_REQUESTS = Counter(
    "predict_requests_total",
    "Prediction attempts",
    ["service", "outcome"],
)
PREDICT_LATENCY = Histogram(
    "predict_latency_seconds",
    "Prediction latency in seconds",
    ["service"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
MODEL_LOADED = Gauge(
    "model_loaded",
    "1 if prediction model is loaded, else 0",
    ["service"],
)
LATENCY_MODEL_LOADED = Gauge(
    "latency_model_loaded",
    "1 if latency prediction model is loaded, else 0",
    ["service"],
)
PREDICT_ERRORS = Counter(
    "predict_errors_total",
    "Prediction errors by class",
    ["service", "error_class"],
)
LATENCY_PREDICT_REQUESTS = Counter(
    "latency_predict_requests_total",
    "Latency prediction attempts",
    ["service", "outcome"],
)


def new_request_id() -> str:
    incoming = request.headers.get("X-Request-Id") or request.headers.get("X-Request-ID")
    if incoming and incoming.strip():
        return incoming.strip()[:128]
    return uuid.uuid4().hex


def set_model_loaded(loaded: bool) -> None:
    MODEL_LOADED.labels(service=SERVICE_NAME).set(1 if loaded else 0)


def set_latency_model_loaded(loaded: bool) -> None:
    LATENCY_MODEL_LOADED.labels(service=SERVICE_NAME).set(1 if loaded else 0)


def observe_predict(outcome: str, latency_s: float, error_class: str | None = None) -> None:
    PREDICT_REQUESTS.labels(service=SERVICE_NAME, outcome=outcome).inc()
    PREDICT_LATENCY.labels(service=SERVICE_NAME).observe(latency_s)
    if error_class:
        PREDICT_ERRORS.labels(service=SERVICE_NAME, error_class=error_class).inc()


def observe_latency_predict(outcome: str) -> None:
    LATENCY_PREDICT_REQUESTS.labels(service=SERVICE_NAME, outcome=outcome).inc()


def register_request_middleware(app: Flask, *, service: str = SERVICE_NAME) -> None:
    """Attach request-id propagation and structured access logging."""

    @app.before_request
    def _before() -> None:
        g.request_id = new_request_id()
        g.request_started = time.perf_counter()

    @app.after_request
    def _after(response):  # type: ignore[no-untyped-def]
        started = getattr(g, "request_started", None)
        latency_ms = (
            round((time.perf_counter() - started) * 1000.0, 3) if started is not None else None
        )
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-Id"] = request_id

        endpoint = request.endpoint or "unknown"
        REQUESTS.labels(
            service=service,
            method=request.method,
            endpoint=endpoint,
            status=str(response.status_code),
        ).inc()

        _LOG.info(
            "request completed",
            extra={
                "request_id": request_id,
                "path": request.path,
                "method": request.method,
                "status": response.status_code,
                "latency_ms": latency_ms,
                "service": service,
            },
        )
        return response


def metrics_response() -> tuple[bytes, int, dict[str, str]]:
    """Return Prometheus exposition payload."""
    return generate_latest(REGISTRY), 200, {"Content-Type": CONTENT_TYPE_LATEST}


def _latency_optional_by_default() -> bool:
    return os.environ.get("LATENCY_MODEL_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }


def required_predict_fields(*, require_latency_ms: bool = True) -> tuple[str, ...]:
    fields = [
        "cpu_usage",
        "memory_usage",
        "net_io",
        "disk_io",
        "cloud_provider",
        "region",
        "vm_type",
        "vCPU",
        "RAM_GB",
        "target",
        "throughput",
        "utilization",
    ]
    if require_latency_ms:
        fields.insert(fields.index("throughput"), "latency_ms")
    return tuple(fields)


def validate_predict_payload(
    data: Any, *, require_latency_ms: bool | None = None
) -> str | None:
    """Return an error message if payload is invalid, else None.

    When ``LATENCY_MODEL_ENABLED`` and the latency model is available, callers
    may pass ``require_latency_ms=False`` so the server fills ``latency_ms``.
    """
    if data is None:
        return "Request body must be a JSON object"
    if not isinstance(data, dict):
        return "Request body must be a JSON object"
    if require_latency_ms is None:
        # Soft default: latency_ms still preferred, but omission is allowed when
        # the latency model is enabled (server fills before cost scoring).
        require_latency_ms = not _latency_optional_by_default()
    missing = [
        field
        for field in required_predict_fields(require_latency_ms=require_latency_ms)
        if field not in data
    ]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    temporal = ("hour", "day", "month", "day_of_week", "is_weekend")
    if "timestamp" not in data and not all(key in data for key in temporal):
        return "Provide 'timestamp' or temporal fields hour/day/month/day_of_week/is_weekend"
    return None


def validate_latency_payload(data: Any) -> str | None:
    """Latency endpoint never accepts latency_ms as a required input."""
    return validate_predict_payload(data, require_latency_ms=False)


def timed(fn: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - started
