"""
Stateful pipeline tests for dependency-aware re-execution semantics.

Validates: idempotency, incremental recovery, lineage-based versioning,
digest correctness (Git SHA-256 blob ids), and artifact integrity.

These tests MUST run sequentially in collection (file) order. Do not enable
pytest-xdist or any parallel runner: tests mutate shared artifacts/params/src
and rely on per-test cleanup plus the ensure_coherent_pipeline_state fixture.
"""

import hashlib
import json
import pickle
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml
from packaging.version import Version

# Document sequential contract for maintainers / accidental -n usage.
# (Suite is stateful; test.sh must not enable pytest-xdist.)

PROJECT_ROOT = Path("/app/cloud-cost")
ARTIFACTS = PROJECT_ROOT / "artifacts"
MAIN = PROJECT_ROOT / "main.py"
PARAMS = PROJECT_ROOT / "params.yaml"

MLRUNS = PROJECT_ROOT / "mlruns" / "0"
MODEL_BUNDLE = ARTIFACTS / "model_bundle"
LOGS = PROJECT_ROOT / "logs"
PIPELINE_META = ARTIFACTS / ".pipeline"

EXPECTED_PIPELINE_STAGES = (
    "data_validation",
    "data_transformation",
    "model_trainer",
    "model_evaluation",
    "model_packaging",
)

# Inputs tests may mutate; restored before each test if left dirty.
_MUTABLE_SOURCE_PATHS = (
    PARAMS,
    PROJECT_ROOT / "schema.yaml",
    PROJECT_ROOT / "dataset" / "Cloud_Dataset.csv",
    PROJECT_ROOT / "src" / "components" / "model_trainer.py",
    PROJECT_ROOT / "src" / "components" / "data_transformation.py",
    PROJECT_ROOT / "src" / "components" / "data_validation.py",
    PROJECT_ROOT / "src" / "components" / "model_evaluation.py",
    PROJECT_ROOT / "src" / "components" / "model_packager.py",
    PROJECT_ROOT / "src" / "utils" / "feature_engineering.py",
    PROJECT_ROOT / "src" / "pipeline" / "data_validation_pipeline.py",
    PROJECT_ROOT / "src" / "pipeline" / "model_trainer_pipeline.py",
    PROJECT_ROOT / "src" / "pipeline" / "data_transformation_pipeline.py",
    PROJECT_ROOT / "src" / "pipeline" / "model_evaluation_pipeline.py",
    PROJECT_ROOT / "src" / "pipeline" / "model_packaging_pipeline.py",
)


def sha256(path: Path):
    """Return lowercase SHA-256 hex digest of a file's raw bytes."""
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


def git_blob_sha256(path: Path) -> str:
    """Git SHA-256 blob object id (SHA-256 over Git blob framing of the file)."""
    data = path.read_bytes()
    header = f"blob {len(data)}".encode() + bytes([0])
    return hashlib.sha256(header + data).hexdigest()


def assert_git_blob_hex(value: str) -> None:
    assert isinstance(value, str)
    assert len(value) == 64
    assert value == value.lower()
    int(value, 16)


def snapshot_tree(root: Path):
    """
    Returns hashes for every file beneath root.
    """
    snapshot = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        if "logs" in path.parts:
            continue

        snapshot[path.relative_to(root)] = sha256(path)

    return snapshot


def version_dirs():
    """Return sorted semver bundle directories under artifacts/model_bundle/."""
    return sorted(
        (d for d in MODEL_BUNDLE.iterdir() if d.is_dir() and d.name != "latest"),
        key=lambda p: tuple(map(int, p.name.split("."))),
    )


def mlflow_runs():
    """
    Return all MLflow run IDs for the default experiment.
    """
    if not MLRUNS.exists():
        return []

    return sorted(d.name for d in MLRUNS.iterdir() if d.is_dir())


def run_pipeline():
    """Execute main.py in PROJECT_ROOT; assert exactly one new log file."""
    before_logs = set(LOGS.iterdir()) if LOGS.exists() else set()
    subprocess.run(
        [sys.executable, str(MAIN)],
        cwd=PROJECT_ROOT,
        check=True,
    )
    after_logs = set(LOGS.iterdir()) if LOGS.exists() else set()
    assert len(after_logs) == len(before_logs) + 1



def load_trained_model():
    model_path = ARTIFACTS / "model_trainer" / "model.pkl"
    with open(model_path, "rb") as handle:
        return pickle.load(handle)


def load_test_features():
    test_data = pd.read_csv(ARTIFACTS / "data_transformation" / "test.csv")
    return test_data.drop(columns=["cost"])


def load_stage_metadata(stage_id: str) -> dict:
    meta_path = PIPELINE_META / f"{stage_id}.json"
    with open(meta_path, encoding="utf-8") as handle:
        return json.load(handle)


def assert_sha256_hex(value: str) -> None:
    assert_git_blob_hex(value)


def feature_model_version() -> str:
    path = ARTIFACTS / "data_transformation" / "feature_columns.json"
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["model_version"]


def snapshot_pipeline_stage_files(*stage_ids: str) -> dict[str, str]:
    return {
        stage_id: sha256(PIPELINE_META / f"{stage_id}.json") for stage_id in stage_ids
    }


def realign_pipeline_after_restore() -> None:
    """Re-run once so .pipeline digests match restored on-disk inputs."""
    run_pipeline()


def pipeline_state_is_coherent() -> bool:
    """True when all stage ledgers exist and digests match live files."""
    try:
        if not PIPELINE_META.is_dir():
            return False
        model_path = ARTIFACTS / "model_trainer" / "model.pkl"
        if not model_path.is_file() or model_path.stat().st_size == 0:
            return False
        for stage_id in EXPECTED_PIPELINE_STAGES:
            meta_path = PIPELINE_META / f"{stage_id}.json"
            if not meta_path.is_file():
                return False
            record = json.loads(meta_path.read_text(encoding="utf-8"))
            if record.get("status") != "success" or record.get("stage") != stage_id:
                return False
            for rel_path, digest in (record.get("dependencies") or {}).items():
                path = PROJECT_ROOT / rel_path
                if not path.is_file() or git_blob_sha256(path) != digest:
                    return False
            for rel_path, digest in (record.get("outputs") or {}).items():
                path = PROJECT_ROOT / rel_path
                if not path.is_file() or git_blob_sha256(path) != digest:
                    return False
        return True
    except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError):
        return False


@pytest.fixture(scope="session")
def golden_mutable_sources():
    """Byte-exact copies of mutable sources as of suite start (post-oracle)."""
    snapshots = {}
    for path in _MUTABLE_SOURCE_PATHS:
        assert path.is_file(), f"Missing expected source at suite start: {path}"
        snapshots[path] = path.read_bytes()
    return snapshots


@pytest.fixture(autouse=True)
def ensure_coherent_pipeline_state(golden_mutable_sources):
    """
    Start every test from coherent pipeline state.

    Restores mutated sources left behind by a failed cleanup, then re-runs the
    pipeline only when ledgers/artifacts are inconsistent.
    """
    restored = False
    for path, blob in golden_mutable_sources.items():
        if path.read_bytes() != blob:
            path.write_bytes(blob)
            restored = True
    if restored or not pipeline_state_is_coherent():
        run_pipeline()
    assert pipeline_state_is_coherent(), "Pipeline must be coherent before each test"
    yield


def assert_stage_metadata_record(record: dict, stage_id: str) -> None:
    assert record.get("stage") == stage_id
    assert record.get("status") == "success"
    assert isinstance(record.get("completed_at"), str)

    dependencies = record.get("dependencies") or {}
    outputs = record.get("outputs") or {}

    assert dependencies, f"{stage_id} metadata must fingerprint dependency inputs"
    assert outputs, f"{stage_id} metadata must fingerprint owned outputs"

    for digest in dependencies.values():
        assert_sha256_hex(digest)
    for digest in outputs.values():
        assert_sha256_hex(digest)


def assert_pipeline_metadata_complete() -> None:
    assert PIPELINE_META.exists()
    for stage_id in EXPECTED_PIPELINE_STAGES:
        meta_path = PIPELINE_META / f"{stage_id}.json"
        assert meta_path.exists(), f"Missing metadata file for stage '{stage_id}'"
        assert_stage_metadata_record(load_stage_metadata(stage_id), stage_id)


def test_second_run_preserves_everything():
    """
    Running the pipeline twice without any changes should produce identical results.
    Verifies idempotency - no artifacts, MLflow runs, or versions should change.
    """

    artifacts_before = snapshot_tree(ARTIFACTS)
    mlruns_before = mlflow_runs()
    versions_before = version_dirs()

    run_pipeline()

    artifacts_after = snapshot_tree(ARTIFACTS)
    mlruns_after = mlflow_runs()
    versions_after = version_dirs()

    assert artifacts_before == artifacts_after
    assert mlruns_before == mlruns_after
    assert versions_before == versions_after


def test_missing_validation_artifacts_trigger_resume():
    """
    Deleting artifacts/data_validation/ is a true upstream invalidation.
    Because validation feeds every later ML stage, rebuild must mint a new
    semver bundle version and create exactly one new MLflow run.
    """

    validation = ARTIFACTS / "data_validation"

    before_runs = mlflow_runs()
    versions_before = version_dirs()

    shutil.rmtree(validation)

    run_pipeline()

    assert validation.exists()
    assert len(version_dirs()) == len(versions_before) + 1
    assert len(mlflow_runs()) == len(before_runs) + 1


def test_missing_transformation_artifacts_trigger_resume():
    """
    Deleting artifacts/data_transformation/ is a true upstream invalidation.
    Feature schema / semver lineage lives here, so rebuild must mint a new
    semver bundle version and create exactly one new MLflow run.
    """

    transformation = ARTIFACTS / "data_transformation"

    before_runs = mlflow_runs()
    versions_before = version_dirs()

    shutil.rmtree(transformation)

    run_pipeline()

    assert transformation.exists()
    assert len(version_dirs()) == len(versions_before) + 1
    assert len(mlflow_runs()) == len(before_runs) + 1


def test_missing_model_trainer_artifacts():
    """
    Missing model_trainer outputs are downstream recovery: stages 1-2 stay valid,
    so recreate model.pkl without a new semver. Evaluation must re-run and
    therefore creates exactly one new MLflow run.
    """

    trainer = ARTIFACTS / "model_trainer"

    before_runs = mlflow_runs()
    before = version_dirs()

    shutil.rmtree(trainer)

    run_pipeline()

    assert trainer.exists()

    assert (trainer / "model.pkl").exists()

    assert (trainer / "metrics.json").exists()

    with open(trainer / "model.pkl", "rb") as f:
        pickle.load(f)

    with open(trainer / "metrics.json") as f:
        json.load(f)

    assert len(version_dirs()) == len(before)
    assert len(mlflow_runs()) == len(before_runs) + 1


def test_missing_evaluation_artifacts():
    """
    Missing evaluation outputs are downstream recovery: no new semver, but
    re-running model_evaluation creates exactly one new MLflow run.
    """

    evaluation = ARTIFACTS / "model_evaluation"

    before_runs = mlflow_runs()
    before = version_dirs()

    shutil.rmtree(evaluation)

    run_pipeline()

    assert evaluation.exists()

    metrics = evaluation / "metrics.json"

    assert metrics.exists()

    with open(metrics) as f:
        json.load(f)

    assert len(version_dirs()) == len(before)
    assert len(mlflow_runs()) == len(before_runs) + 1


def test_missing_model_bundle_only():
    """
    Deleting only the model bundle should recreate it without retraining.
    Verifies packaging can be regenerated from existing trained artifacts.
    """

    shutil.rmtree(MODEL_BUNDLE)

    run_pipeline()

    assert MODEL_BUNDLE.exists()

    versions = version_dirs()
    assert len(versions) >= 1

    latest = MODEL_BUNDLE / "latest"
    assert latest.exists()

    with open(latest / "manifest.json") as handle:
        manifest = json.load(handle)

    assert "model_version" in manifest
    assert "files" in manifest

    for required in ("model.pkl", "label_encoders.pkl", "feature_columns.json"):
        assert (latest / required).exists()


def test_corrupted_model_triggers_rebuild():
    """
    Corrupted model.pkl is downstream recovery: rebuild without a new semver.
    Evaluation re-runs and creates exactly one new MLflow run.
    """

    model = ARTIFACTS / "model_trainer" / "model.pkl"

    model.write_bytes(b"garbage")

    before = version_dirs()
    before_runs = mlflow_runs()

    run_pipeline()

    with open(model, "rb") as f:
        rebuilt = pickle.load(f)

    assert rebuilt is not None

    assert len(version_dirs()) == len(before)
    assert len(mlflow_runs()) == len(before_runs) + 1


def test_corrupted_metrics_trigger_packaging():
    """
    Corrupted evaluation metrics are downstream recovery: no new semver.
    Re-running model_evaluation creates exactly one new MLflow run.
    """

    metrics = ARTIFACTS / "model_evaluation" / "metrics.json"

    metrics.write_text("{")

    before = version_dirs()
    before_runs = mlflow_runs()

    run_pipeline()

    with open(metrics) as f:
        repaired = json.load(f)

    assert isinstance(repaired, dict)

    for key in ["MAE", "MSE", "RMSE", "R2"]:
        assert key in repaired
        assert isinstance(repaired[key], int | float)

    assert len(version_dirs()) == len(before)
    assert len(mlflow_runs()) == len(before_runs) + 1


def test_parameter_change_creates_new_mlflow_run():
    """
    Modifying hyperparameters invalidates model_trainer onward (not stages 1-2).
    Expect a new MLflow run and no new semver bundle version.
    """
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    with open(PARAMS) as f:
        params = yaml.safe_load(f)

    original = params["RandomForest"]["n_estimators"]

    params["RandomForest"]["n_estimators"] = original + 50

    with open(PARAMS, "w") as f:
        yaml.safe_dump(params, f, sort_keys=False)

    try:
        run_pipeline()

        after_runs = mlflow_runs()

        assert len(after_runs) == len(before_runs) + 1
        assert len(version_dirs()) == len(before_versions)

    finally:
        with open(PARAMS) as f:
            params = yaml.safe_load(f)

        params["RandomForest"]["n_estimators"] = original

        with open(PARAMS, "w") as f:
            yaml.safe_dump(params, f, sort_keys=False)


def test_parameter_restoration_stabilizes_pipeline():
    """
    Adding a new parameter then restoring it should change the artifact state
    and leave a new MLflow run from the temporary invalidation, without minting
    a lasting new semver lineage beyond what the temporary change produced.
    """

    original = PARAMS.read_text()
    versions_before = version_dirs()
    runs_before = mlflow_runs()

    PARAMS.write_text(original + "\npytest_parameter: 123\n")

    run_pipeline()

    assert len(mlflow_runs()) == len(runs_before) + 1
    assert len(version_dirs()) == len(versions_before)

    PARAMS.write_text(original)

    before = snapshot_tree(ARTIFACTS)
    runs_mid = mlflow_runs()

    run_pipeline()

    after = snapshot_tree(ARTIFACTS)

    assert before != after
    assert len(mlflow_runs()) == len(runs_mid) + 1
    assert len(version_dirs()) == len(versions_before)


def test_previous_packages_are_preserved():
    """
    Existing versioned packages should be preserved when new packages are created.
    Verifies that repackaging doesn't delete previous model versions.
    """

    before = set(version_dirs())

    shutil.rmtree(ARTIFACTS / "data_validation")

    run_pipeline()

    after = set(version_dirs())

    assert before.issubset(after)


def test_latest_tracks_newest_package():
    """
    The 'latest' symlink should always point to the newest model version.
    Verifies that the latest manifest correctly references the current version.
    """
    shutil.rmtree(ARTIFACTS / "data_validation")

    run_pipeline()

    newest = version_dirs()[-1]

    with open(MODEL_BUNDLE / "latest" / "manifest.json") as f:
        latest = json.load(f)

    assert latest["model_version"] == newest.name


def test_pipeline_metadata_exists():
    """
    Pipeline metadata directory should contain one SHA-256 fingerprinted JSON
    record per ML stage after running the pipeline.
    """
    assert_pipeline_metadata_complete()


def test_pipeline_metadata_output_digests_match_artifacts():
    """
    Recorded output digests in training metadata must match live artifact hashes.
    """
    run_pipeline()
    assert_pipeline_metadata_complete()

    for stage_id in EXPECTED_PIPELINE_STAGES:
        record = load_stage_metadata(stage_id)
        for rel_path, recorded_digest in record["outputs"].items():
            artifact_path = PROJECT_ROOT / rel_path
            assert artifact_path.is_file(), f"Missing output artifact {rel_path}"
            assert git_blob_sha256(artifact_path) == recorded_digest


def test_pipeline_metadata_stable():
    """
    Pipeline metadata should remain stable when running without changes.
    Verifies that metadata doesn't change on idempotent runs.
    """

    before = snapshot_tree(PIPELINE_META)

    run_pipeline()

    after = snapshot_tree(PIPELINE_META)

    assert before == after


def test_resume_from_partial_state():
    """
    Pipeline should resume correctly from a partially built state.
    Verifies recovery when only evaluation artifacts are missing.
    """

    shutil.rmtree(ARTIFACTS / "model_evaluation")

    run_pipeline()

    assert (ARTIFACTS / "model_evaluation").exists()


def test_pipeline_metadata_persists():
    """
    Pipeline metadata files should persist across runs without changes.
    Verifies that metadata files remain valid and readable.
    """
    before = {
        p.relative_to(PIPELINE_META) for p in PIPELINE_META.rglob("*") if p.is_file()
    }

    run_pipeline()

    after = {
        p.relative_to(PIPELINE_META) for p in PIPELINE_META.rglob("*") if p.is_file()
    }

    assert before == after

    for stage_id in EXPECTED_PIPELINE_STAGES:
        assert_stage_metadata_record(load_stage_metadata(stage_id), stage_id)


def test_second_run_without_changes_only_creates_log():
    """
    Running the pipeline without changes should only create a new log file.
    All artifacts, runs, and versions should remain identical.
    """
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    run_pipeline()

    assert before_runs == mlflow_runs()
    assert before_versions == version_dirs()


def test_missing_transformation_triggers_new_pipeline():
    """
    Missing transformation artifacts are a true upstream invalidation of the
    model input schema lineage: full downstream rebuild with a new semver and
    a new MLflow run (same semantics as deleting the transformation directory).
    """
    shutil.rmtree(ARTIFACTS / "data_transformation")

    before_versions = version_dirs()
    before_runs = mlflow_runs()

    run_pipeline()

    after_versions = version_dirs()
    after_runs = mlflow_runs()

    assert len(after_versions) == len(before_versions) + 1
    assert len(after_runs) == len(before_runs) + 1

    assert (ARTIFACTS / "data_transformation").exists()


def test_missing_model_bundle_only_repackages():
    """
    Deleting only the model bundle should repackage without new MLflow runs.
    Verifies that packaging doesn't trigger unnecessary retraining.
    """
    shutil.rmtree(MODEL_BUNDLE)

    before_runs = mlflow_runs()

    run_pipeline()

    after_runs = mlflow_runs()

    assert before_runs == after_runs

    assert MODEL_BUNDLE.exists()


def test_existing_packages_are_preserved():
    """
    Existing versioned packages should be preserved when rebuilding from scratch.
    Verifies that previous model versions are never deleted.
    """
    versions_before = version_dirs()

    shutil.rmtree(ARTIFACTS / "data_validation")

    run_pipeline()

    versions_after = version_dirs()

    assert set(versions_before).issubset(set(versions_after))


def test_recreating_model_bundle_does_not_retrain_model():
    """
    Removing only the deployment package should recreate the package
    without retraining the model or creating a new experiment.
    """

    trainer_model = ARTIFACTS / "model_trainer" / "model.pkl"

    original_model_hash = sha256(trainer_model)

    runs_before = mlflow_runs()

    shutil.rmtree(MODEL_BUNDLE)

    run_pipeline()

    runs_after = mlflow_runs()

    assert MODEL_BUNDLE.exists()

    assert sha256(trainer_model) == original_model_hash, (
        "The trained model changed while regenerating only the package."
    )

    assert runs_before == runs_after, (
        "Packaging unexpectedly triggered a new MLflow training run."
    )


def test_model_produces_predictions_after_execution():
    """
    The trained model must load and produce numeric predictions on test data.
    Verifies outputs remain capable of inference after pipeline execution.
    """

    run_pipeline()

    model = load_trained_model()
    features = load_test_features()
    predictions = model.predict(features)

    assert len(predictions) == len(features)
    assert all(isinstance(value, float | int) for value in predictions)


def test_source_code_change_triggers_rebuild():
    """
    Fit-or-later / lineage boundary: trainer-source edits create a new FileStore
    run with no new semver; feature_columns model_version unchanged.
    """

    trainer_src = PROJECT_ROOT / "src" / "components" / "model_trainer.py"
    original = trainer_src.read_text()
    before_runs = mlflow_runs()
    before_versions = version_dirs()
    before_lineage = feature_model_version()

    trainer_src.write_text(original + "\n# dependency-invalidation probe\n")

    try:
        run_pipeline()
        after_runs = mlflow_runs()
        assert len(after_runs) == len(before_runs) + 1
        assert len(version_dirs()) == len(before_versions)
        assert feature_model_version() == before_lineage
    finally:
        trainer_src.write_text(original)
        realign_pipeline_after_restore()


def test_corrupted_training_metadata_triggers_recovery():
    """
    Corrupted model_trainer.json forces that stage and later stages to re-run.
    Stages 1-2 remain valid, so no new semver; evaluation re-run creates one
    new MLflow run and metadata must be rewritten with valid SHA-256 digests.
    """

    meta_path = PIPELINE_META / "model_trainer.json"
    meta_path.write_text("{")

    before_versions = version_dirs()
    before_runs = mlflow_runs()

    run_pipeline()

    record = load_stage_metadata("model_trainer")
    assert_stage_metadata_record(record, "model_trainer")
    assert len(version_dirs()) == len(before_versions)
    assert len(mlflow_runs()) == len(before_runs) + 1


def test_feature_engineering_code_change_triggers_version_bump():
    """
    Editing data_transformation.py is a true upstream invalidation of the
    model input schema lineage: expect a new semver and a new MLflow run.
    """

    transform_src = PROJECT_ROOT / "src" / "components" / "data_transformation.py"
    original = transform_src.read_text()
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    transform_src.write_text(original + "\n# feature-engineering invalidation probe\n")

    try:
        run_pipeline()
        assert len(mlflow_runs()) == len(before_runs) + 1
        assert len(version_dirs()) == len(before_versions) + 1
    finally:
        transform_src.write_text(original)
        realign_pipeline_after_restore()


def test_validation_source_change_triggers_full_rebuild():
    """
    Editing data_validation.py is a lineage-changing upstream invalidation:
    new semver and exactly one new MLflow run.
    """

    validation_src = PROJECT_ROOT / "src" / "components" / "data_validation.py"
    original = validation_src.read_text()
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    validation_src.write_text(original + "\n# validation-source invalidation probe\n")

    try:
        run_pipeline()
        assert len(mlflow_runs()) == len(before_runs) + 1
        assert len(version_dirs()) == len(before_versions) + 1
    finally:
        validation_src.write_text(original)
        realign_pipeline_after_restore()


def test_dataset_change_triggers_upstream_rebuild():
    """
    Editing the training dataset must invalidate stages 1-2 and cascade:
    new semver and exactly one new MLflow run.
    """

    dataset = PROJECT_ROOT / "dataset" / "Cloud_Dataset.csv"
    original = dataset.read_bytes()
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    frame = pd.read_csv(dataset)
    last_idx = frame.index[-1]
    frame.loc[last_idx, "cost"] = float(frame.loc[last_idx, "cost"]) + 0.01
    frame.to_csv(dataset, index=False)

    try:
        run_pipeline()
        assert len(mlflow_runs()) == len(before_runs) + 1
        assert len(version_dirs()) == len(before_versions) + 1
    finally:
        dataset.write_bytes(original)
        realign_pipeline_after_restore()


def test_schema_change_triggers_upstream_rebuild():
    """
    Editing schema.yaml must invalidate validation/transformation lineage:
    new semver and exactly one new MLflow run.
    """

    schema = PROJECT_ROOT / "schema.yaml"
    original = schema.read_text(encoding="utf-8")
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    schema.write_text(original + "\n# schema invalidation probe\n", encoding="utf-8")

    try:
        run_pipeline()
        assert len(mlflow_runs()) == len(before_runs) + 1
        assert len(version_dirs()) == len(before_versions) + 1
    finally:
        schema.write_text(original, encoding="utf-8")
        realign_pipeline_after_restore()


def test_corrupted_label_encoders_triggers_version_bump():
    """
    Corrupting label_encoders.pkl invalidates data_transformation (lineage owner):
    expect a new semver and a new MLflow run.
    """

    encoders = ARTIFACTS / "data_transformation" / "label_encoders.pkl"
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    encoders.write_bytes(b"not-a-pickle")

    run_pipeline()

    assert len(mlflow_runs()) == len(before_runs) + 1
    assert len(version_dirs()) == len(before_versions) + 1
    with open(encoders, "rb") as handle:
        pickle.load(handle)


def test_missing_train_csv_only_triggers_version_bump():
    """
    One missing transformation output invalidates the whole transformation stage.
    """

    train_csv = ARTIFACTS / "data_transformation" / "train.csv"
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    train_csv.unlink()

    run_pipeline()

    assert train_csv.exists()
    assert len(mlflow_runs()) == len(before_runs) + 1
    assert len(version_dirs()) == len(before_versions) + 1


def test_parameter_change_preserves_feature_model_version():
    """
    Hyperparameter edits must not rewrite feature_columns.json model_version.
    """

    before_lineage = feature_model_version()
    before_versions = version_dirs()
    before_runs = mlflow_runs()

    with open(PARAMS) as handle:
        params = yaml.safe_load(handle)

    original = params["RandomForest"]["n_estimators"]
    params["RandomForest"]["n_estimators"] = original + 25

    with open(PARAMS, "w") as handle:
        yaml.safe_dump(params, handle, sort_keys=False)

    try:
        run_pipeline()
        assert feature_model_version() == before_lineage
        assert len(version_dirs()) == len(before_versions)
        assert len(mlflow_runs()) == len(before_runs) + 1
    finally:
        with open(PARAMS) as handle:
            params = yaml.safe_load(handle)
        params["RandomForest"]["n_estimators"] = original
        with open(PARAMS, "w") as handle:
            yaml.safe_dump(params, handle, sort_keys=False)
        realign_pipeline_after_restore()


def test_packaging_only_preserves_upstream_pipeline_metadata_bytes():
    """
    Packaging-only recovery: skipped-stage .pipeline JSON files stay
    byte-identical; redeploy into the current feature_columns version without
    minting a new semver or creating a new MLflow run.
    """

    lineage = feature_model_version()
    before_versions = {path.name for path in version_dirs()}
    before_runs = mlflow_runs()
    before_meta = snapshot_pipeline_stage_files(
        "data_validation",
        "data_transformation",
        "model_trainer",
        "model_evaluation",
    )

    shutil.rmtree(MODEL_BUNDLE)

    run_pipeline()

    after_meta = snapshot_pipeline_stage_files(
        "data_validation",
        "data_transformation",
        "model_trainer",
        "model_evaluation",
    )
    assert before_meta == after_meta
    assert before_runs == mlflow_runs()
    assert feature_model_version() == lineage
    assert {path.name for path in version_dirs()} == {lineage}
    assert lineage in before_versions


def test_evaluation_recovery_preserves_upstream_metadata_and_model_bytes():
    """
    Evaluation recovery must not rewrite skipped upstream metadata or retrain.
    """

    model_path = ARTIFACTS / "model_trainer" / "model.pkl"
    original_model = sha256(model_path)
    before_meta = snapshot_pipeline_stage_files(
        "data_validation",
        "data_transformation",
        "model_trainer",
    )
    before_versions = version_dirs()
    before_runs = mlflow_runs()

    shutil.rmtree(ARTIFACTS / "model_evaluation")

    run_pipeline()

    assert sha256(model_path) == original_model
    assert before_meta == snapshot_pipeline_stage_files(
        "data_validation",
        "data_transformation",
        "model_trainer",
    )
    assert len(version_dirs()) == len(before_versions)
    assert len(mlflow_runs()) == len(before_runs) + 1


def test_combined_metrics_and_bundle_recovery():
    """
    Corrupt metrics + missing bundle: evaluation re-runs (+1 MLflow), packaging
    re-runs, no new semver, and the fitted model bytes stay unchanged.
    """

    model_path = ARTIFACTS / "model_trainer" / "model.pkl"
    original_model = sha256(model_path)
    before_versions = version_dirs()
    before_runs = mlflow_runs()
    lineage = feature_model_version()

    (ARTIFACTS / "model_evaluation" / "metrics.json").write_text("{")
    shutil.rmtree(MODEL_BUNDLE)

    run_pipeline()

    assert sha256(model_path) == original_model
    assert feature_model_version() == lineage
    assert len(version_dirs()) == 1
    assert version_dirs()[0].name == lineage
    assert len(mlflow_runs()) == len(before_runs) + 1
    assert len(before_versions) >= 1


def test_packaging_metadata_records_feature_columns_dependency():
    """
    model_packaging dependencies must fingerprint feature_columns.json so
    packaging stays tied to the lineage owner rather than inventing versions.
    """

    record = load_stage_metadata("model_packaging")
    deps = record.get("dependencies") or {}
    feature_key = "artifacts/data_transformation/feature_columns.json"
    assert feature_key in deps
    assert deps[feature_key] == git_blob_sha256(PROJECT_ROOT / feature_key)


def test_dependency_digests_match_git_blob_ids():
    """
    Recorded dependency digests must be Git SHA-256 blob object ids, not bare
    hashes of file bytes.
    """

    run_pipeline()
    for stage_id in EXPECTED_PIPELINE_STAGES:
        record = load_stage_metadata(stage_id)
        for rel_path, recorded_digest in record["dependencies"].items():
            path = PROJECT_ROOT / rel_path
            assert path.is_file(), f"Missing dependency {rel_path} for {stage_id}"
            expected = git_blob_sha256(path)
            assert recorded_digest == expected
            assert recorded_digest != sha256(path)
            # Also check outputs use the same digest family.
        for rel_path, recorded_digest in record["outputs"].items():
            path = PROJECT_ROOT / rel_path
            assert path.is_file(), f"Missing output {rel_path} for {stage_id}"
            assert recorded_digest == git_blob_sha256(path)
            assert recorded_digest != sha256(path)


def test_params_yaml_only_fingerprinted_by_trainer():
    """
    params.yaml may appear only in model_trainer dependencies — never stages 1/2/4/5.
    """

    for stage_id in EXPECTED_PIPELINE_STAGES:
        deps = load_stage_metadata(stage_id)["dependencies"]
        has_params = any(Path(path).name == "params.yaml" for path in deps)
        if stage_id == "model_trainer":
            assert has_params, "model_trainer must fingerprint params.yaml"
        else:
            assert not has_params, f"{stage_id} must not fingerprint params.yaml"


def test_packaging_outputs_use_versioned_manifest_not_latest():
    """
    Packaging metadata must fingerprint the versioned manifest path, not latest.
    """

    run_pipeline()
    version = feature_model_version()
    record = load_stage_metadata("model_packaging")
    outputs = record["outputs"]
    expected = f"artifacts/model_bundle/{version}/manifest.json"
    assert expected in outputs
    assert outputs[expected] == git_blob_sha256(PROJECT_ROOT / expected)
    assert "artifacts/model_bundle/latest" not in outputs
    assert "artifacts/model_bundle/latest/manifest.json" not in outputs


def test_pipeline_metadata_sorted_keys_and_trailing_newline():
    """
    Instruction rule: dependencies/outputs maps use strict lexicographic key
    order; ledger files end with a trailing newline (stable no-op bytes).
    """

    run_pipeline()
    for stage_id in EXPECTED_PIPELINE_STAGES:
        path = PIPELINE_META / f"{stage_id}.json"
        raw = path.read_text(encoding="utf-8")
        assert raw.endswith("\n")
        record = json.loads(raw)
        assert list(record["dependencies"]) == sorted(record["dependencies"])
        assert list(record["outputs"]) == sorted(record["outputs"])


def test_parameter_change_preserves_upstream_pipeline_metadata_bytes():
    """
    Fit-changing param edits must leave stages 1-2 metadata byte-identical.
    """

    before_meta = snapshot_pipeline_stage_files(
        "data_validation",
        "data_transformation",
    )
    before_lineage = feature_model_version()
    before_versions = version_dirs()
    before_runs = mlflow_runs()

    with open(PARAMS) as handle:
        params = yaml.safe_load(handle)
    original = params["RandomForest"]["n_estimators"]
    params["RandomForest"]["n_estimators"] = original + 10
    with open(PARAMS, "w") as handle:
        yaml.safe_dump(params, handle, sort_keys=False)

    try:
        run_pipeline()
        assert before_meta == snapshot_pipeline_stage_files(
            "data_validation",
            "data_transformation",
        )
        assert feature_model_version() == before_lineage
        assert len(version_dirs()) == len(before_versions)
        assert len(mlflow_runs()) == len(before_runs) + 1
    finally:
        with open(PARAMS) as handle:
            params = yaml.safe_load(handle)
        params["RandomForest"]["n_estimators"] = original
        with open(PARAMS, "w") as handle:
            yaml.safe_dump(params, handle, sort_keys=False)
        realign_pipeline_after_restore()


def test_corrupted_validation_metadata_triggers_version_bump():
    """
    Corrupt data_validation.json is lineage-changing: new semver + MLflow run.
    """

    meta_path = PIPELINE_META / "data_validation.json"
    before_runs = mlflow_runs()
    before_versions = version_dirs()
    before_lineage = feature_model_version()

    meta_path.write_text("{")

    run_pipeline()

    record = load_stage_metadata("data_validation")
    assert_stage_metadata_record(record, "data_validation")
    assert len(mlflow_runs()) == len(before_runs) + 1
    assert len(version_dirs()) == len(before_versions) + 1
    assert feature_model_version() != before_lineage


def test_corrupted_transformation_metadata_triggers_version_bump():
    """
    Corrupt data_transformation.json is lineage-changing: new semver + MLflow run.
    """

    meta_path = PIPELINE_META / "data_transformation.json"
    before_runs = mlflow_runs()
    before_versions = version_dirs()
    before_lineage = feature_model_version()

    meta_path.write_text("{")

    run_pipeline()

    record = load_stage_metadata("data_transformation")
    assert_stage_metadata_record(record, "data_transformation")
    assert len(mlflow_runs()) == len(before_runs) + 1
    assert len(version_dirs()) == len(before_versions) + 1
    assert feature_model_version() != before_lineage


def test_missing_validation_status_file_triggers_version_bump():
    """
    Deleting only status.txt (not the whole validation directory) is lineage-changing.
    """

    status = ARTIFACTS / "data_validation" / "status.txt"
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    status.unlink()

    run_pipeline()

    assert status.exists()
    assert len(mlflow_runs()) == len(before_runs) + 1
    assert len(version_dirs()) == len(before_versions) + 1


def test_lineage_invalidation_strictly_increases_model_version():
    """
    When stage 2 re-executes, feature_columns model_version must strictly increase.
    """

    before = feature_model_version()
    before_versions = version_dirs()

    shutil.rmtree(ARTIFACTS / "data_validation")
    run_pipeline()

    after = feature_model_version()
    assert Version(after) > Version(before)
    assert after == version_dirs()[-1].name
    assert len(version_dirs()) == len(before_versions) + 1


def test_empty_model_pickle_triggers_downstream_recovery():
    """
    Zero-byte model.pkl is structurally invalid: rebuild without a new semver.
    """

    model = ARTIFACTS / "model_trainer" / "model.pkl"
    before_versions = version_dirs()
    before_runs = mlflow_runs()
    before_lineage = feature_model_version()

    model.write_bytes(b"")

    run_pipeline()

    assert model.stat().st_size > 0
    with open(model, "rb") as handle:
        pickle.load(handle)
    assert len(version_dirs()) == len(before_versions)
    assert feature_model_version() == before_lineage
    assert len(mlflow_runs()) == len(before_runs) + 1


def test_feature_columns_n_features_mismatch_triggers_version_bump():
    """
    Structurally invalid feature_columns.json invalidates transformation lineage.
    """

    feature_path = ARTIFACTS / "data_transformation" / "feature_columns.json"
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    with open(feature_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    payload["n_features"] = int(payload["n_features"]) + 99
    feature_path.write_text(json.dumps(payload), encoding="utf-8")

    run_pipeline()

    with open(feature_path, encoding="utf-8") as handle:
        repaired = json.load(handle)
    assert repaired["n_features"] == len(repaired["feature_order"])
    assert len(mlflow_runs()) == len(before_runs) + 1
    assert len(version_dirs()) == len(before_versions) + 1


def test_content_identical_param_rewrite_does_not_retrain():
    """
    Rewriting params.yaml with identical bytes must not create a new MLflow run.
    Digest-based invalidation is required; mtime-only helpers must not drive skips.
    """

    original = PARAMS.read_bytes()
    before_runs = mlflow_runs()
    before_versions = version_dirs()
    before_lineage = feature_model_version()

    PARAMS.write_bytes(original)

    run_pipeline()

    assert mlflow_runs() == before_runs
    assert version_dirs() == before_versions
    assert feature_model_version() == before_lineage


def test_packaging_only_preserves_feature_columns_bytes():
    """
    Packaging-only recovery must not rewrite feature_columns.json.
    """

    feature_path = ARTIFACTS / "data_transformation" / "feature_columns.json"
    before_feature = feature_path.read_bytes()
    before_runs = mlflow_runs()
    before_lineage = feature_model_version()

    shutil.rmtree(MODEL_BUNDLE)
    run_pipeline()

    assert feature_path.read_bytes() == before_feature
    assert feature_model_version() == before_lineage
    assert before_runs == mlflow_runs()
    assert version_dirs()[0].name == before_lineage


def test_corrupted_trainer_metrics_are_downstream_recovery():
    """
    Corrupt artifacts/model_trainer/metrics.json while stages 1-2 stay valid:
    refit/evaluate without a new semver.
    """

    trainer_metrics = ARTIFACTS / "model_trainer" / "metrics.json"
    before_runs = mlflow_runs()
    before_versions = version_dirs()
    before_lineage = feature_model_version()

    trainer_metrics.write_text("{")

    run_pipeline()

    with open(trainer_metrics, encoding="utf-8") as handle:
        repaired = json.load(handle)
    assert set(repaired) >= {"MAE", "MSE", "RMSE", "R2"}
    assert feature_model_version() == before_lineage
    assert len(version_dirs()) == len(before_versions)
    assert len(mlflow_runs()) == len(before_runs) + 1


def test_new_mlflow_run_uses_default_experiment_store():
    """
    Evaluation recovery must append a run directory under mlruns/0 with meta.yaml.
    """

    before = set(mlflow_runs())
    shutil.rmtree(ARTIFACTS / "model_evaluation")
    run_pipeline()
    created = set(mlflow_runs()) - before
    assert len(created) == 1
    run_dir = MLRUNS / next(iter(created))
    assert (run_dir / "meta.yaml").is_file()


def test_artifact_contracts_match_existing_components():
    """
    Live metrics / feature schema / manifest must match the field contracts
    already produced by the project's evaluation, transformation, and packager.
    """

    run_pipeline()

    metrics_path = ARTIFACTS / "model_evaluation" / "metrics.json"
    with open(metrics_path, encoding="utf-8") as handle:
        metrics = json.load(handle)
    assert set(metrics) >= {"MAE", "MSE", "RMSE", "R2"}
    for key in ("MAE", "MSE", "RMSE", "R2"):
        assert isinstance(metrics[key], int | float)

    feature_path = ARTIFACTS / "data_transformation" / "feature_columns.json"
    with open(feature_path, encoding="utf-8") as handle:
        features = json.load(handle)
    assert "model_version" in features
    assert isinstance(features.get("feature_order"), list)
    assert features.get("n_features") == len(features["feature_order"])

    manifest_path = MODEL_BUNDLE / "latest" / "manifest.json"
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    assert "model_version" in manifest
    assert "files" in manifest
    assert "created_at" in manifest
    bundle_dir = MODEL_BUNDLE / manifest["model_version"]
    required = (
        "model.pkl",
        "label_encoders.pkl",
        "feature_columns.json",
        "manifest.json",
    )
    for name in required:
        assert (bundle_dir / name).is_file()


def test_transform_source_change_preserves_validation_ledger_bytes():
    """
    Editing transformation implementation must not rewrite validation's ledger
    when validation itself did not re-run.
    """

    transform_src = PROJECT_ROOT / "src" / "components" / "data_transformation.py"
    original = transform_src.read_text()
    before_validation = snapshot_pipeline_stage_files("data_validation")
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    transform_src.write_text(original + "\n# transform-impl probe\n")
    try:
        run_pipeline()
        assert before_validation == snapshot_pipeline_stage_files("data_validation")
        assert len(mlflow_runs()) == len(before_runs) + 1
        assert len(version_dirs()) == len(before_versions) + 1
    finally:
        transform_src.write_text(original)
        realign_pipeline_after_restore()


def test_validation_pipeline_module_change_triggers_version_bump():
    """
    Editing data_validation_pipeline.py is a lineage-changing implementation edit.
    """

    pipeline_src = PROJECT_ROOT / "src" / "pipeline" / "data_validation_pipeline.py"
    original = pipeline_src.read_text()
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    pipeline_src.write_text(original + "\n# validation-pipeline probe\n")
    try:
        run_pipeline()
        assert len(mlflow_runs()) == len(before_runs) + 1
        assert len(version_dirs()) == len(before_versions) + 1
    finally:
        pipeline_src.write_text(original)
        realign_pipeline_after_restore()


def test_trainer_pipeline_module_change_is_fit_only():
    """
    Fit-or-later / lineage boundary: editing model_trainer_pipeline.py refits
    without minting a new semver; upstream ledgers stay bitwise identical.
    """

    pipeline_src = PROJECT_ROOT / "src" / "pipeline" / "model_trainer_pipeline.py"
    original = pipeline_src.read_text()
    before_runs = mlflow_runs()
    before_versions = version_dirs()
    before_lineage = feature_model_version()
    before_upstream = snapshot_pipeline_stage_files(
        "data_validation",
        "data_transformation",
    )

    pipeline_src.write_text(original + "\n# trainer-pipeline probe\n")
    try:
        run_pipeline()
        assert len(mlflow_runs()) == len(before_runs) + 1
        assert len(version_dirs()) == len(before_versions)
        assert feature_model_version() == before_lineage
        assert before_upstream == snapshot_pipeline_stage_files(
            "data_validation",
            "data_transformation",
        )
    finally:
        pipeline_src.write_text(original)
        realign_pipeline_after_restore()


def test_ledger_dependencies_exclude_pycache():
    """
    Generated __pycache__ paths must not appear in any stage dependency map.
    """

    run_pipeline()
    for stage_id in EXPECTED_PIPELINE_STAGES:
        deps = load_stage_metadata(stage_id)["dependencies"]
        for path in deps:
            assert "__pycache__" not in path
            assert not path.endswith(".pyc")


def test_stage_ledger_tracks_defining_src_modules():
    """
    Lineage/material-state rule: each stage must fingerprint both its
    component module under src/components/ and its pipeline wrapper under
    src/pipeline/ (not merely one of the two).
    """

    run_pipeline()
    expected = {
        "data_validation": (
            "src/components/data_validation.py",
            "src/pipeline/data_validation_pipeline.py",
        ),
        "data_transformation": (
            "src/components/data_transformation.py",
            "src/pipeline/data_transformation_pipeline.py",
        ),
        "model_trainer": (
            "src/components/model_trainer.py",
            "src/pipeline/model_trainer_pipeline.py",
        ),
        "model_evaluation": (
            "src/components/model_evaluation.py",
            "src/pipeline/model_evaluation_pipeline.py",
        ),
        "model_packaging": (
            "src/components/model_packager.py",
            "src/pipeline/model_packaging_pipeline.py",
        ),
    }
    for stage_id, required_paths in expected.items():
        deps = load_stage_metadata(stage_id)["dependencies"]
        for required in required_paths:
            assert required in deps, f"{stage_id} missing dependency {required}"


def test_ledger_records_have_no_extra_fields():
    """
    Ledger JSON must not carry stub/cache_key extras—only stage bookkeeping
    fields required by the instruction.
    """

    run_pipeline()
    allowed = {"stage", "status", "completed_at", "dependencies", "outputs"}
    for stage_id in EXPECTED_PIPELINE_STAGES:
        record = load_stage_metadata(stage_id)
        extra = set(record) - allowed
        assert not extra, f"{stage_id} has unexpected ledger fields: {extra}"


def test_feature_engineering_util_change_triggers_version_bump():
    """
    Transformation relies on src/utils/feature_engineering.py; editing it is a
    lineage-changing upstream invalidation (new semver + FileStore run).
    """

    util_src = PROJECT_ROOT / "src" / "utils" / "feature_engineering.py"
    original = util_src.read_text()
    before_runs = mlflow_runs()
    before_versions = version_dirs()

    util_src.write_text(original + "\n# feature-engineering util probe\n")
    try:
        run_pipeline()
        assert len(mlflow_runs()) == len(before_runs) + 1
        assert len(version_dirs()) == len(before_versions) + 1
    finally:
        util_src.write_text(original)
        realign_pipeline_after_restore()


def test_evaluation_source_change_is_fit_only():
    """
    Fit-or-later rule: editing model_evaluation.py must not mint a new semver
    or rewrite upstream ledgers; evaluation re-run adds exactly one FileStore run.
    """

    eval_src = PROJECT_ROOT / "src" / "components" / "model_evaluation.py"
    original = eval_src.read_text()
    before_runs = mlflow_runs()
    before_versions = version_dirs()
    before_lineage = feature_model_version()
    before_upstream = snapshot_pipeline_stage_files(
        "data_validation",
        "data_transformation",
        "model_trainer",
    )

    eval_src.write_text(original + "\n# evaluation-source probe\n")
    try:
        run_pipeline()
        assert len(mlflow_runs()) == len(before_runs) + 1
        assert len(version_dirs()) == len(before_versions)
        assert feature_model_version() == before_lineage
        assert before_upstream == snapshot_pipeline_stage_files(
            "data_validation",
            "data_transformation",
            "model_trainer",
        )
    finally:
        eval_src.write_text(original)
        realign_pipeline_after_restore()


def test_packaging_source_change_is_packaging_only():
    """
    Packaging-only rule: editing model_packager.py must not mint a new semver
    or create a new FileStore run; upstream ledgers stay bitwise identical.
    """

    packager_src = PROJECT_ROOT / "src" / "components" / "model_packager.py"
    original = packager_src.read_text()
    before_runs = mlflow_runs()
    before_versions = version_dirs()
    before_lineage = feature_model_version()
    before_upstream = snapshot_pipeline_stage_files(
        "data_validation",
        "data_transformation",
        "model_trainer",
        "model_evaluation",
    )

    packager_src.write_text(original + "\n# packaging-source probe\n")
    try:
        run_pipeline()
        assert len(mlflow_runs()) == len(before_runs)
        assert len(version_dirs()) == len(before_versions)
        assert feature_model_version() == before_lineage
        assert before_upstream == snapshot_pipeline_stage_files(
            "data_validation",
            "data_transformation",
            "model_trainer",
            "model_evaluation",
        )
    finally:
        packager_src.write_text(original)
        realign_pipeline_after_restore()


def test_flask_inference_remains_usable():
    """
    Instruction rule: Flask inference must stay usable after training.
    Exercises app.py health, home template, and /api/predict against the
    packaged latest bundle.
    """

    run_pipeline()
    previous_cwd = Path.cwd()
    try:
        import os

        os.chdir(PROJECT_ROOT)
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        for module_name in (
            "app",
            "src.pipeline.prediction_pipeline",
        ):
            sys.modules.pop(module_name, None)

        import app as flask_app

        assert flask_app.predictor is not None, "PredictionPipeline failed to load"
        client = flask_app.app.test_client()

        home = client.get("/")
        assert home.status_code == 200
        assert b"form" in home.data.lower() or b"predict" in home.data.lower()

        health = client.get("/health")
        assert health.status_code == 200
        health_payload = health.get_json()
        assert health_payload["model_loaded"] is True
        assert health_payload["bundle_exists"] is True

        frame = pd.read_csv(PROJECT_ROOT / "dataset" / "Cloud_Dataset.csv")
        sample = frame.iloc[0].to_dict()
        payload = {
            "timestamp": str(sample["timestamp"]),
            "cpu_usage": float(sample["cpu_usage"]),
            "memory_usage": float(sample["memory_usage"]),
            "net_io": float(sample["net_io"]),
            "disk_io": float(sample["disk_io"]),
            "cloud_provider": str(sample["cloud_provider"]),
            "region": str(sample["region"]),
            "vm_type": str(sample["vm_type"]),
            "vCPU": int(sample["vCPU"]),
            "RAM_GB": float(sample["RAM_GB"]),
            "target": str(sample["target"]),
            "latency_ms": float(sample["latency_ms"]),
            "throughput": float(sample["throughput"]),
            "utilization": float(sample["utilization"]),
        }
        predict = client.post("/api/predict", json=payload)
        assert predict.status_code == 200, predict.get_data(as_text=True)
        predict_payload = predict.get_json()
        assert predict_payload["status"] == "success"
        assert isinstance(predict_payload["prediction"], float | int)
    finally:
        import os

        os.chdir(previous_cwd)
