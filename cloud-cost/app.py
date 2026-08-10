#!/usr/bin/env python3
"""Cloud cost inference API with caching, batch, canary/shadow, and ops logging."""

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
from src.serving import (
    choose_variant,
    load_optional_probe,
    record_shadow,
    serving_mode,
)

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

probe_predictor = load_optional_probe() if predictor is not None else None
set_model_loaded(predictor is not None)

_dataset = Path(__file__).resolve().parent / "dataset" / "Cloud_Dataset.csv"
FEATURE_MONITOR.ranges = load_training_ranges(_dataset)


def _request_id() -> str | None:
    return getattr(g, "request_id", None)


def _score(model: PredictionPipeline, payload: dict) -> tuple[float, float, bool]:
    key = cache_key(payload, model.model_version)
    cached = PREDICT_CACHE.get(key)
    if cached is not None:
        return cached, 0.0, True

    def _run():
        input_df = CustomData(payload, label_encoders=model.encoder).get_data_as_dataframe()
        return model.predict(input_df)

    prediction, latency_s = timed(_run)
    value = float(prediction[0])
    PREDICT_CACHE.put(key, value)
    return value, latency_s, False


def _run_prediction(payload: dict) -> tuple[float, float, bool, str, str | None]:
    """Return prediction, latency, cache_hit, variant, model_version."""
    assert predictor is not None
    variant = choose_variant(probe_predictor is not None)
    active = probe_predictor if variant == "canary" and probe_predictor else predictor
    value, latency_s, cache_hit = _score(active, payload)

    if serving_mode() == "shadow" and probe_predictor is not None:
        try:
            shadow_value, _, _ = _score(probe_predictor, payload)
            logging.info(
                "shadow_score primary=%.6f probe=%.6f delta=%.6f",
                value,
                shadow_value,
                shadow_value - value,
            )
            record_shadow("success")
        except Exception:
            logging.exception("shadow scoring failed")
            record_shadow("error")

    return value, latency_s, cache_hit, variant, active.model_version


@app.get("/")
def overview():
    return render_template("overview.html", active="overview")


@app.get("/estimate")
def home():
    return render_template("index.html", active="estimate")


@app.get("/health")
def health():
    model_info = {
        "model_loaded": predictor is not None,
        "bundle_dir": predictor.bundle_dir if predictor else None,
        "model_version": predictor.model_version if predictor else None,
        "bundle_exists": os.path.exists(predictor.bundle_dir) if predictor else False,
        "status": "ok",
        "service": "cloud-cost-api",
        "serving_mode": serving_mode(),
        "probe_loaded": probe_predictor is not None,
        "probe_version": probe_predictor.model_version if probe_predictor else None,
    }
    if predictor and os.path.exists(predictor.bundle_dir):
        model_info["bundle_files"] = os.listdir(predictor.bundle_dir)
    if predictor and predictor.metrics:
        model_info["metrics"] = predictor.metrics
    return jsonify(model_info)


@app.get("/ready")
def ready():
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
            "serving_mode": serving_mode(),
        }
    )


@app.get("/metrics")
def metrics():
    body, status, headers = metrics_response()
    return body, status, headers


@app.get("/ops/model-card")
def model_card():
    """Offline metrics + online serving posture (ops convenience)."""
    if predictor is None:
        return jsonify({"error": "model_not_loaded"}), 503
    return jsonify(
        {
            "task": "regression",
            "label": "cost",
            "precision_recall_applicable": False,
            "offline_metrics": predictor.metrics,
            "online": {
                "serving_mode": serving_mode(),
                "model_version": predictor.model_version,
                "probe_loaded": probe_predictor is not None,
                "probe_version": (
                    probe_predictor.model_version if probe_predictor else None
                ),
                "note": (
                    "Online accuracy requires ground-truth cost feedback; "
                    "current online signals are latency/errors/cache/drift OOB."
                ),
            },
            "request_id": _request_id(),
        }
    )


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
        value, latency_s, cache_hit, _variant, _version = _run_prediction(form_data)
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
        value, latency_s, cache_hit, variant, version = _run_prediction(data)
        observe_predict("cache_hit" if cache_hit else "success", latency_s)
        return jsonify(
            {
                "prediction": value,
                "status": "success",
                "model_version": version,
                "variant": variant,
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


@app.post("/api/predict/batch")
def api_predict_batch():
    """Real-time batch inference for a JSON list of payloads (sync)."""
    try:
        if predictor is None:
            return jsonify({"error": "Prediction model not available"}), 503

        body = request.get_json(silent=True)
        if not isinstance(body, dict) or "instances" not in body:
            return jsonify({"error": "Body must be {\"instances\": [ ... ]}"}), 400
        instances = body["instances"]
        if not isinstance(instances, list) or not instances:
            return jsonify({"error": "instances must be a non-empty list"}), 400
        if len(instances) > 500:
            return jsonify({"error": "instances limited to 500 per request"}), 400

        results = []
        for idx, item in enumerate(instances):
            err = validate_predict_payload(item)
            if err:
                results.append({"index": idx, "status": "error", "error": err})
                continue
            FEATURE_MONITOR.check(item)
            value, latency_s, cache_hit, variant, version = _run_prediction(item)
            observe_predict("cache_hit" if cache_hit else "success", latency_s)
            results.append(
                {
                    "index": idx,
                    "status": "success",
                    "prediction": value,
                    "model_version": version,
                    "variant": variant,
                    "latency_ms": round(latency_s * 1000.0, 3),
                    "cache_hit": cache_hit,
                }
            )

        return jsonify(
            {
                "status": "success",
                "count": len(results),
                "results": results,
                "request_id": _request_id(),
            }
        )
    except Exception as e:
        logging.exception("batch prediction failed")
        return jsonify({"error": str(e), "request_id": _request_id()}), 500


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "not found", "request_id": _request_id()}), 404


@app.errorhandler(405)
def method_not_allowed(_error):
    return jsonify({"error": "method not allowed", "request_id": _request_id()}), 405


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
