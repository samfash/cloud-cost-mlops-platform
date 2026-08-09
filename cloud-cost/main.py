from src.logging.logger import logging
from src.pipeline.pipeline_executor import PipelineExecutor

logging.info("Starting dependency-aware training pipeline")
PipelineExecutor().run()
logging.info("Training pipeline finished")
