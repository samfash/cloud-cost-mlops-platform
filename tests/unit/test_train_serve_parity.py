"""Train/serve feature parity: CustomData must match training transform columns."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
CC = ROOT / "cloud-cost"
sys.path.insert(0, str(CC))


@pytest.fixture(scope="module")
def trained_artifacts():
    train_csv = CC / "artifacts" / "data_transformation" / "train.csv"
    encoders = CC / "artifacts" / "data_transformation" / "label_encoders.pkl"
    schema = CC / "artifacts" / "data_transformation" / "feature_columns.json"
    if not (train_csv.is_file() and encoders.is_file() and schema.is_file()):
        pytest.skip("Train first: cd cloud-cost && python main.py")
    return train_csv, encoders, schema


def test_customdata_columns_match_feature_order(trained_artifacts):
    import pickle

    from src.pipeline.prediction_pipeline import CustomData

    train_csv, encoders_path, schema_path = trained_artifacts
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    feature_order = schema["feature_order"]
    with encoders_path.open("rb") as handle:
        encoders = pickle.load(handle)

    raw = pd.read_csv(CC / "dataset" / "Cloud_Dataset.csv").iloc[0].to_dict()
    payload = {
        "timestamp": raw["timestamp"],
        "cpu_usage": raw["cpu_usage"],
        "memory_usage": raw["memory_usage"],
        "net_io": raw["net_io"],
        "disk_io": raw["disk_io"],
        "RAM_GB": raw["RAM_GB"],
        "vCPU": raw["vCPU"],
        "latency_ms": raw["latency_ms"],
        "throughput": raw["throughput"],
        "utilization": raw["utilization"],
        "cloud_provider": raw["cloud_provider"],
        "region": raw["region"],
        "vm_type": raw["vm_type"],
        "target": raw["target"],
    }
    df = CustomData(payload, label_encoders=encoders).get_data_as_dataframe()
    # Drop raw categoricals; encoded + engineered remain
    serve_cols = [c for c in df.columns if c.endswith("_encoded") or c not in {
        "cloud_provider", "region", "vm_type", "target"
    }]
    for col in feature_order:
        assert col in serve_cols or col in df.columns, f"missing serve column {col}"
    aligned = df.reindex(columns=feature_order)
    assert list(aligned.columns) == feature_order
    assert not aligned.isna().any().any()


def test_feature_store_snapshot_exists(trained_artifacts):
    from src.feature_store import assert_serve_schema, load_schema_snapshot

    _, _, schema_path = trained_artifacts
    snap = CC / "artifacts" / "data_transformation" / "feature_store" / "schema_snapshot.json"
    if not snap.is_file():
        pytest.skip("feature store snapshot missing — retrain")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    snapshot = load_schema_snapshot(snap)
    assert_serve_schema(snapshot, schema["feature_order"], schema["model_version"])
