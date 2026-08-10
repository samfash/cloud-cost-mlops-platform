"""Lightweight local feature-store contract (schema snapshot, not Feast)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def schema_fingerprint(feature_order: list[str], model_version: str) -> str:
    payload = {"model_version": model_version, "feature_order": feature_order}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def write_schema_snapshot(
    root: Path,
    *,
    feature_order: list[str],
    model_version: str,
    split_mode: str,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Persist offline feature schema for train/serve parity checks."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / "schema_snapshot.json"
    doc = {
        "model_version": model_version,
        "feature_order": feature_order,
        "n_features": len(feature_order),
        "split_mode": split_mode,
        "fingerprint": schema_fingerprint(feature_order, model_version),
        "store_type": "local_file_snapshot",
        "note": "Offline schema contract only — not an online feature service.",
    }
    if extra:
        doc["extra"] = extra
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def load_schema_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_serve_schema(
    snapshot: dict[str, Any], feature_order: list[str], model_version: str
) -> None:
    expected = snapshot.get("fingerprint")
    actual = schema_fingerprint(feature_order, model_version)
    if expected != actual:
        raise ValueError(
            f"Feature schema fingerprint mismatch: serve={actual} store={expected}"
        )
