#!/usr/bin/env python3
import hashlib
import hmac
import json
import pickle
import sys
from pathlib import Path
from typing import ClassVar

import pandas as pd

from src.exception.exception import CustomException
from src.logging.logger import logging
from src.utils.feature_engineering import (
    CATEGORICAL_COLUMNS,
    add_engineered_features,
    add_temporal_features,
    encode_categorical_columns,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BUNDLE_ROOT = _PROJECT_ROOT / "artifacts" / "model_bundle"


def _sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _object_path(digest: str) -> Path:
    return _BUNDLE_ROOT / "objects" / digest[:2] / digest[2:4] / digest[4:]


def _binding_mac(seal_tag: str, digest_ring: str, publish_nonce: str) -> str:
    key = hashlib.blake2b(
        publish_nonce.encode(), digest_size=16, person=b"mpip-mac"
    ).digest()
    return hmac.new(
        key, f"{seal_tag}|{digest_ring}".encode(), hashlib.sha256
    ).hexdigest()


class PredictionPipeline:
    def __init__(self, version: str | None = None):
        try:
            logging.info("Initiating prediction pipeline.")
            if version:
                head = version.strip()
            else:
                head = (_BUNDLE_ROOT / "HEAD").read_text(encoding="utf-8").strip()
            self.bundle_dir = str(_BUNDLE_ROOT / "versions" / head)
            bundle = Path(self.bundle_dir)
            if not bundle.is_dir():
                raise RuntimeError(f"Model version not found: {head}")

            with (bundle / "manifest.json").open() as handle:
                manifest = json.load(handle)

            expected_mac = _binding_mac(
                manifest["seal_tag"],
                manifest["digest_ring"],
                manifest["publish_nonce"],
            )
            if not hmac.compare_digest(expected_mac, manifest["binding_mac"]):
                msg = "binding_mac integrity check failed"
                raise RuntimeError(msg)

            resolved: dict[str, Path] = {}
            for name, meta in manifest["blobs"].items():
                path = _object_path(meta["sha256"])
                actual = _sha256_file(path)
                expected = meta["sha256"]
                if actual != expected:
                    msg = f"Integrity check failed for {name}: {actual} != {expected}"
                    raise RuntimeError(msg)
                if path.stat().st_size != int(meta["size"]):
                    msg = f"Size check failed for {name}"
                    raise RuntimeError(msg)
                resolved[name] = path

            with resolved["model.pkl"].open("rb") as handle:
                self.model = pickle.load(handle)

            try:
                with resolved["label_encoders.pkl"].open("rb") as handle:
                    self.encoder = pickle.load(handle)
            except FileNotFoundError:
                self.encoder = None

            with resolved["feature_columns.json"].open() as handle:
                feature_schema = json.load(handle)
            self.feature_columns = feature_schema["feature_order"]
            self.model_version = feature_schema["model_version"]

            with resolved["metrics.json"].open() as handle:
                self.metrics = json.load(handle)

            logging.info("Prediction pipeline initialized successfully.")
        except Exception as e:
            raise CustomException(e, sys) from e

    def predict(self, input_data: pd.DataFrame):
        try:
            if self.feature_columns is not None:
                input_data = input_data.reindex(columns=self.feature_columns)
            return self.model.predict(input_data)
        except Exception as e:
            raise CustomException(e, sys) from e


class CustomData:
    NUMERIC_COLUMNS: ClassVar[list[str]] = [
        "cpu_usage",
        "memory_usage",
        "net_io",
        "disk_io",
        "RAM_GB",
        "latency_ms",
        "throughput",
        "utilization",
    ]
    INTEGER_COLUMNS: ClassVar[list[str]] = ["vCPU"]
    TEMPORAL_COLUMNS: ClassVar[list[str]] = [
        "hour",
        "day",
        "month",
        "day_of_week",
        "is_weekend",
    ]

    def __init__(self, data: dict, label_encoders: dict | None = None):
        self.data = data
        self.label_encoders = label_encoders

    def get_data_as_dataframe(self) -> pd.DataFrame:
        try:
            df = pd.DataFrame([self.data])

            for col in self.NUMERIC_COLUMNS:
                df[col] = pd.to_numeric(df[col])
            for col in self.INTEGER_COLUMNS:
                df[col] = pd.to_numeric(df[col]).astype(int)

            if "timestamp" in df.columns:
                df = add_temporal_features(df, timestamp_col="timestamp")
            else:
                for col in self.TEMPORAL_COLUMNS:
                    df[col] = pd.to_numeric(df[col]).astype(int)

            df = encode_categorical_columns(df, self.label_encoders, CATEGORICAL_COLUMNS)
            return add_engineered_features(df)
        except Exception as e:
            raise CustomException(e, sys) from e
