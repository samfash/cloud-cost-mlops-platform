#!/usr/bin/env python3
"""Cloud cost inference API with caching, batch, canary/shadow, and ops logging."""

from __future__ import annotations

import os
import time
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from src.api_guards import register_api_guards
from src.async_jobs import JOB_QUEUE, async_jobs_enabled
from src.audit_log import AUDIT_LOG
from src.exception.exception import CustomException
from src.feature_monitor import FEATURE_MONITOR, load_training_ranges
from src.logging.logger import logging
from src.observability import (
    metrics_response,
    observe_latency_predict,
    observe_predict,
    register_request_middleware,
    set_latency_model_loaded,
    set_model_loaded,
    timed,
    validate_latency_payload,
    validate_predict_payload,
)
from src.pipeline.prediction_pipeline import (
    CustomData,
    LatencyCustomData,
    PredictionPipeline,
)
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
set_latency_model_loaded(bool(predictor and predictor.has_latency_model))
AUDIT_LOG.ensure_schema()

_dataset = Path(__file__).resolve().parent / "dataset" / "Cloud_Dataset.csv"
FEATURE_MONITOR.ranges = load_training_ranges(_dataset)


def _request_id() -> str | None:
    return getattr(g, "request_id", None)


def _score_latency(model: PredictionPipeline, payload: dict) -> float:
    frame = LatencyCustomData(payload, label_encoders=model.encoder).get_data_as_dataframe()
    return model.predict_latency(frame)


def _ensure_latency_feature(payload: dict, model: PredictionPipeline) -> tuple[dict, float | None]:
    """Fill latency_ms from the latency model when omitted."""
    if "latency_ms" in payload and payload["latency_ms"] not in (None, ""):
        return payload, None
    if not model.has_latency_model:
        raise ValueError(
            "latency_ms is required when the latency model is unavailable "
            "(set LATENCY_MODEL_ENABLED=1 and retrain/package)"
        )
    predicted = _score_latency(model, payload)
    filled = dict(payload)
    filled["latency_ms"] = predicted
    return filled, predicted


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


def _run_prediction(
    payload: dict,
) -> tuple[float, float, bool, str, str | None, float | None]:
    """Return prediction, wall latency, cache_hit, variant, version, predicted_latency_ms."""
    assert predictor is not None
    filled, predicted_latency = _ensure_latency_feature(payload, predictor)
    variant = choose_variant(probe_predictor is not None)
    active = probe_predictor if variant == "canary" and probe_predictor else predictor
    # Canary/probe may lack latency model; prefer primary for fill, score on active.
    if active is not predictor and "latency_ms" not in payload:
        filled, predicted_latency = _ensure_latency_feature(payload, active)

    value, latency_s, cache_hit = _score(active, filled)

    if serving_mode() == "shadow" and probe_predictor is not None:
        try:
            shadow_payload, _ = _ensure_latency_feature(payload, probe_predictor)
            shadow_value, _, _ = _score(probe_predictor, shadow_payload)
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

    return value, latency_s, cache_hit, variant, active.model_version, predicted_latency


def _audit(
    *,
    endpoint: str,
    status: str,
    prediction: float | None = None,
    predicted_latency_ms: float | None = None,
    cache_hit: bool | None = None,
    wall_latency_ms: float | None = None,
    model_version: str | None = None,
    variant: str | None = None,
) -> None:
    AUDIT_LOG.write(
        {
            "created_at": time.time(),
            "request_id": _request_id(),
            "endpoint": endpoint,
            "model_version": model_version,
            "variant": variant,
            "prediction": prediction,
            "predicted_latency_ms": predicted_latency_ms,
            "cache_hit": cache_hit,
            "latency_ms": wall_latency_ms,
            "status": status,
        }
    )


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
        "latency_model_loaded": bool(predictor and predictor.has_latency_model),
        "latency_metrics": predictor.latency_metrics if predictor else None,
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
            "latency_model_loaded": predictor.has_latency_model,
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
            "task": "multi_regression",
            "labels": ["cost", "latency_ms"],
            "precision_recall_applicable": False,
            "offline_metrics": {
                "cost": predictor.metrics,
                "latency_ms": predictor.latency_metrics,
            },
            "online": {
                "serving_mode": serving_mode(),
                "model_version": predictor.model_version,
                "probe_loaded": probe_predictor is not None,
                "probe_version": (
                    probe_predictor.model_version if probe_predictor else None
                ),
                "latency_model_loaded": predictor.has_latency_model,
                "note": (
                    "Online accuracy requires ground-truth cost/latency feedback; "
                    "current online signals are wall-latency/errors/cache/drift OOB."
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
        value, latency_s, cache_hit, _variant, _version, pred_lat = _run_prediction(
            form_data
        )
        observe_predict("cache_hit" if cache_hit else "success", latency_s)
        _audit(
            endpoint="predict",
            status="success",
            prediction=value,
            predicted_latency_ms=pred_lat,
            cache_hit=cache_hit,
            wall_latency_ms=round(latency_s * 1000.0, 3),
            model_version=_version,
            variant=_variant,
        )
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
        validation_error = validate_predict_payload(
            data, require_latency_ms=not predictor.has_latency_model
        )
        if validation_error:
            observe_predict("invalid", 0.0, error_class="validation")
            return jsonify({"error": validation_error}), 400

        FEATURE_MONITOR.check(data)
        value, latency_s, cache_hit, variant, version, pred_lat = _run_prediction(data)
        observe_predict("cache_hit" if cache_hit else "success", latency_s)
        _audit(
            endpoint="api_predict",
            status="success",
            prediction=value,
            predicted_latency_ms=pred_lat,
            cache_hit=cache_hit,
            wall_latency_ms=round(latency_s * 1000.0, 3),
            model_version=version,
            variant=variant,
        )
        body = {
            "prediction": value,
            "status": "success",
            "model_version": version,
            "variant": variant,
            "request_id": _request_id(),
            "latency_ms": round(latency_s * 1000.0, 3),
            "cache_hit": cache_hit,
        }
        if pred_lat is not None:
            body["predicted_latency_ms"] = round(pred_lat, 3)
            body["latency_ms_source"] = "model"
        else:
            body["latency_ms_source"] = "request"
        return jsonify(body)
    except CustomException as e:
        logging.error("API prediction error: %s", e)
        observe_predict("error", 0.0, error_class="custom")
        return jsonify({"error": str(e), "request_id": _request_id()}), 500
    except Exception as e:
        logging.exception("Unexpected API prediction error")
        observe_predict("error", 0.0, error_class="unexpected")
        return jsonify({"error": str(e), "request_id": _request_id()}), 500


@app.post("/api/predict/latency")
def api_predict_latency():
    """Predict service latency_ms from workload features (no leakage inputs)."""
    try:
        if predictor is None or not predictor.has_latency_model:
            observe_latency_predict("unavailable")
            return jsonify({"error": "Latency model not available"}), 503

        data = request.get_json(silent=True)
        err = validate_latency_payload(data)
        if err:
            observe_latency_predict("invalid")
            return jsonify({"error": err}), 400

        FEATURE_MONITOR.check({k: v for k, v in data.items() if k != "latency_ms"})

        def _run():
            return _score_latency(predictor, data)

        predicted, wall_s = timed(_run)
        observe_latency_predict("success")
        _audit(
            endpoint="api_predict_latency",
            status="success",
            predicted_latency_ms=predicted,
            wall_latency_ms=round(wall_s * 1000.0, 3),
            model_version=predictor.model_version,
        )
        return jsonify(
            {
                "predicted_latency_ms": round(predicted, 3),
                "status": "success",
                "model_version": predictor.model_version,
                "request_id": _request_id(),
                "latency_ms": round(wall_s * 1000.0, 3),
                "offline_metrics": predictor.latency_metrics,
            }
        )
    except CustomException as e:
        logging.error("Latency prediction error: %s", e)
        observe_latency_predict("error")
        return jsonify({"error": str(e), "request_id": _request_id()}), 500
    except Exception as e:
        logging.exception("Unexpected latency prediction error")
        observe_latency_predict("error")
        return jsonify({"error": str(e), "request_id": _request_id()}), 500


def _batch_instances(instances: list) -> list[dict]:
    results = []
    for idx, item in enumerate(instances):
        err = validate_predict_payload(
            item, require_latency_ms=not (predictor and predictor.has_latency_model)
        )
        if err:
            results.append({"index": idx, "status": "error", "error": err})
            continue
        FEATURE_MONITOR.check(item)
        value, latency_s, cache_hit, variant, version, pred_lat = _run_prediction(item)
        observe_predict("cache_hit" if cache_hit else "success", latency_s)
        row = {
            "index": idx,
            "status": "success",
            "prediction": value,
            "model_version": version,
            "variant": variant,
            "latency_ms": round(latency_s * 1000.0, 3),
            "cache_hit": cache_hit,
        }
        if pred_lat is not None:
            row["predicted_latency_ms"] = round(pred_lat, 3)
        results.append(row)
    return results


@app.post("/api/predict/batch")
def api_predict_batch():
    """Real-time batch inference for a JSON list of payloads (sync)."""
    try:
        if predictor is None:
            return jsonify({"error": "Prediction model not available"}), 503

        body = request.get_json(silent=True)
        if not isinstance(body, dict) or "instances" not in body:
            return jsonify({"error": 'Body must be {"instances": [ ... ]}'}), 400
        instances = body["instances"]
        if not isinstance(instances, list) or not instances:
            return jsonify({"error": "instances must be a non-empty list"}), 400
        if len(instances) > 500:
            return jsonify({"error": "instances limited to 500 per request"}), 400

        results = _batch_instances(instances)
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


@app.post("/api/predict/batch/async")
def api_predict_batch_async():
    """Enqueue batch inference; poll ``GET /api/jobs/<job_id>`` (in-process queue)."""
    try:
        if predictor is None:
            return jsonify({"error": "Prediction model not available"}), 503
        if not async_jobs_enabled():
            return jsonify({"error": "Async jobs disabled (ASYNC_JOBS_ENABLED=0)"}), 503

        body = request.get_json(silent=True)
        if not isinstance(body, dict) or "instances" not in body:
            return jsonify({"error": 'Body must be {"instances": [ ... ]}'}), 400
        instances = body["instances"]
        if not isinstance(instances, list) or not instances:
            return jsonify({"error": "instances must be a non-empty list"}), 400
        if len(instances) > 2000:
            return jsonify({"error": "async instances limited to 2000 per job"}), 400

        # Capture list for worker closure.
        snapshot = list(instances)

        def _work():
            rows = _batch_instances(snapshot)
            return {"count": len(rows), "results": rows}

        job_id = JOB_QUEUE.submit(_work)
        return (
            jsonify(
                {
                    "status": "queued",
                    "job_id": job_id,
                    "poll": f"/api/jobs/{job_id}",
                    "request_id": _request_id(),
                }
            ),
            202,
        )
    except Exception as e:
        logging.exception("async batch enqueue failed")
        return jsonify({"error": str(e), "request_id": _request_id()}), 500


@app.get("/api/jobs/<job_id>")
def api_job_status(job_id: str):
    job = JOB_QUEUE.get(job_id)
    if job is None:
        return jsonify({"error": "job not found", "request_id": _request_id()}), 404
    payload = {
        "job_id": job.job_id,
        "status": job.status,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "request_id": _request_id(),
    }
    if job.status == "succeeded":
        payload["result"] = job.result
    if job.status == "failed":
        payload["error"] = job.error
    return jsonify(payload)


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "not found", "request_id": _request_id()}), 404


@app.errorhandler(405)
def method_not_allowed(_error):
    return jsonify({"error": "method not allowed", "request_id": _request_id()}), 405


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
