#!/usr/bin/env python3
import sys

from src.components.model_packager import ModelPackager
from src.config.configuration import ConfigurationManager
from src.exception.exception import CustomException
from src.logging.logger import logging

STAGE_NAME = "Model Packaging Stage"


class ModelPackagingPipeline:
    def __init__(self):
        pass

    def initiate_model_packaging(self):
        try:
            config = ConfigurationManager()
            model_packager_config = config.get_model_packager_config()
            model_packager = ModelPackager(config=model_packager_config)
            bundle_dir = model_packager.initiate_packaging()
            logging.info(f"{STAGE_NAME} completed. Bundle: {bundle_dir}")
            return bundle_dir
        except Exception as e:
            logging.error(f"Error in {STAGE_NAME}: {e!s}")
            raise CustomException(e, sys) from e


if __name__ == "__main__":
    pipeline = ModelPackagingPipeline()
    bundle_dir = pipeline.initiate_model_packaging()
    print(f"Pipeline completed successfully! Bundle created at: {bundle_dir}")
