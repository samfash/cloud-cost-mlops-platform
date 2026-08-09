"""Dependency-aware pipeline executor."""

from __future__ import annotations

import sys
from typing import Callable

from src.exception.exception import CustomException
from src.logging.logger import logging
from src.pipeline.data_transformation_pipeline import DataTransformationTrainingPipeline
from src.pipeline.data_validation_pipeline import DataValidationTrainingPipeline
from src.pipeline.dependency_tracker import (
    DependencyTracker,
    outputs_structurally_valid,
)
from src.pipeline.model_evaluation_pipeline import ModelEvaluationTrainingPipeline
from src.pipeline.model_packaging_pipeline import ModelPackagingPipeline
from src.pipeline.model_trainer_pipeline import ModelTrainerTrainingPipeline
from src.pipeline.stage_definitions import PIPELINE_STAGES, StageSpec


class PipelineExecutor:
    """Run the training pipeline according to the declared dependency graph."""

    def __init__(self, tracker: DependencyTracker | None = None):
        self.tracker = tracker or DependencyTracker()
        self._runners: dict[str, Callable[[], None]] = {
            "data_validation": self._run_data_validation,
            "data_transformation": self._run_data_transformation,
            "model_trainer": self._run_model_trainer,
            "model_evaluation": self._run_model_evaluation,
            "model_packaging": self._run_model_packaging,
        }

    def is_stage_complete(self, stage: StageSpec, upstream_valid: bool) -> bool:
        if not upstream_valid:
            return False

        metadata = self.tracker.load_metadata(stage.stage_id)
        if not metadata or metadata.get("status") != "success":
            return False

        if not self.tracker.dependency_hashes_match(stage.stage_id, stage.dependencies):
            logging.info(f"Stage '{stage.stage_id}' invalid: dependency digests changed")
            return False

        stage_outputs = stage.get_outputs()
        if not outputs_structurally_valid(stage_outputs):
            logging.info(f"Stage '{stage.stage_id}' invalid: owned artifacts missing or corrupt")
            return False

        if not self.tracker.output_hashes_match(stage.stage_id, list(stage_outputs.keys())):
            logging.info(f"Stage '{stage.stage_id}' invalid: output digests do not match metadata")
            return False

        return True

    def plan_execution(self) -> list[tuple[StageSpec, bool]]:
        plan: list[tuple[StageSpec, bool]] = []
        force_downstream = False
        stage_validity: dict[str, bool] = {}

        for stage in PIPELINE_STAGES:
            upstream_ok = all(stage_validity.get(uid, False) for uid in stage.upstream)
            if force_downstream:
                must_run = True
            else:
                complete = self.is_stage_complete(stage, upstream_valid=upstream_ok)
                must_run = not complete

            plan.append((stage, must_run))
            stage_validity[stage.stage_id] = not must_run
            if must_run:
                force_downstream = True

        return plan

    def run(self) -> None:
        plan = self.plan_execution()

        for stage, must_run in plan:
            stage_name = stage.display_name
            try:
                if not must_run:
                    logging.info(
                        f">>>>>> stage {stage_name} skipped "
                        f"(artifacts valid; dependencies unchanged) <<<<<<\n\nx==========x"
                    )
                    continue

                logging.info(f">>>>>> stage {stage_name} started <<<<<<")
                runner = self._runners[stage.stage_id]
                runner()
                stage_outputs = stage.get_outputs()
                if outputs_structurally_valid(stage_outputs):
                    self.tracker.save_metadata(
                        stage.stage_id,
                        dependencies=stage.dependencies,
                        outputs=list(stage_outputs.keys()),
                    )
                    logging.info(f">>>>>> stage {stage_name} completed <<<<<<\n\nx==========x")
                else:
                    logging.warning(
                        f"Stage '{stage.stage_id}' finished without valid owned "
                        f"artifacts; pipeline metadata was not updated"
                    )
                    logging.info(f">>>>>> stage {stage_name} completed <<<<<<\n\nx==========x")
            except Exception as e:
                logging.exception(e)
                raise CustomException(e, sys) from e

    @staticmethod
    def _run_data_validation() -> None:
        DataValidationTrainingPipeline().initiate_data_validation()

    @staticmethod
    def _run_data_transformation() -> None:
        DataTransformationTrainingPipeline().initiate_data_transformation()

    @staticmethod
    def _run_model_trainer() -> None:
        ModelTrainerTrainingPipeline().initiate_model_trainer()

    @staticmethod
    def _run_model_evaluation() -> None:
        ModelEvaluationTrainingPipeline().initiate_model_evaluation()

    @staticmethod
    def _run_model_packaging() -> None:
        ModelPackagingPipeline().initiate_model_packaging()
