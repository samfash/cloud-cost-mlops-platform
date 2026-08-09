#!/usr/bin/env python3
import pickle
import sys

import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.config.configuration import ModelEvaluationConfig
from src.exception.exception import CustomException
from src.logging.logger import logging


class ModelEvaluation:
    def __init__(self, config: ModelEvaluationConfig):
        self.config = config

    def start_model_evaluation(self):
        try:
            logging.info("Starting model evaluation...")

            # Load model
            with open(self.config.model_path, "rb") as f:
                model = pickle.load(f)
            logging.info(f"Model loaded from {self.config.model_path}")

            # Load test data
            test = pd.read_csv(self.config.test_data_path)
            X_test = test.drop(columns=["cost"])
            y_test = test["cost"]

            # Predict
            y_pred = model.predict(X_test)

            # Evaluate metrics
            mae = mean_absolute_error(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test, y_pred)

            metrics = {"MAE": mae, "MSE": mse, "RMSE": rmse, "R2": r2}
            logging.info(f"Evaluation metrics: {metrics}")

            # Save metrics to JSON
            pd.Series(metrics).to_json(self.config.metric_file_name)
            logging.info(f"Metrics saved at {self.config.metric_file_name}")

            with mlflow.start_run():
                # Log metrics
                for metric_name, metric_value in metrics.items():
                    mlflow.log_metric(metric_name, metric_value)

                # Log model as artifact
                mlflow.log_artifact(self.config.model_path, artifact_path="model")
                logging.info("Metrics and model logged to MLflow successfully.")

            return metrics

        except Exception as e:
            raise CustomException(e, sys) from e
