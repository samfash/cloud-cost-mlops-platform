#!/usr/bin/env python3
import json
import pickle
import sys
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import yaml
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.config.configuration import ModelEvaluationConfig
from src.exception.exception import CustomException
from src.logging.logger import logging


def _regression_bundle(y_true, y_pred) -> dict:
    mae = float(mean_absolute_error(y_true, y_pred))
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(np.sqrt(mse))
    r2 = float(r2_score(y_true, y_pred))
    return {"MAE": mae, "MSE": mse, "RMSE": rmse, "R2": r2}


class ModelEvaluation:
    def __init__(self, config: ModelEvaluationConfig):
        self.config = config

    def start_model_evaluation(self):
        try:
            logging.info("Starting model evaluation...")

            with open(self.config.model_path, "rb") as f:
                model = pickle.load(f)
            logging.info(f"Model loaded from {self.config.model_path}")

            train_path = Path(self.config.test_data_path).parent / "train.csv"
            test = pd.read_csv(self.config.test_data_path)
            X_test = test.drop(columns=["cost"])
            y_test = test["cost"]

            y_pred = model.predict(X_test)
            test_metrics = _regression_bundle(y_test, y_pred)

            metrics = {**test_metrics}

            if train_path.is_file():
                train = pd.read_csv(train_path)
                X_train = train.drop(columns=["cost"])
                y_train = train["cost"]
                train_pred = model.predict(X_train)
                train_metrics = _regression_bundle(y_train, train_pred)
                metrics.update(
                    {
                        "train_MAE": train_metrics["MAE"],
                        "train_RMSE": train_metrics["RMSE"],
                        "train_R2": train_metrics["R2"],
                        "test_MAE": test_metrics["MAE"],
                        "test_RMSE": test_metrics["RMSE"],
                        "test_R2": test_metrics["R2"],
                        "gap_MAE": float(test_metrics["MAE"] - train_metrics["MAE"]),
                        "gap_R2": float(train_metrics["R2"] - test_metrics["R2"]),
                    }
                )
                # Offline baseline for context (not a packaging gate).
                baseline = DummyRegressor(strategy="mean")
                baseline.fit(X_train, y_train)
                baseline_pred = baseline.predict(X_test)
                baseline_metrics = _regression_bundle(y_test, baseline_pred)
                metrics["baseline_mean_MAE"] = baseline_metrics["MAE"]
                metrics["baseline_mean_R2"] = baseline_metrics["R2"]
                metrics["lift_MAE_vs_baseline"] = float(
                    baseline_metrics["MAE"] - test_metrics["MAE"]
                )

            # Precision/recall are classification metrics — N/A for cost regression.
            metrics["metric_family"] = "regression"
            metrics["precision_recall_applicable"] = False

            logging.info(f"Evaluation metrics: {metrics}")

            with open(self.config.metric_file_name, "w", encoding="utf-8") as handle:
                json.dump(metrics, handle, indent=2)
            logging.info(f"Metrics saved at {self.config.metric_file_name}")

            params_path = Path(__file__).resolve().parents[2] / "params.yaml"
            rf_params = {}
            if params_path.is_file():
                with params_path.open(encoding="utf-8") as handle:
                    loaded = yaml.safe_load(handle) or {}
                rf_params = loaded.get("RandomForest", {})

            with mlflow.start_run(run_name="cloud-cost-evaluation"):
                for key, value in rf_params.items():
                    mlflow.log_param(f"rf_{key}", value)
                mlflow.log_param("task_type", "regression")
                mlflow.log_param("label_column", "cost")
                for metric_name, metric_value in metrics.items():
                    if isinstance(metric_value, (int, float, np.floating)):
                        mlflow.log_metric(metric_name, float(metric_value))
                mlflow.log_artifact(self.config.model_path, artifact_path="model")
                mlflow.log_artifact(str(self.config.metric_file_name), artifact_path="metrics")
                logging.info("Metrics, params, and model logged to MLflow successfully.")

            return metrics

        except Exception as e:
            raise CustomException(e, sys) from e
