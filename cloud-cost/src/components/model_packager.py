#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import secrets
import shutil
import sqlite3
import struct
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.entity.config_entity import ModelPackagerConfig
from src.exception.exception import CustomException
from src.logging.logger import logging
from src.utils.common import create_directories

REQUIRED_METRICS = {"MAE", "MSE", "RMSE", "R2"}
# Cost-model digest_ring is sealed over these four logical names only
# (descending filename order). Latency blobs are optional CAS adjuncts.
CORE_BLOB_NAMES = (
    "model.pkl",
    "metrics.json",
    "label_encoders.pkl",
    "feature_columns.json",
)
ANCHOR_CLASSES = {
    "bootstrap",
    "major_gain",
    "minor_gain",
    "schema_break_accepted",
    "stable_or_better",
}
PROBE_CLASSES = {
    "minor_gain_mae_soft",
    "r2_ok_mae_worse",
    "tradeoff_mae",
}


def _sha256_file(path: Path | str) -> str:
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _parse_version(name: str) -> tuple[int, int, int] | None:
    parts = name.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return int(parts[0]), int(parts[1]), int(parts[2])


def _object_path(bundle_root: Path, digest: str) -> Path:
    return bundle_root / "objects" / digest[:2] / digest[2:4] / digest[4:]


def _binding_mac(seal_tag: str, digest_ring: str, publish_nonce: str) -> str:
    key = hashlib.blake2b(
        publish_nonce.encode(), digest_size=16, person=b"mpip-mac"
    ).digest()
    return hmac.new(
        key, f"{seal_tag}|{digest_ring}".encode(), hashlib.sha256
    ).hexdigest()


class ModelPackager:
    def __init__(self, config: ModelPackagerConfig):
        self.config = config
        self.bundle_root = Path(self.config.root_dir)
        create_directories([self.bundle_root])
        (self.bundle_root / "objects").mkdir(parents=True, exist_ok=True)
        (self.bundle_root / "versions").mkdir(parents=True, exist_ok=True)

    def _version_dirs(self) -> list[Path]:
        versions_root = self.bundle_root / "versions"
        if not versions_root.exists():
            return []
        versions: list[tuple[tuple[int, int, int], Path]] = []
        for item in versions_root.iterdir():
            if not item.is_dir() or item.name.startswith("."):
                continue
            parsed = _parse_version(item.name)
            if parsed is not None:
                versions.append((parsed, item))
        versions.sort(key=lambda pair: pair[0])
        return [path for _, path in versions]

    def _cleanup_staging(self) -> None:
        journal = self.bundle_root / ".publish.journal"
        if journal.exists():
            journal.unlink()
        for item in self.bundle_root.iterdir():
            if item.is_dir() and item.name.startswith(".staging-"):
                shutil.rmtree(item, ignore_errors=True)
            if item.is_file() and item.name.startswith(".staging-"):
                item.unlink(missing_ok=True)
        objects = self.bundle_root / "objects"
        if objects.exists():
            for path in objects.rglob("*"):
                if path.is_file() and (
                    path.name.startswith(".staging-") or path.name.startswith(".tmp-")
                ):
                    path.unlink(missing_ok=True)

    def _remove_legacy_latest(self) -> None:
        latest = self.bundle_root / "latest"
        if latest.exists() or latest.is_symlink():
            if latest.is_symlink() or latest.is_file():
                latest.unlink()
            else:
                shutil.rmtree(latest)

    def _load_parent_manifest(self, parent: Path) -> dict:
        with open(parent / "manifest.json") as handle:
            return json.load(handle)

    def _load_parent_payload(self, parent: Path) -> tuple[dict, dict, dict]:
        manifest = self._load_parent_manifest(parent)
        metrics_digest = manifest["blobs"]["metrics.json"]["sha256"]
        features_digest = manifest["blobs"]["feature_columns.json"]["sha256"]
        with open(_object_path(self.bundle_root, metrics_digest)) as handle:
            metrics = json.load(handle)
        with open(_object_path(self.bundle_root, features_digest)) as handle:
            features = json.load(handle)
        return metrics, features, manifest

    def _decide(
        self,
        candidate_metrics: dict,
        candidate_features: dict,
    ) -> tuple[str, str | None, str, int]:
        if not REQUIRED_METRICS.issubset(candidate_metrics):
            msg = "Candidate metrics missing required keys"
            raise RuntimeError(msg)

        new_r2 = float(candidate_metrics["R2"])
        new_mae = float(candidate_metrics["MAE"])
        if new_r2 < float(self.config.r2_floor):
            msg = "Candidate R2 below r2_floor"
            raise RuntimeError(msg)
        if new_mae > float(self.config.mae_ceiling):
            msg = "Candidate MAE above mae_ceiling"
            raise RuntimeError(msg)

        existing = self._version_dirs()
        if not existing:
            return "1.0.0", None, "bootstrap", 7

        parent = existing[-1]
        parent_metrics, parent_features, parent_manifest = self._load_parent_payload(
            parent
        )
        major, minor, patch = _parse_version(parent.name)
        parent_epoch = int(parent_manifest["bundle_epoch"])

        prev_r2 = float(parent_metrics["R2"])
        prev_mae = float(parent_metrics["MAE"])
        delta_r2 = new_r2 - prev_r2
        mae_rel = (new_mae - prev_mae) / max(prev_mae, 1e-12)

        parent_order = list(parent_features["feature_order"])
        new_order = list(candidate_features["feature_order"])
        feature_break = parent_order != new_order or len(parent_order) != len(new_order)

        minor_thresh = float(self.config.r2_minor_bump_threshold)
        major_thresh = float(self.config.r2_major_bump_threshold)
        mae_tol = float(self.config.mae_regression_tolerance)
        allow_patch = bool(self.config.allow_nonimproving_patch)

        if feature_break:
            if delta_r2 >= minor_thresh and mae_rel <= mae_tol:
                return (
                    f"{major}.{minor + 1}.0",
                    parent.name,
                    "schema_break_accepted",
                    parent_epoch,
                )
            msg = "Schema break without qualifying metrics"
            raise RuntimeError(msg)

        if delta_r2 >= major_thresh and mae_rel <= 0:
            return f"{major + 1}.0.0", parent.name, "major_gain", parent_epoch + 1

        if delta_r2 >= minor_thresh and mae_rel <= 0:
            return f"{major}.{minor + 1}.0", parent.name, "minor_gain", parent_epoch

        if delta_r2 >= minor_thresh and 0 < mae_rel <= mae_tol:
            return (
                f"{major}.{minor}.{patch + 1}",
                parent.name,
                "minor_gain_mae_soft",
                parent_epoch,
            )

        if delta_r2 >= minor_thresh and mae_rel > mae_tol:
            msg = "R2 gain blocked by MAE regression beyond tolerance"
            raise RuntimeError(msg)

        if delta_r2 >= 0 and mae_rel <= 0:
            return (
                f"{major}.{minor}.{patch + 1}",
                parent.name,
                "stable_or_better",
                parent_epoch,
            )

        if delta_r2 >= 0 and mae_rel > 0:
            if allow_patch:
                return (
                    f"{major}.{minor}.{patch + 1}",
                    parent.name,
                    "r2_ok_mae_worse",
                    parent_epoch,
                )
            msg = "Non-improving MAE patch disabled"
            raise RuntimeError(msg)

        if delta_r2 < 0 and mae_rel < 0:
            if allow_patch:
                return (
                    f"{major}.{minor}.{patch + 1}",
                    parent.name,
                    "tradeoff_mae",
                    parent_epoch,
                )
            msg = "Tradeoff patch disabled"
            raise RuntimeError(msg)

        msg = "Dual metric regression refused"
        raise RuntimeError(msg)

    def _store_blob(self, data: bytes, digest: str | None = None) -> tuple[str, int]:
        if digest is None:
            digest = hashlib.sha256(data).hexdigest()
        dest = _object_path(self.bundle_root, digest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if dest.read_bytes() != data:
                msg = f"CAS collision for {digest}"
                raise RuntimeError(msg)
            return digest, len(data)
        tmp = dest.parent / f".tmp-{digest[4:]}"
        tmp.write_bytes(data)
        os.replace(tmp, dest)
        return digest, len(data)

    def _store_file_blob(self, src: Path) -> tuple[str, int]:
        digest = _sha256_file(src)
        data = Path(src).read_bytes()
        return self._store_blob(data, digest=digest)

    def _write_catalog(self) -> None:
        catalog_path = self.bundle_root / "catalog.sqlite"
        if catalog_path.exists():
            catalog_path.unlink()
        conn = sqlite3.connect(catalog_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                CREATE TABLE packages (
                    version TEXT PRIMARY KEY,
                    parent_version TEXT,
                    created_at TEXT NOT NULL,
                    promotion_class TEXT NOT NULL,
                    bundle_epoch INTEGER NOT NULL,
                    r2 REAL NOT NULL,
                    mae REAL NOT NULL,
                    digest_ring TEXT NOT NULL,
                    lineage_token TEXT NOT NULL,
                    seal_tag TEXT NOT NULL,
                    publish_nonce TEXT NOT NULL,
                    binding_mac TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE blobs (
                    sha256 TEXT PRIMARY KEY,
                    logical_name TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    first_seen_version TEXT NOT NULL
                )
                """
            )
            first_seen: dict[str, tuple[str, str, int]] = {}
            for version_dir in self._version_dirs():
                with open(version_dir / "manifest.json") as handle:
                    manifest = json.load(handle)
                metrics_digest = manifest["blobs"]["metrics.json"]["sha256"]
                with open(_object_path(self.bundle_root, metrics_digest)) as handle:
                    metrics = json.load(handle)
                conn.execute(
                    """
                    INSERT INTO packages (
                        version, parent_version, created_at, promotion_class,
                        bundle_epoch, r2, mae, digest_ring, lineage_token,
                        seal_tag, publish_nonce, binding_mac
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version_dir.name,
                        manifest["parent_version"],
                        manifest["created_at"],
                        manifest["promotion_class"],
                        int(manifest["bundle_epoch"]),
                        float(metrics["R2"]),
                        float(metrics["MAE"]),
                        manifest["digest_ring"],
                        manifest["lineage_token"],
                        manifest["seal_tag"],
                        manifest["publish_nonce"],
                        manifest["binding_mac"],
                    ),
                )
                for logical_name, meta in manifest["blobs"].items():
                    digest = meta["sha256"]
                    if digest not in first_seen:
                        first_seen[digest] = (
                            logical_name,
                            version_dir.name,
                            int(meta["size"]),
                        )
            for digest, (logical_name, first_version, size) in first_seen.items():
                conn.execute(
                    """
                    INSERT INTO blobs (sha256, logical_name, size, first_seen_version)
                    VALUES (?, ?, ?, ?)
                    """,
                    (digest, logical_name, size, first_version),
                )
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            conn.close()

    def _update_pins_and_head(self, version: str, promotion_class: str) -> None:
        pins_path = self.bundle_root / "pins.json"
        if pins_path.exists():
            pins = json.loads(pins_path.read_text(encoding="utf-8"))
        else:
            pins = {"anchor": None, "probe": None}

        if promotion_class in ANCHOR_CLASSES:
            pins = {"anchor": version, "probe": None}
        elif promotion_class in PROBE_CLASSES:
            pins["probe"] = version
        else:
            msg = f"Unknown promotion_class {promotion_class}"
            raise RuntimeError(msg)

        active = pins["probe"] if pins["probe"] is not None else pins["anchor"]
        pins_tmp = self.bundle_root / ".staging-pins.json"
        pins_tmp.write_text(
            json.dumps(pins, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(pins_tmp, pins_path)

        head_tmp = self.bundle_root / ".staging-HEAD"
        head_tmp.write_text(f"{active}\n", encoding="utf-8")
        os.replace(head_tmp, self.bundle_root / "HEAD")

    def _append_releases(
        self,
        version: str,
        promotion_class: str,
        digest_ring: str,
        lineage_token: str,
        publish_nonce: str,
        binding_mac: str,
    ) -> None:
        releases = self.bundle_root / "RELEASES"
        epoch_ms = int(time.time() * 1000)
        with releases.open("a", encoding="utf-8") as handle:
            handle.write(
                f"{epoch_ms} {version} {promotion_class} {digest_ring} "
                f"{lineage_token} {publish_nonce} {binding_mac}\n"
            )

    def _write_journal(self, version: str) -> Path:
        journal = self.bundle_root / ".publish.journal"
        fd = os.open(str(journal), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, f"{version}\n".encode())
        finally:
            os.close(fd)
        return journal

    def initiate_packaging(self) -> str:
        lock_path = self.bundle_root / ".publish.lock"
        lock_path.touch(exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                return self._publish_locked()
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _publish_locked(self) -> str:
        try:
            logging.info("Starting model packaging...")
            self._cleanup_staging()

            with open(self.config.metrics_path) as handle:
                metrics = json.load(handle)
            with open(self.config.feature_schema_path) as handle:
                feature_schema = json.load(handle)

            model_version, parent_version, promotion_class, bundle_epoch = self._decide(
                metrics, feature_schema
            )

            journal = self._write_journal(model_version)

            blob_inventory: dict[str, dict[str, str | int]] = {}
            for logical_name, src in (
                ("model.pkl", self.config.model_path),
                ("label_encoders.pkl", self.config.label_encoders_path),
                ("metrics.json", self.config.metrics_path),
            ):
                digest, size = self._store_file_blob(Path(src))
                blob_inventory[logical_name] = {"sha256": digest, "size": size}

            feature_payload = {
                "feature_order": list(feature_schema["feature_order"]),
                "n_features": len(feature_schema["feature_order"]),
                "model_version": model_version,
            }
            feature_bytes = json.dumps(feature_payload, indent=2).encode("utf-8")
            digest, size = self._store_blob(feature_bytes)
            blob_inventory["feature_columns.json"] = {"sha256": digest, "size": size}

            # Optional latency adjuncts (same version; not part of cost digest_ring).
            for logical_name, src in (
                ("latency_model.pkl", self.config.latency_model_path),
                (
                    "latency_feature_columns.json",
                    self.config.latency_feature_schema_path,
                ),
                ("latency_metrics.json", self.config.latency_metrics_path),
            ):
                if not src:
                    continue
                path = Path(src)
                if not path.is_file():
                    logging.warning("Optional latency blob missing: %s", path)
                    continue
                if logical_name.endswith(".json"):
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if logical_name == "latency_feature_columns.json":
                        payload = {
                            **payload,
                            "model_version": model_version,
                        }
                    digest, size = self._store_blob(
                        json.dumps(payload, indent=2).encode("utf-8")
                    )
                else:
                    digest, size = self._store_file_blob(path)
                blob_inventory[logical_name] = {"sha256": digest, "size": size}

            missing_core = [n for n in CORE_BLOB_NAMES if n not in blob_inventory]
            if missing_core:
                msg = f"Missing core CAS blobs: {missing_core}"
                raise RuntimeError(msg)

            digest_bytes = struct.pack(">I", int(bundle_epoch)) + b"".join(
                bytes.fromhex(str(blob_inventory[name]["sha256"]))
                for name in CORE_BLOB_NAMES
            )
            digest_ring = hashlib.blake2b(
                digest_bytes, digest_size=32, person=b"mpip-ring"
            ).hexdigest()
            parent_key = parent_version if parent_version is not None else "ROOT"
            lineage_token = hashlib.sha256(
                f"{parent_key}|{model_version}|{digest_ring}".encode()
            ).hexdigest()
            seal_tag = hashlib.blake2b(
                lineage_token.encode(), digest_size=16, person=b"mpip-seal"
            ).hexdigest()
            publish_nonce = secrets.token_hex(8)
            binding_mac = _binding_mac(seal_tag, digest_ring, publish_nonce)

            created_at_dt = datetime.now(UTC)
            if parent_version is not None:
                parent_manifest = self._load_parent_manifest(
                    self.bundle_root / "versions" / parent_version
                )
                parent_created = datetime.fromisoformat(
                    parent_manifest["created_at"].replace("Z", "+00:00")
                )
                if created_at_dt <= parent_created:
                    created_at_dt = parent_created + timedelta(microseconds=1)
            created_at = created_at_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            manifest = {
                "model_version": model_version,
                "parent_version": parent_version,
                "created_at": created_at,
                "promotion_class": promotion_class,
                "bundle_epoch": bundle_epoch,
                "blobs": blob_inventory,
                "digest_ring": digest_ring,
                "lineage_token": lineage_token,
                "seal_tag": seal_tag,
                "publish_nonce": publish_nonce,
                "binding_mac": binding_mac,
            }

            staging = self.bundle_root / f".staging-{model_version}"
            if staging.exists():
                shutil.rmtree(staging)
            staging.mkdir(parents=True)
            with open(staging / "manifest.json", "w") as handle:
                json.dump(manifest, handle, indent=2)

            final_dir = self.bundle_root / "versions" / model_version
            if final_dir.exists():
                msg = f"Refusing to overwrite existing package {model_version}"
                raise RuntimeError(msg)
            os.replace(staging, final_dir)

            self._append_releases(
                model_version,
                promotion_class,
                digest_ring,
                lineage_token,
                publish_nonce,
                binding_mac,
            )
            self._write_catalog()
            self._update_pins_and_head(model_version, promotion_class)
            if journal.exists():
                journal.unlink()
            self._remove_legacy_latest()
            self._cleanup_staging()

            logging.info(f"Model packaging completed. Bundle at: {final_dir}")
            return str(final_dir)
        except Exception as e:
            self._cleanup_staging()
            raise CustomException(e, sys) from e
