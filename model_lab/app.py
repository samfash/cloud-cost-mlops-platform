"""Model lab Flask API for trial selection with ops hardening."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from pathlib import Path

from flask import Flask, g, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, generate_latest

from model_lab.selector import select_chosen_trial

# Reuse shared guards from cloud-cost when PYTHONPATH includes it.
try:
    from src.api_guards import register_api_guards
except ImportError:  # pragma: no cover - local import fallback
    register_api_guards = None  # type: ignore[assignment]

LAB_ROOT = Path(__file__).resolve().parent
SERVICE = "model-lab-api"

app = Flask(__name__)
if register_api_guards is not None:
    register_api_guards(app)

SELECT_REQUESTS = Counter(
    "model_lab_select_requests_total",
    "Model lab election attempts",
    ["outcome"],
)
HTTP_REQUESTS = Counter(
    "model_lab_http_requests_total",
    "Total HTTP requests for model lab",
    ["service", "method", "endpoint", "status"],
)


def _configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_model_lab_configured", False):
        return
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)

    class _JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            payload = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "service": SERVICE,
            }
            for key in ("request_id", "path", "method", "status", "latency_ms"):
                if hasattr(record, key):
                    payload[key] = getattr(record, key)
            return json.dumps(payload, default=str)

    handler.setFormatter(_JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root._model_lab_configured = True  # type: ignore[attr-defined]


_configure_logging()
log = logging.getLogger(SERVICE)


@app.before_request
def _before_request() -> None:
    incoming = request.headers.get("X-Request-Id") or request.headers.get("X-Request-ID")
    g.request_id = (incoming.strip()[:128] if incoming and incoming.strip() else uuid.uuid4().hex)
    g.request_started = time.perf_counter()


@app.after_request
def _after_request(response):
    started = getattr(g, "request_started", None)
    latency_ms = (
        round((time.perf_counter() - started) * 1000.0, 3) if started is not None else None
    )
    request_id = getattr(g, "request_id", None)
    if request_id:
        response.headers["X-Request-Id"] = request_id
    endpoint = request.endpoint or "unknown"
    HTTP_REQUESTS.labels(
        service=SERVICE,
        method=request.method,
        endpoint=endpoint,
        status=str(response.status_code),
    ).inc()
    log.info(
        "request completed",
        extra={
            "request_id": request_id,
            "path": request.path,
            "method": request.method,
            "status": response.status_code,
            "latency_ms": latency_ms,
        },
    )
    return response


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "model-lab",
            "ready": True,
            "lab_root": str(LAB_ROOT),
        }
    )


@app.get("/ready")
def ready():
    trials = LAB_ROOT / "trials"
    constraints = LAB_ROOT / "constraints.yaml"
    elect = LAB_ROOT / "legacy" / "elect.rexx"
    ok = trials.is_dir() and constraints.is_file() and elect.is_file()
    body = {
        "ready": ok,
        "service": "model-lab",
        "trials_dir": str(trials),
        "constraints_path": str(constraints),
    }
    return jsonify(body), (200 if ok else 503)


@app.get("/metrics")
def metrics():
    return generate_latest(REGISTRY), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.post("/api/select")
def select():
    try:
        # Empty body → defaults. Non-empty invalid JSON → 400 (do not coerce to {}).
        if request.content_length and request.content_length > 0:
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                SELECT_REQUESTS.labels(outcome="invalid").inc()
                return jsonify({"error": "Request body must be a JSON object"}), 400
        else:
            payload = {}

        trials_dir = Path(payload.get("trials_dir", LAB_ROOT / "trials"))
        constraints = Path(payload.get("constraints_path", LAB_ROOT / "constraints.yaml"))
        if not trials_dir.is_dir():
            SELECT_REQUESTS.labels(outcome="invalid").inc()
            return jsonify({"error": f"trials_dir not found: {trials_dir}"}), 400
        if not constraints.is_file():
            SELECT_REQUESTS.labels(outcome="invalid").inc()
            return jsonify({"error": f"constraints_path not found: {constraints}"}), 400

        chosen = select_chosen_trial(trials_dir, constraints)
        SELECT_REQUESTS.labels(outcome="success").inc()
        return jsonify(
            {
                "status": "success",
                "chosen": chosen,
                "request_id": getattr(g, "request_id", None),
            }
        )
    except Exception as e:
        log.exception("election failed")
        SELECT_REQUESTS.labels(outcome="error").inc()
        return jsonify({"error": str(e), "request_id": getattr(g, "request_id", None)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=False)
