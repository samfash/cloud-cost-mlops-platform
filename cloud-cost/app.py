#!/usr/bin/env python3
"""Cloud cost inference API with readiness, metrics, caching, and ops logging."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

from src.api_guards import register_api_guards
from src.exception.exception import CustomException
from src.feature_monitor import FEATURE_MONITOR, load_training_ranges
from src.logging.logger import logging
from src.observability import (
    metrics_response,
    observe_predict,
    register_request_middleware,
    set_model_loaded,
    timed,
    validate_predict_payload,
)
from src.pipeline.prediction_pipeline import CustomData, PredictionPipeline
from src.predict_cache import PREDICT_CACHE, cache_key

app = Flask(__name__)
register_request_middleware(app)
register_api_guards(app)

try:
    logging.info("Initializing PredictionPipeline...")
    predictor = PredictionPipeline()
    logging.info("PredictionPipeline initialized successfully")
except CustomException as e:
    logging.error("Failed to initialize prediction pipeline: %s", e)
    predictor = None

set_model_loaded(predictor is not None)

_dataset = Path(__file__).resolve().parent / "dataset" / "Cloud_Dataset.csv"
FEATURE_MONITOR.ranges = load_training_ranges(_dataset)


def _request_id() -> str | None:
    return getattr(g, "request_id", None)


def _run_prediction(payload: dict) -> tuple[float, float, bool]:
    """Return (prediction, latency_s, cache_hit)."""
    key = cache_key(payload, predictor.model_version if predictor else None)
    cached = PREDICT_CACHE.get(key)
    if cached is not None:
        return cached, 0.0, True

    def _run():
        input_df = CustomData(payload, label_encoders=predictor.encoder).get_data_as_dataframe()
        return predictor.predict(input_df)

    prediction, latency_s = timed(_run)
    value = float(prediction[0])
    PREDICT_CACHE.put(key, value)
    return value, latency_s, False


@app.get("/")
def overview():
    return render_template("overview.html", active="overview")


@app.get("/estimate")
def home():
    return render_template("index.html", active="estimate")


@app.get("/health")
def health():
    """Liveness-oriented health: process is up; includes model metadata."""
    model_info = {
        "model_loaded": predictor is not None,
        "bundle_dir": predictor.bundle_dir if predictor else None,
        "model_version": predictor.model_version if predictor else None,
        "bundle_exists": os.path.exists(predictor.bundle_dir) if predictor else False,
        "status": "ok",
        "service": "cloud-cost-api",
    }
    if predictor and os.path.exists(predictor.bundle_dir):
        model_info["bundle_files"] = os.listdir(predictor.bundle_dir)
    if predictor and predictor.metrics:
        model_info["metrics"] = predictor.metrics
    return jsonify(model_info)


@app.get("/ready")
def ready():
    """Readiness: only ready when a sealed model bundle is loaded."""
    if predictor is None:
        return (
            jsonify(
                {
                    "ready": False,
                    "reason": "model_not_loaded",
                    "service": "cloud-cost-api",
                }
            ),
            503,
        )
    return jsonify(
        {
            "ready": True,
            "model_version": predictor.model_version,
            "bundle_dir": predictor.bundle_dir,
            "service": "cloud-cost-api",
        }
    )


@app.get("/metrics")
def metrics():
    body, status, headers = metrics_response()
    return body, status, headers


@app.post("/predict")
def predict():
    try:
        if predictor is None:
            observe_predict("unavailable", 0.0, error_class="model_unavailable")
            return jsonify({"error": "Prediction model not available"}), 503

        form_data = request.form.to_dict()
        if not form_data:
            observe_predict("invalid", 0.0, error_class="validation")
            return jsonify({"error": "Form body is required"}), 400

        FEATURE_MONITOR.check(form_data)
        value, latency_s, cache_hit = _run_prediction(form_data)
        observe_predict("cache_hit" if cache_hit else "success", latency_s)
        return render_template(
            "results.html",
            prediction=value,
            input_data=form_data,
            active="estimate",
        )
    except CustomException as e:
        logging.error("Prediction error: %s", e)
        observe_predict("error", 0.0, error_class="custom")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.exception("Unexpected prediction error")
        observe_predict("error", 0.0, error_class="unexpected")
        return jsonify({"error": str(e)}), 500


@app.post("/api/predict")
def api_predict():
    try:
        if predictor is None:
            observe_predict("unavailable", 0.0, error_class="model_unavailable")
            return jsonify({"error": "Prediction model not available"}), 503

        data = request.get_json(silent=True)
        validation_error = validate_predict_payload(data)
        if validation_error:
            observe_predict("invalid", 0.0, error_class="validation")
            return jsonify({"error": validation_error}), 400

        FEATURE_MONITOR.check(data)
        value, latency_s, cache_hit = _run_prediction(data)
        observe_predict("cache_hit" if cache_hit else "success", latency_s)
        return jsonify(
            {
                "prediction": value,
                "status": "success",
                "model_version": predictor.model_version,
                "request_id": _request_id(),
                "latency_ms": round(latency_s * 1000.0, 3),
                "cache_hit": cache_hit,
            }
        )
    except CustomException as e:
        logging.error("API prediction error: %s", e)
        observe_predict("error", 0.0, error_class="custom")
        return jsonify({"error": str(e), "request_id": _request_id()}), 500
    except Exception as e:
        logging.exception("Unexpected API prediction error")
        observe_predict("error", 0.0, error_class="unexpected")
        return jsonify({"error": str(e), "request_id": _request_id()}), 500


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "not found", "request_id": _request_id()}), 404


@app.errorhandler(405)
def method_not_allowed(_error):
    return jsonify({"error": "method not allowed", "request_id": _request_id()}), 405


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
