#!/usr/bin/env python3
import sys
from pathlib import Path

from src.components.data_transformation import DataTransformation
from src.config.configuration import ConfigurationManager
from src.exception.exception import CustomException
from src.logging.logger import logging

STAGE_NAME = "Data Transformation Stage"


class DataTransformationTrainingPipeline:
    def __init__(self):
        pass

    def initiate_data_transformation(self):
        try:
            with open(Path("artifacts/data_validation/status.txt")) as f:
                status_content = f.read().strip().split(" ")[-1].lower()
                if status_content == "true":
                    logging.info("Validation passed. Proceeding to transformation.")
                else:
                    logging.warning("Validation failed or not passed. Skipping transformation.")

                config = ConfigurationManager()
                data_transformation_config = config.get_data_transformation_config()
                data_transformation = DataTransformation(config=data_transformation_config)
                data_transformation.start_initiate_data_transformation()

        except Exception as e:
            logging.error(f"Error in {STAGE_NAME}: {e!s}")
            raise CustomException(e, sys) from e
