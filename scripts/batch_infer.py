#!/usr/bin/env python3
"""Offline/batch scoring helper against a running API or local PredictionPipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _via_http(url: str, instances: list[dict]) -> dict:
    import urllib.request

    payload = json.dumps({"instances": instances}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _via_local(instances: list[dict]) -> dict:
    sys.path.insert(0, str(ROOT / "cloud-cost"))
    from src.pipeline.prediction_pipeline import CustomData, PredictionPipeline

    model = PredictionPipeline()
    results = []
    for idx, item in enumerate(instances):
        df = CustomData(item, label_encoders=model.encoder).get_data_as_dataframe()
        pred = float(model.predict(df)[0])
        results.append(
            {
                "index": idx,
                "status": "success",
                "prediction": pred,
                "model_version": model.model_version,
            }
        )
    return {"status": "success", "count": len(results), "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch cloud-cost inference")
    parser.add_argument("input_json", type=Path, help="JSON file: list or {instances:[...]}")
    parser.add_argument(
        "--url",
        default="",
        help="If set, POST to API batch endpoint (e.g. http://127.0.0.1:8080/api/predict/batch)",
    )
    args = parser.parse_args()
    raw = json.loads(args.input_json.read_text(encoding="utf-8"))
    instances = raw["instances"] if isinstance(raw, dict) and "instances" in raw else raw
    if not isinstance(instances, list):
        print("input must be a list or {instances:[...]}", file=sys.stderr)
        return 1
    out = _via_http(args.url, instances) if args.url else _via_local(instances)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
