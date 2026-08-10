#!/usr/bin/env python3
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.config.configuration import ModelTrainerConfig
from src.exception.exception import CustomException
from src.logging.logger import logging


def _regression_bundle(y_true, y_pred) -> dict:
    mae = float(mean_absolute_error(y_true, y_pred))
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(np.sqrt(mse))
    r2 = float(r2_score(y_true, y_pred))
    return {"MAE": mae, "MSE": mse, "RMSE": rmse, "R2": r2}


class ModelTrainer:
    def __init__(self, config: ModelTrainerConfig, params):
        self.config = config
        self.params = params

    def start_model_trainer(self):
        try:
            logging.info("Model training started...")

            train = pd.read_csv(self.config.train_data_path)
            test = pd.read_csv(self.config.test_data_path)

            X_train = train.drop(columns=["cost"])
            y_train = train["cost"]
            X_test = test.drop(columns=["cost"])
            y_test = test["cost"]

            logging.info(f"Train shape: {X_train.shape}, Test shape: {X_test.shape}")

            model = RandomForestRegressor(
                n_estimators=self.params["n_estimators"],
                max_depth=self.params["max_depth"],
                min_samples_split=self.params["min_samples_split"],
                min_samples_leaf=self.params["min_samples_leaf"],
                max_features=self.params["max_features"],
                random_state=self.params["random_state"],
                n_jobs=-1,
                oob_score=True,
                bootstrap=True,
            )

            model.fit(X_train, y_train)
            logging.info("RandomForest training completed.")

            model_path = os.path.join(self.config.root_dir, self.config.model_name)
            with open(model_path, "wb") as f:
                pickle.dump(model, f)
            logging.info(f"Model saved at {model_path}")

            train_pred = model.predict(X_train)
            test_pred = model.predict(X_test)
            train_metrics = _regression_bundle(y_train, train_pred)
            test_metrics = _regression_bundle(y_test, test_pred)

            metrics = {
                **test_metrics,  # packaging gates read top-level MAE/R2 as holdout
                "train_MAE": train_metrics["MAE"],
                "train_RMSE": train_metrics["RMSE"],
                "train_R2": train_metrics["R2"],
                "test_MAE": test_metrics["MAE"],
                "test_RMSE": test_metrics["RMSE"],
                "test_R2": test_metrics["R2"],
                "gap_MAE": float(test_metrics["MAE"] - train_metrics["MAE"]),
                "gap_R2": float(train_metrics["R2"] - test_metrics["R2"]),
                "oob_score": float(getattr(model, "oob_score_", float("nan"))),
            }
            logging.info(
                "Bias/variance signal — train_R2=%.6f test_R2=%.6f gap_R2=%.6f oob=%.6f",
                metrics["train_R2"],
                metrics["test_R2"],
                metrics["gap_R2"],
                metrics["oob_score"],
            )

            metrics_path = os.path.join(self.config.root_dir, "metrics.json")
            with open(metrics_path, "w", encoding="utf-8") as handle:
                json.dump(metrics, handle, indent=2)
            logging.info(f"Metrics saved at {metrics_path}")

        except Exception as e:
            raise CustomException(e, sys) from e
