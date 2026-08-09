"""Dependency-aware pipeline state tracking using Git blob digests."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd
from src.logging.logger import logging

PIPELINE_META_DIR = Path("artifacts") / ".pipeline"


def git_blob_sha256(path: Path) -> str | None:
    """Git SHA-256 blob object id for a file (SHA-256 over Git blob framing)."""
    try:
        if not path.is_file():
            return None
        data = path.read_bytes()
        header = f"blob {len(data)}".encode() + bytes([0])
        return hashlib.sha256(header + data).hexdigest()
    except OSError:
        return None


def normalize_path(path: str | Path) -> str:
    return Path(path).as_posix()


class DependencyTracker:
    """Persists and evaluates per-stage execution metadata under artifacts/.pipeline/."""

    def __init__(self, meta_dir: Path = PIPELINE_META_DIR):
        self.meta_dir = Path(meta_dir)
        self.meta_dir.mkdir(parents=True, exist_ok=True)

    def metadata_path(self, stage_id: str) -> Path:
        return self.meta_dir / f"{stage_id}.json"

    def load_metadata(self, stage_id: str) -> dict | None:
        path = self.metadata_path(stage_id)
        if not path.is_file():
            return None
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            logging.warning(f"Unreadable pipeline metadata for stage '{stage_id}'")
            return None

    def save_metadata(
        self,
        stage_id: str,
        dependencies: Iterable[str | Path],
        outputs: Iterable[str | Path],
    ) -> dict:
        """Write success metadata only after a stage completes successfully."""
        dep_map: dict[str, str] = {}
        for dep in dependencies:
            key = normalize_path(dep)
            digest = git_blob_sha256(Path(dep))
            if digest is None:
                raise FileNotFoundError(
                    f"Cannot record dependency hash; missing or unreadable: {key}"
                )
            dep_map[key] = digest

        out_map: dict[str, str] = {}
        for output in outputs:
            key = normalize_path(output)
            digest = git_blob_sha256(Path(output))
            if digest is None:
                raise FileNotFoundError(f"Cannot record output hash; missing or unreadable: {key}")
            out_map[key] = digest

        record = {
            "stage": stage_id,
            "status": "success",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "dependencies": dep_map,
            "outputs": out_map,
        }

        path = self.metadata_path(stage_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
            handle.write("\n")

        logging.info(f"Pipeline metadata saved for stage '{stage_id}' at {path}")
        return record

    def dependency_hashes_match(self, stage_id: str, dependencies: Iterable[str | Path]) -> bool:
        metadata = self.load_metadata(stage_id)
        if not metadata or metadata.get("status") != "success":
            return False

        recorded = metadata.get("dependencies") or {}
        current_keys = {normalize_path(dep) for dep in dependencies}
        recorded_keys = set(recorded.keys())
        if current_keys != recorded_keys:
            return False

        for dep in dependencies:
            key = normalize_path(dep)
            current = git_blob_sha256(Path(dep))
            if current is None or recorded.get(key) != current:
                return False
        return True

    def output_hashes_match(self, stage_id: str, outputs: Iterable[str | Path]) -> bool:
        metadata = self.load_metadata(stage_id)
        if not metadata or metadata.get("status") != "success":
            return False

        recorded = metadata.get("outputs") or {}
        current_keys = {normalize_path(out) for out in outputs}
        recorded_keys = set(recorded.keys())
        if current_keys != recorded_keys:
            return False

        for output in outputs:
            key = normalize_path(output)
            current = git_blob_sha256(Path(output))
            if current is None or recorded.get(key) != current:
                return False
        return True


def _is_readable_file(path: Path) -> bool:
    try:
        return path.is_file() and os.access(path, os.R_OK)
    except OSError:
        return False


def validate_status_txt(path: Path) -> bool:
    if not _is_readable_file(path):
        return False
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return False
        lines = content.splitlines()
        status_line = lines[0]
        token = status_line.strip().split()[-1].lower()
        return token == "true"
    except OSError:
        return False


def validate_csv_with_cost(path: Path) -> bool:
    if not _is_readable_file(path):
        return False
    try:
        df = pd.read_csv(path)
        return not (df.empty or "cost" not in df.columns)
    except Exception:
        return False


def validate_pickle(path: Path) -> bool:
    if not _is_readable_file(path):
        return False
    try:
        if path.stat().st_size == 0:
            return False
        with open(path, "rb") as handle:
            pickle.load(handle)
        return True
    except Exception:
        return False


def validate_feature_columns_json(path: Path) -> bool:
    if not _is_readable_file(path):
        return False
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return False
        feature_order = data.get("feature_order")
        n_features = data.get("n_features")
        if not isinstance(feature_order, list) or len(feature_order) == 0:
            return False
        if not isinstance(n_features, int) or n_features != len(feature_order):
            return False
        return "model_version" in data
    except Exception:
        return False


def validate_metrics_json(path: Path) -> bool:
    if not _is_readable_file(path):
        return False
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return False
        required = {"MAE", "MSE", "RMSE", "R2"}
        return required.issubset(data.keys())
    except Exception:
        return False


def validate_label_encoders(path: Path) -> bool:
    if not _is_readable_file(path):
        return False
    try:
        with open(path, "rb") as handle:
            encoders = pickle.load(handle)
        return isinstance(encoders, dict) and len(encoders) > 0
    except Exception:
        return False


def validate_cas_bundle_head(path: Path) -> bool:
    """Validate CAS packaging via HEAD pointer + versioned manifest + pins."""
    if not _is_readable_file(path):
        return False
    try:
        version = path.read_text(encoding="utf-8").strip()
        if not version:
            return False
        bundle_root = path.parent
        manifest = bundle_root / "versions" / version / "manifest.json"
        pins = bundle_root / "pins.json"
        if not _is_readable_file(manifest) or not _is_readable_file(pins):
            return False
        with open(manifest, encoding="utf-8") as handle:
            data = json.load(handle)
        required = {
            "model_version",
            "blobs",
            "digest_ring",
            "binding_mac",
            "promotion_class",
        }
        if not required.issubset(data.keys()):
            return False
        if data.get("model_version") != version:
            return False
        for logical in ("model.pkl", "label_encoders.pkl", "metrics.json", "feature_columns.json"):
            if logical not in data["blobs"]:
                return False
        return True
    except Exception:
        return False


def outputs_structurally_valid(
    outputs: dict[str, Callable[[Path], bool]],
) -> bool:
    """Every owned output must exist, be readable, and pass its structural check."""
    if not outputs:
        return False
    for path_str, validator in outputs.items():
        path = Path(path_str)
        if not validator(path):
            logging.info(f"Artifact failed structural validation: {path_str}")
            return False
    return True
