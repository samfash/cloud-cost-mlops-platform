#!/usr/bin/env python3
import os

from src.constants import CONFIG_FILE_PATH, PARAMS_FILE_PATH, SCHEMA_FILE_PATH
from src.entity.config_entity import (
    DataTransformationConfig,
    DataValidationConfig,
    ModelEvaluationConfig,
    ModelPackagerConfig,
    ModelTrainerConfig,
)
from src.utils.common import create_directories, read_yaml


class ConfigurationManager:
    def __init__(
        self,
        config_filepath=CONFIG_FILE_PATH,
        params_filepath=PARAMS_FILE_PATH,
        schema_filepath=SCHEMA_FILE_PATH,
    ):
        self.config = read_yaml(config_filepath)
        self.params = read_yaml(params_filepath)
        self.schema = read_yaml(schema_filepath)
        create_directories([self.config.artifacts_root])

    # ----------------------------------------------------------------------------------
    def get_data_validation_config(self) -> DataValidationConfig:
        config = self.config.data_validation
        schema = self.schema.COLUMNS

        create_directories([config.root_dir])

        return DataValidationConfig(
            root_dir=config.root_dir,
            local_data_file=config.local_data_file,
            STATUS_FILE=config.STATUS_FILE,
            all_schema=schema,
        )

    # ---------------------------------------------------------------------------------
    def get_data_transformation_config(self) -> DataTransformationConfig:
        config = self.config.data_transformation
        create_directories([config.root_dir])

        return DataTransformationConfig(root_dir=config.root_dir, data_path=config.data_path)

    # ----------------------------------------------------------------------------------

    def get_model_trainer_config(self) -> ModelTrainerConfig:
        config = self.config.model_trainer
        create_directories([config.root_dir])

        return ModelTrainerConfig(
            root_dir=config.root_dir,
            train_data_path=config.train_data_path,
            test_data_path=config.test_data_path,
            model_name=config.model_name,
        )

    # ----------------------------------------------------------------------------------

    def get_model_evaluation_config(self) -> ModelEvaluationConfig:
        config = self.config.model_evaluation
        os.makedirs(config.root_dir, exist_ok=True)

        return ModelEvaluationConfig(
            root_dir=config.root_dir,
            test_data_path=config.test_data_path,
            model_path=config.model_path,
            metric_file_name=config.metric_file_name,
        )

    def get_model_packager_config(self) -> ModelPackagerConfig:
        config = self.config.model_packager
        os.makedirs(config.root_dir, exist_ok=True)

        return ModelPackagerConfig(
            root_dir=config.root_dir,
            model_path=config.model_path,
            label_encoders_path=config.label_encoders_path,
            feature_schema_path=config.feature_schema_path,
            metrics_path=config.metrics_path,
            r2_minor_bump_threshold=float(config.r2_minor_bump_threshold),
            r2_major_bump_threshold=float(config.r2_major_bump_threshold),
            mae_regression_tolerance=float(config.mae_regression_tolerance),
            r2_floor=float(config.r2_floor),
            mae_ceiling=float(config.mae_ceiling),
            allow_nonimproving_patch=bool(config.allow_nonimproving_patch),
        )
