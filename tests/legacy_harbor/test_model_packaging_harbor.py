#!/usr/bin/env python3
import ast
import dataclasses
import fcntl
import hashlib
import hmac
import importlib
import json
import os
import pickle
import shutil
import sqlite3
import subprocess
import sys
import unittest.mock
from contextlib import contextmanager
from datetime import datetime
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path("/app/cloud-cost")
SRC = PROJECT_ROOT / "src"
ARTIFACTS = PROJECT_ROOT / "artifacts"
MODEL_BUNDLE = ARTIFACTS / "model_bundle"
VERSIONS = MODEL_BUNDLE / "versions"
OBJECTS = MODEL_BUNDLE / "objects"

COMPONENT = SRC / "components"
PIPELINE = SRC / "pipeline"
MAIN = PROJECT_ROOT / "main.py"

BLOB_NAMES = {
    "feature_columns.json",
    "label_encoders.pkl",
    "metrics.json",
    "model.pkl",
}

CONFIG_FIELDS = {
    "root_dir",
    "model_path",
    "label_encoders_path",
    "feature_schema_path",
    "metrics_path",
    "r2_minor_bump_threshold",
    "r2_major_bump_threshold",
    "mae_regression_tolerance",
    "r2_floor",
    "mae_ceiling",
    "allow_nonimproving_patch",
}

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


@contextmanager
def project_cwd():
    """Run code with cwd set to the cloud-cost project root."""
    previous = Path.cwd()
    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    try:
        yield
    finally:
        os.chdir(previous)


def sha256_file(path: Path) -> str:
    """Return lowercase hex SHA-256 of a file's bytes."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def object_path(digest: str) -> Path:
    """Three-level CAS path: objects/<aa>/<bb>/<rest>."""
    return OBJECTS / digest[:2] / digest[2:4] / digest[4:]


def parse_version(name: str):
    """Parse MAJOR.MINOR.PATCH into an int tuple, or None if invalid."""
    parts = name.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return tuple(map(int, parts))


def get_version_dirs():
    """Return promoted version directories under versions/, sorted by semver."""
    if not VERSIONS.exists():
        return []
    versions = []
    for path in VERSIONS.iterdir():
        if not path.is_dir() or path.name.startswith("."):
            continue
        if parse_version(path.name) is not None:
            versions.append(path)
    return sorted(versions, key=lambda p: parse_version(p.name))


def version_dirs():
    """Return promoted version directory names in ascending semver order."""
    return [d.name for d in get_version_dirs()]


def read_head() -> str:
    """Read the raw HEAD file contents (including trailing newline)."""
    return (MODEL_BUNDLE / "HEAD").read_text(encoding="utf-8")


def read_pins() -> dict:
    """Load pins.json serving-channel state."""
    with open(MODEL_BUNDLE / "pins.json", encoding="utf-8") as handle:
        return json.load(handle)


def active_channel(pins: dict) -> str:
    """Resolve active inference channel: probe if set, otherwise anchor."""
    return pins["probe"] if pins["probe"] is not None else pins["anchor"]


def load_manifest(version_dir: Path) -> dict:
    """Load a version's manifest.json model card."""
    with open(version_dir / "manifest.json") as handle:
        return json.load(handle)


def load_blob_json(digest: str) -> dict:
    """Load and parse a JSON blob from the three-level objects store."""
    with open(object_path(digest)) as handle:
        return json.load(handle)


def expected_binding_mac(seal_tag: str, digest_ring: str, publish_nonce: str) -> str:
    """Recompute binding_mac from seal_tag, digest_ring, and publish_nonce."""
    key = hashlib.blake2b(
        publish_nonce.encode(), digest_size=16, person=b"mpip-mac"
    ).digest()
    return hmac.new(
        key, f"{seal_tag}|{digest_ring}".encode(), hashlib.sha256
    ).hexdigest()


def current_packager_config():
    """Return ModelPackagerConfig from ConfigurationManager."""
    with project_cwd():
        configuration_module = importlib.import_module("src.config.configuration")
        importlib.reload(configuration_module)
        return configuration_module.ConfigurationManager().get_model_packager_config()


def make_probe_sources(tag: str, metrics: dict, feature_schema: dict | None = None):
    """Create temporary source artifacts with custom metrics for promotion probes."""
    custom_root = ARTIFACTS / f"_{tag}_sources"
    if custom_root.exists():
        shutil.rmtree(custom_root)
    custom_root.mkdir(parents=True)
    custom_model = custom_root / "model.pkl"
    custom_encoders = custom_root / "encoders.pkl"
    custom_features = custom_root / "features.json"
    custom_metrics = custom_root / "metrics.json"
    shutil.copy2(ARTIFACTS / "model_trainer" / "model.pkl", custom_model)
    shutil.copy2(
        ARTIFACTS / "data_transformation" / "label_encoders.pkl",
        custom_encoders,
    )
    if feature_schema is None:
        shutil.copy2(
            ARTIFACTS / "data_transformation" / "feature_columns.json",
            custom_features,
        )
    else:
        with open(custom_features, "w") as handle:
            json.dump(feature_schema, handle)
    with open(custom_metrics, "w") as handle:
        json.dump(metrics, handle)
    return custom_root, custom_model, custom_encoders, custom_features, custom_metrics


def pack_with_config(model, encoders, features, metrics, **overrides):
    """Run initiate_packaging with a ModelPackagerConfig built from probe paths."""
    with project_cwd():
        entity_module = importlib.import_module("src.entity.config_entity")
        importlib.reload(entity_module)
        packager_module = importlib.import_module("src.components.model_packager")
        importlib.reload(packager_module)
        base = current_packager_config()
        kwargs = {
            "root_dir": MODEL_BUNDLE,
            "model_path": model,
            "label_encoders_path": encoders,
            "feature_schema_path": features,
            "metrics_path": metrics,
            "r2_minor_bump_threshold": float(base.r2_minor_bump_threshold),
            "r2_major_bump_threshold": float(base.r2_major_bump_threshold),
            "mae_regression_tolerance": float(base.mae_regression_tolerance),
            "r2_floor": float(base.r2_floor),
            "mae_ceiling": float(base.mae_ceiling),
            "allow_nonimproving_patch": bool(base.allow_nonimproving_patch),
        }
        kwargs.update(overrides)
        config = entity_module.ModelPackagerConfig(**kwargs)
        return packager_module.ModelPackager(config=config).initiate_packaging()


def rebuild_catalog_from_disk():
    """Rebuild catalog.sqlite from on-disk manifests after a probe rollback."""
    catalog = MODEL_BUNDLE / "catalog.sqlite"
    if catalog.exists():
        catalog.unlink()
    conn = sqlite3.connect(catalog)
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
        first_seen = {}
        for version_dir in get_version_dirs():
            manifest = load_manifest(version_dir)
            metrics = load_blob_json(manifest["blobs"]["metrics.json"]["sha256"])
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
                    first_seen[digest] = (logical_name, version_dir.name, int(meta["size"]))
        for digest, (logical_name, first_version, size) in first_seen.items():
            conn.execute(
                "INSERT INTO blobs (sha256, logical_name, size, first_seen_version) "
                "VALUES (?, ?, ?, ?)",
                (digest, logical_name, size, first_version),
            )
        conn.commit()
    finally:
        conn.close()


def restore_head(version_name: str):
    """Rewrite HEAD to point at version_name after a probe rollback."""
    head = MODEL_BUNDLE / "HEAD"
    tmp = MODEL_BUNDLE / ".staging-HEAD-restore"
    tmp.write_text(f"{version_name}\n", encoding="utf-8")
    os.replace(tmp, head)


def _restore_bundle_after_probe(before, previous_latest_name, custom_root, pins_before, releases_before):
    """Remove probe versions and restore pins, RELEASES, HEAD, and catalog."""
    after = version_dirs()
    for name in set(after) - set(before):
        shutil.rmtree(VERSIONS / name, ignore_errors=True)
    (MODEL_BUNDLE / "pins.json").write_text(
        json.dumps(pins_before, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (MODEL_BUNDLE / "RELEASES").write_text(releases_before, encoding="utf-8")
    restore_head(previous_latest_name)
    rebuild_catalog_from_disk()
    if custom_root.exists():
        shutil.rmtree(custom_root)


def snapshot_store():
    """Capture version list, HEAD target, pins, and RELEASES for later restore."""
    return (
        version_dirs(),
        get_version_dirs()[-1].name,
        read_pins(),
        (MODEL_BUNDLE / "RELEASES").read_text(encoding="utf-8"),
    )


def test_model_packager_component_exists():
    """Verify the model packager component module exists on disk."""
    path = COMPONENT / "model_packager.py"
    assert path.exists(), f"{path} does not exist."


def test_model_packaging_pipeline_exists():
    """Verify ModelPackagingPipeline exposes initiate_model_packaging()."""
    path = PIPELINE / "model_packaging_pipeline.py"
    assert path.exists(), f"{path} does not exist."

    with project_cwd():
        pipeline_module = importlib.import_module("src.pipeline.model_packaging_pipeline")
        importlib.reload(pipeline_module)
        assert hasattr(pipeline_module, "ModelPackagingPipeline")
        assert hasattr(pipeline_module.ModelPackagingPipeline, "initiate_model_packaging")


def test_model_packager_exposes_initiate_packaging():
    """Verify ModelPackager exposes initiate_packaging()."""
    with project_cwd():
        packager_module = importlib.import_module("src.components.model_packager")
        importlib.reload(packager_module)
        assert hasattr(packager_module, "ModelPackager")
        assert hasattr(packager_module.ModelPackager, "initiate_packaging")


def test_model_packager_configuration_section_exists():
    """Verify model_packager YAML includes every promotion gate field with required defaults."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    assert "model_packager" in config
    section = config["model_packager"]
    assert section["r2_minor_bump_threshold"] == 0.05
    assert section["r2_major_bump_threshold"] == 0.15
    assert section["mae_regression_tolerance"] == 0.05
    assert float(section["r2_floor"]) == 0.0
    assert float(section["mae_ceiling"]) == 1.0e9
    assert section["allow_nonimproving_patch"] is True


def test_missing_metric_keys_refuse():
    """Verify packaging refuses when MAE/MSE/RMSE/R2 are incomplete."""
    newest = get_version_dirs()[-1]
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    probe = {"MAE": baseline["MAE"], "R2": baseline["R2"], "source": "missing_keys"}
    custom_root, model, encoders, features, metrics = make_probe_sources(
        "missing_keys", probe
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        with project_cwd():
            exception_module = importlib.import_module("src.exception.exception")
            raised = False
            try:
                pack_with_config(model, encoders, features, metrics)
            except exception_module.CustomException:
                raised = True
            assert raised
        assert version_dirs() == before
        assert read_pins() == pins_before
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_configuration_manager_provides_packager_config():
    """Verify ConfigurationManager returns a populated ModelPackagerConfig."""
    with project_cwd():
        entity_module = importlib.import_module("src.entity.config_entity")
        importlib.reload(entity_module)
        configuration_module = importlib.import_module("src.config.configuration")
        importlib.reload(configuration_module)

        manager = configuration_module.ConfigurationManager()
        assert hasattr(manager, "get_model_packager_config")
        packager_config = manager.get_model_packager_config()

        assert hasattr(entity_module, "ModelPackagerConfig")
        assert dataclasses.is_dataclass(entity_module.ModelPackagerConfig)
        assert isinstance(packager_config, entity_module.ModelPackagerConfig)
        for field in CONFIG_FIELDS:
            assert getattr(packager_config, field) is not None


def test_artifacts_directory_exists():
    """Verify the artifacts root directory exists."""
    assert ARTIFACTS.exists()


def test_existing_artifacts_exist():
    """Verify training-stage artifact directories remain after packaging."""
    assert (ARTIFACTS / "data_transformation").exists()
    assert (ARTIFACTS / "data_validation").exists()
    assert (ARTIFACTS / "model_evaluation").exists()
    assert (ARTIFACTS / "model_trainer").exists()


def test_model_bundle_exists():
    """Verify artifacts/model_bundle exists as a directory."""
    assert MODEL_BUNDLE.exists()
    assert MODEL_BUNDLE.is_dir()


def test_at_least_one_package_exists():
    """Verify at least one semver directory exists under versions/."""
    assert len(get_version_dirs()) > 0


def test_head_is_regular_file_with_newline():
    """Verify HEAD is a regular file ending with a newline active-channel version."""
    head = MODEL_BUNDLE / "HEAD"
    assert head.exists()
    assert head.is_file()
    assert not head.is_symlink()
    text = head.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.strip() == active_channel(read_pins())


def test_legacy_latest_pointer_removed():
    """Verify migration leftover latest pointer is removed after publish."""
    assert not (MODEL_BUNDLE / "latest").exists()
    assert not (MODEL_BUNDLE / "latest").is_symlink()


def test_version_dirs_live_under_versions():
    """Verify semver directories are not placed flat under model_bundle/."""
    for path in MODEL_BUNDLE.iterdir():
        if path.is_dir() and parse_version(path.name) is not None:
            raise AssertionError(
                f"flat version directory {path.name} must live under versions/"
            )


def test_version_directory_contains_only_manifest():
    """Verify each version directory contains only manifest.json."""
    for version in get_version_dirs():
        entries = [p.name for p in version.iterdir()]
        assert entries == ["manifest.json"], f"{version.name} entries={entries}"


def test_cas_blobs_use_three_level_paths():
    """Verify every manifest blob resolves under objects/<aa>/<bb>/<rest>."""
    for version in get_version_dirs():
        manifest = load_manifest(version)
        assert set(manifest["blobs"]) == BLOB_NAMES
        for name, meta in manifest["blobs"].items():
            digest = meta["sha256"]
            path = object_path(digest)
            assert path.is_file(), f"missing CAS blob for {version.name}/{name}"
            assert path.parts[-3] == digest[:2]
            assert path.parts[-2] == digest[2:4]
            assert path.name == digest[4:]
            assert path.stat().st_size == int(meta["size"])
            assert sha256_file(path) == digest


def test_catalog_sqlite_wal_and_schema():
    """Verify catalog.sqlite WAL mode and packages/blobs rows match the store."""
    catalog = MODEL_BUNDLE / "catalog.sqlite"
    assert catalog.exists()
    conn = sqlite3.connect(catalog)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert str(mode).lower() == "wal"
        packages = conn.execute(
            "SELECT version, parent_version, created_at, promotion_class, "
            "bundle_epoch, r2, mae, digest_ring, lineage_token, seal_tag, "
            "publish_nonce, binding_mac FROM packages ORDER BY version"
        ).fetchall()
        versions = get_version_dirs()
        assert [row[0] for row in packages] == [v.name for v in versions]
        for row, version_dir in zip(packages, versions, strict=True):
            manifest = load_manifest(version_dir)
            metrics = load_blob_json(manifest["blobs"]["metrics.json"]["sha256"])
            assert row[1] == manifest["parent_version"]
            assert row[2] == manifest["created_at"]
            assert row[3] == manifest["promotion_class"]
            assert row[4] == manifest["bundle_epoch"]
            assert row[5] == metrics["R2"]
            assert row[6] == metrics["MAE"]
            assert row[7] == manifest["digest_ring"]
            assert row[8] == manifest["lineage_token"]
            assert row[9] == manifest["seal_tag"]
            assert row[10] == manifest["publish_nonce"]
            assert row[11] == manifest["binding_mac"]
        blob_rows = conn.execute(
            "SELECT sha256, logical_name, size, first_seen_version FROM blobs"
        ).fetchall()
        assert blob_rows
        for digest, logical_name, size, first_seen in blob_rows:
            assert object_path(digest).is_file()
            assert parse_version(first_seen) is not None
            assert isinstance(logical_name, str)
            assert int(size) == object_path(digest).stat().st_size
    finally:
        conn.close()


def test_catalog_rebuilds_from_scratch_each_publish():
    """Verify each publish deletes and recreates catalog.sqlite (not incremental)."""
    catalog = MODEL_BUNDLE / "catalog.sqlite"
    conn = sqlite3.connect(catalog)
    try:
        conn.execute("CREATE TABLE poison_marker (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO poison_marker(id) VALUES (1)")
        conn.commit()
    finally:
        conn.close()

    with project_cwd():
        configuration_module = importlib.import_module("src.config.configuration")
        importlib.reload(configuration_module)
        packager_module = importlib.import_module("src.components.model_packager")
        importlib.reload(packager_module)
        config = configuration_module.ConfigurationManager().get_model_packager_config()
        packager_module.ModelPackager(config=config).initiate_packaging()

    conn = sqlite3.connect(catalog)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "poison_marker" not in tables
        assert "packages" in tables
        assert "blobs" in tables
    finally:
        conn.close()


def test_publish_commit_order_releases_catalog_then_pins():
    """Verify the post-gate filesystem publish sequence from the store contract."""
    events: list[str] = []
    real_path_open = Path.open
    real_unlink = Path.unlink
    real_replace = os.replace
    real_os_open = os.open
    real_mkdir = Path.mkdir

    def tracing_path_open(self, mode="r", *args, **kwargs):
        if self.name == "RELEASES" and "a" in str(mode):
            events.append("releases")
        return real_path_open(self, mode, *args, **kwargs)

    def tracing_unlink(self, *args, **kwargs):
        if self.name == "catalog.sqlite":
            events.append("catalog_unlink")
        if self.name == ".publish.journal":
            events.append("journal_clear")
        return real_unlink(self, *args, **kwargs)

    def tracing_replace(src, dst, *args, **kwargs):
        dst_path = Path(dst)
        if dst_path.parent.name == "versions" and parse_version(dst_path.name):
            events.append("version_replace")
        if dst_path.name == "pins.json":
            events.append("pins")
        if dst_path.name == "HEAD":
            events.append("head")
        return real_replace(src, dst, *args, **kwargs)

    def tracing_os_open(path, flags, *args, **kwargs):
        path_name = Path(path).name
        if path_name == ".publish.journal":
            assert flags & os.O_CREAT
            assert flags & os.O_EXCL
            assert flags & os.O_WRONLY
            events.append("journal_create")
        return real_os_open(path, flags, *args, **kwargs)

    def tracing_mkdir(self, *args, **kwargs):
        if self.name.startswith(".staging-"):
            events.append("staging_mkdir")
        return real_mkdir(self, *args, **kwargs)

    with project_cwd():
        configuration_module = importlib.import_module("src.config.configuration")
        importlib.reload(configuration_module)
        packager_module = importlib.import_module("src.components.model_packager")
        importlib.reload(packager_module)
        config = configuration_module.ConfigurationManager().get_model_packager_config()

        with (
            unittest.mock.patch.object(Path, "open", tracing_path_open),
            unittest.mock.patch.object(Path, "unlink", tracing_unlink),
            unittest.mock.patch.object(Path, "mkdir", tracing_mkdir),
            unittest.mock.patch.object(os, "replace", side_effect=tracing_replace),
            unittest.mock.patch.object(os, "open", side_effect=tracing_os_open),
        ):
            packager_module.ModelPackager(config=config).initiate_packaging()

    required = [
        "journal_create",
        "staging_mkdir",
        "version_replace",
        "releases",
        "catalog_unlink",
        "pins",
        "head",
        "journal_clear",
    ]
    positions = []
    for name in required:
        assert name in events, f"missing step {name} in {events}"
        positions.append(events.index(name))
    assert positions == sorted(positions), f"out of order: {events}"



def test_pins_json_matches_promotion_classes():
    """Verify pins.json anchor/probe rules and HEAD active-channel binding."""
    pins = read_pins()
    assert "anchor" in pins and "probe" in pins
    assert pins["anchor"] is not None
    assert read_head().strip() == active_channel(pins)
    newest = get_version_dirs()[-1]
    newest_class = load_manifest(newest)["promotion_class"]
    if newest_class in ANCHOR_CLASSES:
        assert pins["anchor"] == newest.name
        assert pins["probe"] is None
    elif newest_class in PROBE_CLASSES:
        assert pins["probe"] == newest.name


def test_releases_append_only_ledger():
    """Verify RELEASES has one immutable space-delimited line per published version."""
    releases = MODEL_BUNDLE / "RELEASES"
    assert releases.exists()
    lines = releases.read_text(encoding="utf-8").splitlines()
    versions = get_version_dirs()
    assert len(lines) == len(versions)
    for line, version_dir in zip(lines, versions, strict=True):
        parts = line.split(" ")
        assert len(parts) == 7
        epoch_ms, ver, promo, merkle, lineage, nonce, mac = parts
        assert epoch_ms.isdigit()
        assert ver == version_dir.name
        manifest = load_manifest(version_dir)
        assert promo == manifest["promotion_class"]
        assert merkle == manifest["digest_ring"]
        assert lineage == manifest["lineage_token"]
        assert nonce == manifest["publish_nonce"]
        assert mac == manifest["binding_mac"]


def test_releases_append_uses_pathlib_open():
    """Verify RELEASES appends go through pathlib.Path.open, not builtin open()."""
    source = (SRC / "components" / "model_packager.py").read_text(encoding="utf-8")
    assert "RELEASES" in source
    assert '.open("a"' in source or ".open('a'" in source


def test_no_staging_directories_remain():
    """Verify successful publishes leave no .staging-* paths behind."""
    leftovers = [
        p.name
        for p in MODEL_BUNDLE.iterdir()
        if (p.is_dir() or p.is_file()) and p.name.startswith(".staging-")
    ]
    assert not leftovers, f"Leftover staging paths: {leftovers}"


def test_publish_lock_file_exists():
    """Verify .publish.lock exists after packaging."""
    assert (MODEL_BUNDLE / ".publish.lock").exists()


def test_packager_imports_fcntl_at_module_level():
    """Verify model_packager.py uses `import fcntl` at module level."""
    source = (COMPONENT / "model_packager.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    has_import_fcntl = any(
        isinstance(node, ast.Import)
        and any(alias.name == "fcntl" for alias in node.names)
        for node in tree.body
    )
    assert has_import_fcntl, "model_packager.py must use `import fcntl` at module level"


def test_publish_acquires_exclusive_flock():
    """Verify initiate_packaging takes a blocking exclusive flock on .publish.lock."""
    lock_path = MODEL_BUNDLE / ".publish.lock"
    with project_cwd():
        configuration_module = importlib.import_module("src.config.configuration")
        importlib.reload(configuration_module)
        packager_module = importlib.import_module("src.components.model_packager")
        importlib.reload(packager_module)

        config = configuration_module.ConfigurationManager().get_model_packager_config()
        ops: list[int] = []
        contested: list[bool] = []
        real_flock = fcntl.flock
        nonblocking = fcntl.LOCK_EX | fcntl.LOCK_NB

        def tracking_flock(fd, operation):
            ops.append(operation)
            result = real_flock(fd, operation)
            if operation == fcntl.LOCK_EX:
                with lock_path.open("a+", encoding="utf-8") as probe:
                    try:
                        real_flock(probe.fileno(), nonblocking)
                        contested.append(False)
                        real_flock(probe.fileno(), fcntl.LOCK_UN)
                    except BlockingIOError:
                        contested.append(True)
            return result

        with unittest.mock.patch.object(packager_module.fcntl, "flock", side_effect=tracking_flock):
            packager_module.ModelPackager(config=config).initiate_packaging()

        assert fcntl.LOCK_EX in ops, f"expected blocking LOCK_EX, got {ops}"
        assert nonblocking not in ops, "hold must use LOCK_EX, not LOCK_EX|LOCK_NB"
        assert contested and contested[0], "exclusive lock must block concurrent LOCK_NB"


def test_packager_uses_objects_store_and_sqlite_catalog():
    """Verify packaging produced a three-level objects store and a WAL catalog.sqlite."""
    assert OBJECTS.exists()
    assert (MODEL_BUNDLE / "catalog.sqlite").exists()
    conn = sqlite3.connect(MODEL_BUNDLE / "catalog.sqlite")
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert str(mode).lower() == "wal"
    finally:
        conn.close()
    # At least one blob path must be three levels under objects/
    blob_files = [p for p in OBJECTS.rglob("*") if p.is_file()]
    assert blob_files
    sample = blob_files[0]
    assert sample.relative_to(OBJECTS).parts.__len__() == 3


def test_initiate_packaging_promotes_from_staging_directory():
    """Verify staging uses Path.mkdir on .staging-<version> before os.replace publish."""
    with project_cwd():
        configuration_module = importlib.import_module("src.config.configuration")
        importlib.reload(configuration_module)
        packager_module = importlib.import_module("src.components.model_packager")
        importlib.reload(packager_module)

        config = configuration_module.ConfigurationManager().get_model_packager_config()
        before = set(version_dirs())
        created_staging = []
        original_mkdir = Path.mkdir

        def watching_mkdir(self, *args, **kwargs):
            if self.name.startswith(".staging-"):
                created_staging.append(self.name)
            return original_mkdir(self, *args, **kwargs)

        with unittest.mock.patch.object(Path, "mkdir", watching_mkdir):
            packager_module.ModelPackager(config=config).initiate_packaging()
        after = set(version_dirs())
        new_versions = after - before
        assert len(new_versions) == 1
        new_version = next(iter(new_versions))
        assert any(
            name == f".staging-{new_version}" for name in created_staging
        ), (
            f"expected Path.mkdir on .staging-{new_version} during publish, "
            f"got {created_staging}"
        )
        assert not [
            p.name
            for p in MODEL_BUNDLE.iterdir()
            if p.name.startswith(".staging-")
        ]


def test_manifest_contains_required_fields():
    """Verify manifests include required promotion metadata fields."""
    required = {
        "model_version",
        "parent_version",
        "created_at",
        "promotion_class",
        "bundle_epoch",
        "blobs",
        "digest_ring",
        "lineage_token",
        "seal_tag",
        "publish_nonce",
        "binding_mac",
    }
    for version in get_version_dirs():
        manifest = load_manifest(version)
        assert not (required - manifest.keys())


def test_manifest_digest_ring_uses_descending_filenames():
    """Verify digest_ring is blake2b(person=mpip-ring) over epoch + raw digests."""
    import struct

    for version in get_version_dirs():
        manifest = load_manifest(version)
        names = sorted(manifest["blobs"], reverse=True)
        joined = struct.pack(">I", int(manifest["bundle_epoch"])) + b"".join(
            bytes.fromhex(manifest["blobs"][name]["sha256"]) for name in names
        )
        expected = hashlib.blake2b(
            joined, digest_size=32, person=b"mpip-ring"
        ).hexdigest()
        assert manifest["digest_ring"] == expected


def test_manifest_lineage_token():
    """Verify lineage_token binds parent, version, and digest_ring."""
    for version in get_version_dirs():
        manifest = load_manifest(version)
        parent_key = (
            manifest["parent_version"]
            if manifest["parent_version"] is not None
            else "ROOT"
        )
        expected = hashlib.sha256(
            f"{parent_key}|{manifest['model_version']}|{manifest['digest_ring']}".encode()
        ).hexdigest()
        assert manifest["lineage_token"] == expected


def test_manifest_seal_tag_and_publish_nonce():
    """Verify seal_tag and publish_nonce match the store contract."""
    for version in get_version_dirs():
        manifest = load_manifest(version)
        expected_seal = hashlib.blake2b(
            manifest["lineage_token"].encode(), digest_size=16, person=b"mpip-seal"
        ).hexdigest()
        assert manifest["seal_tag"] == expected_seal
        assert isinstance(manifest["publish_nonce"], str)
        assert len(manifest["publish_nonce"]) == 16
        assert all(ch in "0123456789abcdef" for ch in manifest["publish_nonce"])


def test_manifest_binding_mac():
    """Verify binding_mac is HMAC-SHA256 over seal_tag|digest_ring with blake2b key."""
    for version in get_version_dirs():
        manifest = load_manifest(version)
        assert manifest["binding_mac"] == expected_binding_mac(
            manifest["seal_tag"],
            manifest["digest_ring"],
            manifest["publish_nonce"],
        )


def test_publish_journal_absent_after_success():
    """Verify .publish.journal is not left behind after a successful publish."""
    assert not (MODEL_BUNDLE / ".publish.journal").exists()


def test_journal_created_with_o_excl():
    """Verify .publish.journal is created with O_CREAT|O_EXCL|O_WRONLY."""
    source = (SRC / "components" / "model_packager.py").read_text(encoding="utf-8")
    assert "O_EXCL" in source
    assert "O_CREAT" in source
    assert ".publish.journal" in source


def test_catalog_populate_uses_begin_immediate():
    """Verify catalog rebuild issues BEGIN IMMEDIATE."""
    source = (SRC / "components" / "model_packager.py").read_text(encoding="utf-8")
    assert "BEGIN IMMEDIATE" in source
    assert "wal_checkpoint" in source
    assert "foreign_keys" in source


def test_prediction_pipeline_uses_compare_digest():
    """Verify inference verifies binding_mac with hmac.compare_digest."""
    source = (SRC / "pipeline" / "prediction_pipeline.py").read_text(encoding="utf-8")
    assert "compare_digest" in source
    assert "binding_mac" in source
    assert "hmac" in source

def test_manifest_parent_version_chain():
    """Verify parent_version is null for 1.0.0/bootstrap and otherwise the prior semver."""
    versions = get_version_dirs()
    for index, version in enumerate(versions):
        manifest = load_manifest(version)
        if index == 0:
            assert manifest["parent_version"] is None
            assert version.name == "1.0.0"
            assert manifest["promotion_class"] == "bootstrap"
            assert manifest["bundle_epoch"] == 7
        else:
            assert manifest["parent_version"] == versions[index - 1].name


def test_bundle_epoch_rules():
    """Verify bundle_epoch starts at 7 and increments only on major_gain."""
    versions = get_version_dirs()
    assert load_manifest(versions[0])["bundle_epoch"] == 7
    for previous, current in pairwise(versions):
        prev_epoch = load_manifest(previous)["bundle_epoch"]
        cur_manifest = load_manifest(current)
        if cur_manifest["promotion_class"] == "major_gain":
            assert cur_manifest["bundle_epoch"] == prev_epoch + 1
        else:
            assert cur_manifest["bundle_epoch"] == prev_epoch


def test_manifest_version_matches_directory():
    """Verify manifest model_version equals the containing directory name."""
    for version in get_version_dirs():
        assert load_manifest(version)["model_version"] == version.name


def test_head_matches_active_channel():
    """Verify HEAD matches pins.json active channel (probe if set, else anchor)."""
    assert read_head().strip() == active_channel(read_pins())


def test_pickled_artifacts_are_loadable():
    """Verify packaged model and encoder pickles deserialize."""
    for version in get_version_dirs():
        manifest = load_manifest(version)
        with open(object_path(manifest["blobs"]["model.pkl"]["sha256"]), "rb") as f:
            pickle.load(f)
        with open(
            object_path(manifest["blobs"]["label_encoders.pkl"]["sha256"]), "rb"
        ) as f:
            pickle.load(f)


def test_feature_columns_schema():
    """Verify packaged feature_columns schema and model_version alignment."""
    for version in get_version_dirs():
        manifest = load_manifest(version)
        feature_info = load_blob_json(manifest["blobs"]["feature_columns.json"]["sha256"])
        assert feature_info["model_version"] == version.name
        assert isinstance(feature_info["feature_order"], list)
        assert feature_info["feature_order"]
        assert feature_info["n_features"] == len(feature_info["feature_order"])


def test_metrics_contains_expected_scores():
    """Verify packaged metrics include MAE, MSE, RMSE, and R2."""
    expected = {"MAE", "MSE", "RMSE", "R2"}
    for version in get_version_dirs():
        manifest = load_manifest(version)
        metrics = load_blob_json(manifest["blobs"]["metrics.json"]["sha256"])
        assert expected <= metrics.keys()


def test_version_directories_are_unique():
    """Verify published version directory names are unique."""
    versions = version_dirs()
    assert len(versions) == len(set(versions))


def test_model_supports_prediction():
    """Verify a packaged model predicts using packaged feature_order."""
    version = get_version_dirs()[0]
    manifest = load_manifest(version)
    with open(object_path(manifest["blobs"]["model.pkl"]["sha256"]), "rb") as f:
        model = pickle.load(f)
    feature_info = load_blob_json(manifest["blobs"]["feature_columns.json"]["sha256"])
    feature_columns = feature_info["feature_order"]
    X = pd.DataFrame(np.zeros((1, len(feature_columns))), columns=feature_columns)
    prediction = model.predict(X)
    assert len(prediction) == 1


def test_running_main_creates_new_package_version():
    """Verify rerunning main.py adds exactly one new version and keeps old ones."""
    before = version_dirs()
    assert before
    subprocess.run([sys.executable, str(MAIN)], cwd=PROJECT_ROOT, check=True)
    after = version_dirs()
    assert len(after) == len(before) + 1
    assert set(before).issubset(set(after))
    assert len(set(after) - set(before)) == 1


def test_new_package_is_complete():
    """Verify a newly published package has a complete blob inventory."""
    before = version_dirs()
    subprocess.run([sys.executable, str(MAIN)], cwd=PROJECT_ROOT, check=True)
    after = version_dirs()
    new_version = next(iter(set(after) - set(before)))
    package = VERSIONS / new_version
    assert (package / "manifest.json").is_file()
    manifest = load_manifest(package)
    assert set(manifest["blobs"]) == BLOB_NAMES


def test_package_is_self_contained():
    """Verify inference from CAS blobs alone without training directories."""
    newest = get_version_dirs()[-1]
    backup = ARTIFACTS / "_backup"
    backup.mkdir(exist_ok=True)
    shutil.move(ARTIFACTS / "model_trainer", backup / "model_trainer")
    shutil.move(ARTIFACTS / "data_transformation", backup / "data_transformation")
    try:
        manifest = load_manifest(newest)
        with open(object_path(manifest["blobs"]["model.pkl"]["sha256"]), "rb") as f:
            model = pickle.load(f)
        info = load_blob_json(manifest["blobs"]["feature_columns.json"]["sha256"])
        X = pd.DataFrame(
            np.zeros((1, len(info["feature_order"]))),
            columns=info["feature_order"],
        )
        assert len(model.predict(X)) == 1
    finally:
        shutil.move(backup / "model_trainer", ARTIFACTS / "model_trainer")
        shutil.move(backup / "data_transformation", ARTIFACTS / "data_transformation")


def test_model_packaging_pipeline_runs_standalone():
    """Verify standalone packaging does not retrain and refreshes HEAD."""
    trainer_model = ARTIFACTS / "model_trainer" / "model.pkl"
    transformation_encoders = ARTIFACTS / "data_transformation" / "label_encoders.pkl"
    trainer_mtime_before = trainer_model.stat().st_mtime
    encoders_mtime_before = transformation_encoders.stat().st_mtime

    subprocess.run(
        [sys.executable, "-m", "src.pipeline.model_packaging_pipeline"],
        cwd=PROJECT_ROOT,
        check=True,
    )

    assert trainer_model.stat().st_mtime == trainer_mtime_before
    assert transformation_encoders.stat().st_mtime == encoders_mtime_before
    assert read_head().strip() == active_channel(read_pins())


def test_manifest_created_at_is_valid_timestamp():
    """Verify created_at is timezone-aware ISO-8601 ending with Z and strictly increasing."""
    previous = None
    for version in get_version_dirs():
        created_at = load_manifest(version)["created_at"]
        assert isinstance(created_at, str)
        assert created_at.endswith("Z")
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None
        if previous is not None:
            assert parsed > previous
        previous = parsed


def test_packager_source_forbids_predict_calls():
    """Verify model_packager.py never calls .predict( — gating must stay metrics/schema only."""
    source = (COMPONENT / "model_packager.py").read_text(encoding="utf-8")
    assert ".predict(" not in source, (
        "model_packager.py must not call .predict(; gate using metrics/schema JSON only"
    )


def test_pins_json_is_sorted_canonical():
    """Verify pins.json uses indent=2, sort_keys=True, and a trailing newline."""
    raw = (MODEL_BUNDLE / "pins.json").read_text(encoding="utf-8")
    assert raw.endswith("\n")
    parsed = json.loads(raw)
    expected = json.dumps(parsed, indent=2, sort_keys=True) + "\n"
    assert raw == expected


def test_first_version_is_1_0_0():
    """Verify the oldest published version is exactly 1.0.0."""
    versions = version_dirs()
    assert versions[0] == "1.0.0"


def test_stable_metrics_only_bump_patch():
    """Verify consecutive same-line publishes advance only PATCH (or follow bump rules)."""
    versions = [parse_version(name) for name in version_dirs()]
    assert versions[0] == (1, 0, 0)
    for previous, current in pairwise(versions):
        major_p, minor_p, patch_p = previous
        major_c, minor_c, patch_c = current
        if major_c == major_p and minor_c == minor_p:
            assert patch_c == patch_p + 1
        elif major_c == major_p:
            assert minor_c == minor_p + 1
            assert patch_c == 0
        else:
            assert major_c == major_p + 1
            assert minor_c == 0
            assert patch_c == 0


def test_minor_gain_bumps_minor_version():
    """Verify R2 gain above minor threshold with non-worse MAE yields minor_gain."""
    newest = get_version_dirs()[-1]
    major, minor, _patch = parse_version(newest.name)
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    threshold = float(current_packager_config().r2_minor_bump_threshold)

    improved = dict(baseline)
    improved["R2"] = float(baseline["R2"]) + threshold + 0.01
    improved["MAE"] = float(baseline["MAE"]) * 0.99
    improved["source"] = "minor_gain_probe"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "minor_gain", improved
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        pack_with_config(model, encoders, features, metrics)
        after = version_dirs()
        new_versions = set(after) - set(before)
        assert len(new_versions) == 1
        new_version = next(iter(new_versions))
        assert parse_version(new_version) == (major, minor + 1, 0)
        assert load_manifest(VERSIONS / new_version)["promotion_class"] == "minor_gain"
        pins = read_pins()
        assert pins["anchor"] == new_version
        assert pins["probe"] is None
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_major_gain_bumps_major_version():
    """Verify R2 gain above major threshold with non-worse MAE yields major_gain."""
    newest = get_version_dirs()[-1]
    major, _minor, _patch = parse_version(newest.name)
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    threshold = float(current_packager_config().r2_major_bump_threshold)
    parent_epoch = load_manifest(newest)["bundle_epoch"]

    improved = dict(baseline)
    improved["R2"] = float(baseline["R2"]) + threshold + 0.01
    improved["MAE"] = float(baseline["MAE"]) * 0.99
    improved["source"] = "major_gain_probe"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "major_gain", improved
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        pack_with_config(model, encoders, features, metrics)
        after = version_dirs()
        new_versions = set(after) - set(before)
        assert len(new_versions) == 1
        new_version = next(iter(new_versions))
        assert parse_version(new_version) == (major + 1, 0, 0)
        manifest = load_manifest(VERSIONS / new_version)
        assert manifest["promotion_class"] == "major_gain"
        assert manifest["bundle_epoch"] == parent_epoch + 1
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_minor_gain_with_soft_mae_is_patch():
    """Verify minor R2 gain with soft MAE regression yields minor_gain_mae_soft probe."""
    newest = get_version_dirs()[-1]
    major, minor, patch = parse_version(newest.name)
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    cfg = current_packager_config()
    threshold = float(cfg.r2_minor_bump_threshold)
    tol = float(cfg.mae_regression_tolerance)
    anchor_before = read_pins()["anchor"]

    probe = dict(baseline)
    probe["R2"] = float(baseline["R2"]) + threshold + 0.01
    probe["MAE"] = float(baseline["MAE"]) * (1.0 + tol * 0.5)
    probe["source"] = "mae_soft_probe"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "mae_soft", probe
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        pack_with_config(model, encoders, features, metrics)
        after = version_dirs()
        new_versions = set(after) - set(before)
        assert len(new_versions) == 1
        new_version = next(iter(new_versions))
        assert parse_version(new_version) == (major, minor, patch + 1)
        assert (
            load_manifest(VERSIONS / new_version)["promotion_class"]
            == "minor_gain_mae_soft"
        )
        pins = read_pins()
        assert pins["probe"] == new_version
        assert pins["anchor"] == anchor_before
        assert read_head().strip() == new_version
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_minor_gain_with_hard_mae_refuses():
    """Verify minor R2 gain with hard MAE regression refuses without mutating the store."""
    newest = get_version_dirs()[-1]
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    cfg = current_packager_config()
    threshold = float(cfg.r2_minor_bump_threshold)
    tol = float(cfg.mae_regression_tolerance)

    probe = dict(baseline)
    probe["R2"] = float(baseline["R2"]) + threshold + 0.01
    probe["MAE"] = float(baseline["MAE"]) * (1.0 + tol + 0.2)
    probe["source"] = "mae_hard_probe"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "mae_hard", probe
    )
    before, previous, pins_before, releases_before = snapshot_store()
    head_before = read_head()
    try:
        with project_cwd():
            exception_module = importlib.import_module("src.exception.exception")
            raised = False
            try:
                pack_with_config(model, encoders, features, metrics)
            except exception_module.CustomException:
                raised = True
            assert raised, "hard MAE regression must refuse publish"
        assert version_dirs() == before
        assert read_head() == head_before
        assert read_pins() == pins_before
        assert (MODEL_BUNDLE / "RELEASES").read_text(encoding="utf-8") == releases_before
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_schema_break_without_gain_refuses():
    """Verify a feature schema break without qualifying metrics refuses publish."""
    newest = get_version_dirs()[-1]
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    with open(ARTIFACTS / "data_transformation" / "feature_columns.json") as handle:
        schema = json.load(handle)
    broken = dict(schema)
    broken["feature_order"] = [*schema["feature_order"], "synthetic_break_col"]
    broken["n_features"] = len(broken["feature_order"])

    probe = dict(baseline)
    probe["R2"] = float(baseline["R2"])
    probe["source"] = "schema_break_refuse"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "schema_break_refuse", probe, feature_schema=broken
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        with project_cwd():
            exception_module = importlib.import_module("src.exception.exception")
            raised = False
            try:
                pack_with_config(model, encoders, features, metrics)
            except exception_module.CustomException:
                raised = True
            assert raised
        assert version_dirs() == before
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_schema_break_with_gain_minors():
    """Verify a schema break with qualifying metrics yields schema_break_accepted."""
    newest = get_version_dirs()[-1]
    major, minor, _patch = parse_version(newest.name)
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    threshold = float(current_packager_config().r2_minor_bump_threshold)
    with open(ARTIFACTS / "data_transformation" / "feature_columns.json") as handle:
        schema = json.load(handle)
    broken = dict(schema)
    broken["feature_order"] = [*schema["feature_order"], "synthetic_ok_col"]
    broken["n_features"] = len(broken["feature_order"])

    probe = dict(baseline)
    probe["R2"] = float(baseline["R2"]) + threshold + 0.01
    probe["MAE"] = float(baseline["MAE"])
    probe["source"] = "schema_break_ok"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "schema_break_ok", probe, feature_schema=broken
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        pack_with_config(model, encoders, features, metrics)
        after = version_dirs()
        new_versions = set(after) - set(before)
        assert len(new_versions) == 1
        new_version = next(iter(new_versions))
        assert parse_version(new_version) == (major, minor + 1, 0)
        assert (
            load_manifest(VERSIONS / new_version)["promotion_class"]
            == "schema_break_accepted"
        )
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_r2_floor_refuses():
    """Verify candidates below r2_floor are refused."""
    newest = get_version_dirs()[-1]
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    probe = dict(baseline)
    probe["R2"] = -1.0
    probe["source"] = "floor_probe"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "floor", probe
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        with project_cwd():
            exception_module = importlib.import_module("src.exception.exception")
            raised = False
            try:
                pack_with_config(model, encoders, features, metrics, r2_floor=0.0)
            except exception_module.CustomException:
                raised = True
            assert raised
        assert version_dirs() == before
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_mae_ceiling_refuses():
    """Verify candidates above mae_ceiling are refused without mutating the store."""
    newest = get_version_dirs()[-1]
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    probe = dict(baseline)
    probe["MAE"] = 2.0e9
    probe["source"] = "ceiling_probe"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "ceiling", probe
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        with project_cwd():
            exception_module = importlib.import_module("src.exception.exception")
            raised = False
            try:
                pack_with_config(model, encoders, features, metrics, mae_ceiling=1.0e9)
            except exception_module.CustomException:
                raised = True
            assert raised
        assert version_dirs() == before
        assert read_pins() == pins_before
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_tradeoff_mae_patches():
    """Verify R2 drop with improved MAE yields tradeoff_mae when patches are allowed."""
    newest = get_version_dirs()[-1]
    major, minor, patch = parse_version(newest.name)
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    anchor_before = read_pins()["anchor"]

    probe = dict(baseline)
    probe["R2"] = float(baseline["R2"]) - 0.01
    probe["MAE"] = float(baseline["MAE"]) * 0.9
    probe["source"] = "tradeoff_probe"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "tradeoff", probe
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        pack_with_config(model, encoders, features, metrics)
        after = version_dirs()
        new_versions = set(after) - set(before)
        assert len(new_versions) == 1
        new_version = next(iter(new_versions))
        assert parse_version(new_version) == (major, minor, patch + 1)
        assert load_manifest(VERSIONS / new_version)["promotion_class"] == "tradeoff_mae"
        pins = read_pins()
        assert pins["probe"] == new_version
        assert pins["anchor"] == anchor_before
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_stable_or_better_with_equal_r2_and_better_mae():
    """Verify equal R2 with improved MAE yields stable_or_better and updates anchor."""
    newest = get_version_dirs()[-1]
    major, minor, patch = parse_version(newest.name)
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])

    probe = dict(baseline)
    probe["R2"] = float(baseline["R2"])
    probe["MAE"] = float(baseline["MAE"]) * 0.95
    probe["source"] = "stable_or_better_probe"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "stable_or_better", probe
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        pack_with_config(model, encoders, features, metrics)
        after = version_dirs()
        new_versions = set(after) - set(before)
        assert len(new_versions) == 1
        new_version = next(iter(new_versions))
        assert parse_version(new_version) == (major, minor, patch + 1)
        assert (
            load_manifest(VERSIONS / new_version)["promotion_class"] == "stable_or_better"
        )
        pins = read_pins()
        assert pins["anchor"] == new_version
        assert pins["probe"] is None
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_r2_ok_mae_worse_with_equal_r2_and_worse_mae():
    """Verify equal R2 with worse MAE yields r2_ok_mae_worse probe when patches allowed."""
    newest = get_version_dirs()[-1]
    major, minor, patch = parse_version(newest.name)
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    anchor_before = read_pins()["anchor"]

    probe = dict(baseline)
    probe["R2"] = float(baseline["R2"])
    probe["MAE"] = float(baseline["MAE"]) * 1.05
    probe["source"] = "r2_ok_mae_worse_probe"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "r2_ok_mae_worse", probe
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        pack_with_config(model, encoders, features, metrics)
        after = version_dirs()
        new_versions = set(after) - set(before)
        assert len(new_versions) == 1
        new_version = next(iter(new_versions))
        assert parse_version(new_version) == (major, minor, patch + 1)
        assert (
            load_manifest(VERSIONS / new_version)["promotion_class"] == "r2_ok_mae_worse"
        )
        pins = read_pins()
        assert pins["probe"] == new_version
        assert pins["anchor"] == anchor_before
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_binary_artifacts_byte_identical_to_sources():
    """Verify newest model/encoder/metrics blobs match training sources byte-for-byte."""
    newest = get_version_dirs()[-1]
    manifest = load_manifest(newest)
    sources = {
        "model.pkl": ARTIFACTS / "model_trainer" / "model.pkl",
        "label_encoders.pkl": ARTIFACTS / "data_transformation" / "label_encoders.pkl",
        "metrics.json": ARTIFACTS / "model_evaluation" / "metrics.json",
    }
    for name, src in sources.items():
        digest = manifest["blobs"][name]["sha256"]
        assert object_path(digest).read_bytes() == src.read_bytes()


def test_historical_packages_are_immutable():
    """Verify rerunning main.py does not alter the oldest package or earlier RELEASES."""
    oldest = get_version_dirs()[0]
    before_manifest = hashlib.sha256((oldest / "manifest.json").read_bytes()).hexdigest()
    manifest = load_manifest(oldest)
    before_blobs = {
        name: sha256_file(object_path(meta["sha256"]))
        for name, meta in manifest["blobs"].items()
    }
    releases_before = (MODEL_BUNDLE / "RELEASES").read_text(encoding="utf-8")
    first_line = releases_before.splitlines()[0]
    subprocess.run([sys.executable, str(MAIN)], cwd=PROJECT_ROOT, check=True)
    assert (
        hashlib.sha256((oldest / "manifest.json").read_bytes()).hexdigest()
        == before_manifest
    )
    for name, meta in load_manifest(oldest)["blobs"].items():
        assert before_blobs[name] == sha256_file(object_path(meta["sha256"]))
    releases_after = (MODEL_BUNDLE / "RELEASES").read_text(encoding="utf-8")
    assert releases_after.startswith(releases_before) or releases_after.splitlines()[
        0
    ] == first_line
    assert releases_after.splitlines()[0] == first_line
    assert len(releases_after.splitlines()) == len(releases_before.splitlines()) + 1


def test_prediction_pipeline_loads_from_head_bundle():
    """Verify PredictionPipeline loads HEAD bundle and predicts without training dirs."""
    backup = ARTIFACTS / "_prediction_backup"
    backup.mkdir(exist_ok=True)
    shutil.move(ARTIFACTS / "model_trainer", backup / "model_trainer")
    shutil.move(ARTIFACTS / "data_transformation", backup / "data_transformation")
    try:
        with project_cwd():
            prediction_module = importlib.import_module("src.pipeline.prediction_pipeline")
            importlib.reload(prediction_module)
            pipeline = prediction_module.PredictionPipeline()

            assert hasattr(pipeline, "bundle_dir")
            bundle_path = Path(pipeline.bundle_dir)
            if not bundle_path.is_absolute():
                bundle_path = PROJECT_ROOT / bundle_path
            assert bundle_path.exists()
            assert "versions" in str(bundle_path).replace("\\", "/")
            assert pipeline.model_version == read_head().strip()
            assert pipeline.metrics is not None
            assert "R2" in pipeline.metrics

            X = pd.DataFrame(
                np.zeros((1, len(pipeline.feature_columns))),
                columns=pipeline.feature_columns,
            )
            assert len(pipeline.predict(X)) == 1
    finally:
        shutil.move(backup / "model_trainer", ARTIFACTS / "model_trainer")
        shutil.move(backup / "data_transformation", ARTIFACTS / "data_transformation")


def test_prediction_pipeline_predict_skips_categorical_encoding():
    """Verify predict() treats input as already feature_order-aligned (no re-encoding)."""
    with project_cwd():
        prediction_module = importlib.import_module("src.pipeline.prediction_pipeline")
        importlib.reload(prediction_module)
        pipeline = prediction_module.PredictionPipeline()
        transform_calls: list[str] = []

        encoder_attr = None
        for attr in ("encoder", "encoders", "label_encoders"):
            if hasattr(pipeline, attr):
                encoder_attr = attr
                break
        encoders = getattr(pipeline, encoder_attr, None) if encoder_attr else None
        if isinstance(encoders, dict):
            for name, enc in list(encoders.items()):
                if hasattr(enc, "transform"):
                    original = enc.transform

                    def make_wrapped(orig=original, key=name):
                        def wrapped(*args, **kwargs):
                            transform_calls.append(key)
                            return orig(*args, **kwargs)

                        return wrapped

                    enc.transform = make_wrapped()

        X = pd.DataFrame(
            np.zeros((1, len(pipeline.feature_columns))),
            columns=pipeline.feature_columns,
        )
        assert len(pipeline.predict(X)) == 1
        assert not transform_calls, (
            "predict() must not re-run categorical encoding; "
            f"transform called for {transform_calls}"
        )


def test_prediction_pipeline_rejects_tampered_blob():
    """Verify PredictionPipeline raises CustomException when a CAS blob is tampered."""
    newest = get_version_dirs()[-1]
    manifest = load_manifest(newest)
    metrics_path = object_path(manifest["blobs"]["metrics.json"]["sha256"])
    original = metrics_path.read_bytes()
    try:
        metrics_path.write_text('{"MAE": 0, "MSE": 0, "RMSE": 0, "R2": 0, "tampered": true}')
        with project_cwd():
            prediction_module = importlib.import_module("src.pipeline.prediction_pipeline")
            importlib.reload(prediction_module)
            exception_module = importlib.import_module("src.exception.exception")
            raised = False
            try:
                prediction_module.PredictionPipeline()
            except exception_module.CustomException:
                raised = True
            assert raised, "PredictionPipeline must refuse tampered CAS contents"
    finally:
        metrics_path.write_bytes(original)


def test_prediction_pipeline_rejects_bad_binding_mac():
    """Verify PredictionPipeline raises CustomException when binding_mac is altered."""
    newest = get_version_dirs()[-1]
    manifest_path = newest / "manifest.json"
    original = manifest_path.read_bytes()
    try:
        manifest = json.loads(original)
        manifest["binding_mac"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        with project_cwd():
            prediction_module = importlib.import_module("src.pipeline.prediction_pipeline")
            importlib.reload(prediction_module)
            exception_module = importlib.import_module("src.exception.exception")
            raised = False
            try:
                prediction_module.PredictionPipeline()
            except exception_module.CustomException:
                raised = True
            assert raised, "PredictionPipeline must refuse a bad binding_mac"
    finally:
        manifest_path.write_bytes(original)


def test_feature_schema_matches_training_artifact():
    """Verify newest feature_order/n_features match the training schema."""
    with open(ARTIFACTS / "data_transformation" / "feature_columns.json") as f:
        original = json.load(f)
    newest = get_version_dirs()[-1]
    packaged = load_blob_json(
        load_manifest(newest)["blobs"]["feature_columns.json"]["sha256"]
    )
    assert packaged["feature_order"] == original["feature_order"]
    assert packaged["n_features"] == original["n_features"]


def test_metrics_match_training_artifact():
    """Verify newest metrics blob is a byte-for-byte copy of the evaluation artifact."""
    src = (ARTIFACTS / "model_evaluation" / "metrics.json").read_bytes()
    newest = get_version_dirs()[-1]
    digest = load_manifest(newest)["blobs"]["metrics.json"]["sha256"]
    assert object_path(digest).read_bytes() == src


def test_packager_reads_artifact_paths_from_configuration():
    """Verify initiate_packaging reads sources from ModelPackagerConfig paths."""
    newest = get_version_dirs()[-1]
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    sentinel_metrics = {
        "MAE": 0.111,
        "MSE": 0.222,
        "RMSE": 0.333,
        "R2": float(baseline["R2"]),
        "source": "custom_packager_config",
    }
    custom_root, model, encoders, features, metrics = make_probe_sources(
        "custom_config", sentinel_metrics
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        pack_with_config(model, encoders, features, metrics)
        after = version_dirs()
        new_versions = set(after) - set(before)
        assert len(new_versions) == 1
        new_version = next(iter(new_versions))
        packaged_metrics = load_blob_json(
            load_manifest(VERSIONS / new_version)["blobs"]["metrics.json"]["sha256"]
        )
        assert packaged_metrics == sentinel_metrics
        packaged_features = load_blob_json(
            load_manifest(VERSIONS / new_version)["blobs"]["feature_columns.json"][
                "sha256"
            ]
        )
        assert packaged_features["model_version"] == new_version
        promo = load_manifest(VERSIONS / new_version)["promotion_class"]
        assert promo in {"r2_ok_mae_worse", "stable_or_better", "tradeoff_mae"}
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_dual_regression_refuses_when_patches_disabled():
    """Verify dual metric regression refuses when allow_nonimproving_patch is false."""
    newest = get_version_dirs()[-1]
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    probe = dict(baseline)
    probe["R2"] = float(baseline["R2"]) - 0.2
    probe["MAE"] = float(baseline["MAE"]) + 1.0
    probe["source"] = "dual_regression"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "dual_reg", probe
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        with project_cwd():
            exception_module = importlib.import_module("src.exception.exception")
            raised = False
            try:
                pack_with_config(
                    model,
                    encoders,
                    features,
                    metrics,
                    allow_nonimproving_patch=False,
                )
            except exception_module.CustomException:
                raised = True
            assert raised
        assert version_dirs() == before
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_r2_ok_mae_worse_refuses_when_patches_disabled():
    """Verify r2_ok_mae_worse path refuses when allow_nonimproving_patch is false."""
    newest = get_version_dirs()[-1]
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    probe = dict(baseline)
    probe["R2"] = float(baseline["R2"])
    probe["MAE"] = float(baseline["MAE"]) * 1.02
    probe["source"] = "r2_ok_mae_worse_disabled"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "r2_ok_disabled", probe
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        with project_cwd():
            exception_module = importlib.import_module("src.exception.exception")
            raised = False
            try:
                pack_with_config(
                    model,
                    encoders,
                    features,
                    metrics,
                    allow_nonimproving_patch=False,
                )
            except exception_module.CustomException:
                raised = True
            assert raised
        assert version_dirs() == before
        assert read_pins() == pins_before
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )


def test_tradeoff_mae_refuses_when_patches_disabled():
    """Verify tradeoff_mae path refuses when allow_nonimproving_patch is false."""
    newest = get_version_dirs()[-1]
    baseline = load_blob_json(load_manifest(newest)["blobs"]["metrics.json"]["sha256"])
    probe = dict(baseline)
    probe["R2"] = float(baseline["R2"]) - 0.01
    probe["MAE"] = float(baseline["MAE"]) * 0.9
    probe["source"] = "tradeoff_mae_disabled"

    custom_root, model, encoders, features, metrics = make_probe_sources(
        "tradeoff_disabled", probe
    )
    before, previous, pins_before, releases_before = snapshot_store()
    try:
        with project_cwd():
            exception_module = importlib.import_module("src.exception.exception")
            raised = False
            try:
                pack_with_config(
                    model,
                    encoders,
                    features,
                    metrics,
                    allow_nonimproving_patch=False,
                )
            except exception_module.CustomException:
                raised = True
            assert raised
        assert version_dirs() == before
        assert read_pins() == pins_before
    finally:
        _restore_bundle_after_probe(
            before, previous, custom_root, pins_before, releases_before
        )
