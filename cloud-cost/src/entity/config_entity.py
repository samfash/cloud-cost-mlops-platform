#!/usr/bin/env python3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DataValidationConfig:
    root_dir: Path
    local_data_file: Path
    STATUS_FILE: str
    all_schema: dict


# -------------------------------------------------------


@dataclass
class DataTransformationConfig:
    root_dir: Path
    data_path: Path


# -------------------------------------------------------


@dataclass
class ModelTrainerConfig:
    root_dir: Path
    train_data_path: Path
    test_data_path: Path
    model_name: str


# -------------------------------------------------------


@dataclass
class ModelEvaluationConfig:
    root_dir: Path
    test_data_path: Path
    model_path: Path
    metric_file_name: Path


@dataclass(frozen=True)
class ModelPackagerConfig:
    root_dir: Path
    model_path: Path
    label_encoders_path: Path
    feature_schema_path: Path
    metrics_path: Path
    r2_minor_bump_threshold: float
    r2_major_bump_threshold: float
    mae_regression_tolerance: float
    r2_floor: float
    mae_ceiling: float
    allow_nonimproving_patch: bool
