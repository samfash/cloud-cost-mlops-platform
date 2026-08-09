#!/usr/bin/env python3
import sys

from src.components.model_evaluation import ModelEvaluation
from src.config.configuration import ConfigurationManager
from src.exception.exception import CustomException
from src.logging.logger import logging

STAGE_NAME = "Model Evaluation"


class ModelEvaluationTrainingPipeline:
    def __init__(self):
        pass

    def initiate_model_evaluation(self):
        try:
            config = ConfigurationManager()
            model_evaluation_config = config.get_model_evaluation_config()
            model_evaluation = ModelEvaluation(config=model_evaluation_config)
            model_evaluation.start_model_evaluation()
        except Exception as e:
            raise CustomException(e, sys) from e


if __name__ == "__main__":
    try:
        logging.info(f">>>>>> {STAGE_NAME} started <<<<<<")
        obj = ModelEvaluationTrainingPipeline()
        obj.initiate_model_evaluation()
        logging.info(f">>>>>> {STAGE_NAME} completed <<<<<<\n\nx==========x")
    except Exception as e:
        logging.exception(e)
        raise CustomException(e, sys) from e
