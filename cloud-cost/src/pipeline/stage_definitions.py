"""Declarative pipeline stage graph: ownership, dependencies, and validators."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from src.pipeline.dependency_tracker import (
    validate_cas_bundle_head,
    validate_csv_with_cost,
    validate_feature_columns_json,
    validate_label_encoders,
    validate_metrics_json,
    validate_pickle,
    validate_status_txt,
)

DATASET_PATH = "dataset/Cloud_Dataset.csv"
SCHEMA_PATH = "schema.yaml"
PARAMS_PATH = "params.yaml"
CONFIG_PATH = "config/config.yaml"

VALIDATION_STATUS = "artifacts/data_validation/status.txt"
TRAIN_CSV = "artifacts/data_transformation/train.csv"
TEST_CSV = "artifacts/data_transformation/test.csv"
LABEL_ENCODERS = "artifacts/data_transformation/label_encoders.pkl"
FEATURE_COLUMNS = "artifacts/data_transformation/feature_columns.json"
MODEL_PKL = "artifacts/model_trainer/model.pkl"
TRAINER_METRICS = "artifacts/model_trainer/metrics.json"
EVAL_METRICS = "artifacts/model_evaluation/metrics.json"
BUNDLE_HEAD = "artifacts/model_bundle/HEAD"


@dataclass(frozen=True)
class StageSpec:
    """One node in the pipeline dependency graph."""

    stage_id: str
    display_name: str
    dependencies: Sequence[str]
    outputs: dict[str, Callable[[Path], bool]] = field(default_factory=dict)
    upstream: Sequence[str] = field(default_factory=tuple)
    outputs_resolver: Callable[[], dict[str, Callable[[Path], bool]]] | None = None

    def get_outputs(self) -> dict[str, Callable[[Path], bool]]:
        if self.outputs_resolver is not None:
            return self.outputs_resolver()
        return self.outputs

    @property
    def output_paths(self) -> list[str]:
        return list(self.get_outputs().keys())


DATA_VALIDATION = StageSpec(
    stage_id="data_validation",
    display_name="Data Validation Stage",
    dependencies=(
        DATASET_PATH,
        SCHEMA_PATH,
        CONFIG_PATH,
        "src/components/data_validation.py",
        "src/pipeline/data_validation_pipeline.py",
    ),
    outputs={VALIDATION_STATUS: validate_status_txt},
    upstream=(),
)

DATA_TRANSFORMATION = StageSpec(
    stage_id="data_transformation",
    display_name="Data Transformation Stage",
    dependencies=(
        VALIDATION_STATUS,
        DATASET_PATH,
        SCHEMA_PATH,
        CONFIG_PATH,
        "src/components/data_transformation.py",
        "src/pipeline/data_transformation_pipeline.py",
        "src/utils/feature_engineering.py",
    ),
    outputs={
        LABEL_ENCODERS: validate_label_encoders,
        FEATURE_COLUMNS: validate_feature_columns_json,
        TRAIN_CSV: validate_csv_with_cost,
        TEST_CSV: validate_csv_with_cost,
    },
    upstream=("data_validation",),
)

MODEL_TRAINER = StageSpec(
    stage_id="model_trainer",
    display_name="Model Trainer Stage",
    dependencies=(
        TRAIN_CSV,
        TEST_CSV,
        PARAMS_PATH,
        CONFIG_PATH,
        "src/components/model_trainer.py",
        "src/pipeline/model_trainer_pipeline.py",
    ),
    outputs={
        MODEL_PKL: validate_pickle,
        TRAINER_METRICS: validate_metrics_json,
    },
    upstream=("data_transformation",),
)

MODEL_EVALUATION = StageSpec(
    stage_id="model_evaluation",
    display_name="Model Evaluation Stage",
    dependencies=(
        MODEL_PKL,
        TEST_CSV,
        CONFIG_PATH,
        "src/components/model_evaluation.py",
        "src/pipeline/model_evaluation_pipeline.py",
    ),
    outputs={
        EVAL_METRICS: validate_metrics_json,
    },
    upstream=("model_trainer",),
)

MODEL_PACKAGING = StageSpec(
    stage_id="model_packaging",
    display_name="Model packaging Stage",
    dependencies=(
        MODEL_PKL,
        LABEL_ENCODERS,
        FEATURE_COLUMNS,
        EVAL_METRICS,
        CONFIG_PATH,
        "src/components/model_packager.py",
        "src/pipeline/model_packaging_pipeline.py",
    ),
    outputs={BUNDLE_HEAD: validate_cas_bundle_head},
    upstream=("model_evaluation",),
)

PIPELINE_STAGES: Sequence[StageSpec] = (
    DATA_VALIDATION,
    DATA_TRANSFORMATION,
    MODEL_TRAINER,
    MODEL_EVALUATION,
    MODEL_PACKAGING,
)
