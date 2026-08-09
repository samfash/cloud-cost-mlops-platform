#!/usr/bin/env python3
import sys

import yaml

from src.components.model_trainer import ModelTrainer
from src.config.configuration import ConfigurationManager
from src.exception.exception import CustomException
from src.logging.logger import logging

STAGE_NAME = "Model Trainer Stage"


class ModelTrainerTrainingPipeline:
    def __init__(self):
        pass

    def initiate_model_trainer(self):
        try:
            config = ConfigurationManager()
            model_trainer_config = config.get_model_trainer_config()

            # Load params from params.yaml
            with open("params.yaml") as f:
                params = yaml.safe_load(f)["RandomForest"]

            model_trainer = ModelTrainer(config=model_trainer_config, params=params)
            model_trainer.start_model_trainer()

        except Exception as e:
            raise CustomException(e, sys) from e


if __name__ == "__main__":
    try:
        logging.info(f">>>>>> {STAGE_NAME} started <<<<<<")
        obj = ModelTrainerTrainingPipeline()
        obj.initiate_model_trainer()
        logging.info(f">>>>>> {STAGE_NAME} completed <<<<<<\n\nx==========x")
    except Exception as e:
        logging.exception(e)
        raise CustomException(e, sys) from e
