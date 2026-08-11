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

# Must not train latency on its own label or derived ratio.
LATENCY_LEAKAGE_COLS = ("latency_ms", "latency_throughput_ratio", "cost")


def _regression_bundle(y_true, y_pred) -> dict:
    mae = float(mean_absolute_error(y_true, y_pred))
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(np.sqrt(mse))
    r2 = float(r2_score(y_true, y_pred))
    return {"MAE": mae, "MSE": mse, "RMSE": rmse, "R2": r2}


def _rf_from_params(params) -> RandomForestRegressor:
    return RandomForestRegressor(
        n_estimators=params["n_estimators"],
        max_depth=params["max_depth"],
        min_samples_split=params["min_samples_split"],
        min_samples_leaf=params["min_samples_leaf"],
        max_features=params["max_features"],
        random_state=params["random_state"],
        n_jobs=-1,
        oob_score=True,
        bootstrap=True,
    )


class ModelTrainer:
    def __init__(self, config: ModelTrainerConfig, params):
        self.config = config
        self.params = params

    def _train_latency_model(self, train: pd.DataFrame, test: pd.DataFrame) -> None:
        """Train a separate RF for latency_ms; metrics gated separately from cost."""
        if "latency_ms" not in train.columns:
            logging.warning("latency_ms missing from train data; skipping latency model")
            return

        feature_cols = [
            c for c in train.columns if c not in LATENCY_LEAKAGE_COLS
        ]
        X_train = train[feature_cols]
        y_train = train["latency_ms"]
        X_test = test[feature_cols]
        y_test = test["latency_ms"]

        model = _rf_from_params(self.params)
        model.fit(X_train, y_train)

        model_path = os.path.join(self.config.root_dir, "latency_model.pkl")
        with open(model_path, "wb") as handle:
            pickle.dump(model, handle)

        train_metrics = _regression_bundle(y_train, model.predict(X_train))
        test_metrics = _regression_bundle(y_test, model.predict(X_test))
        metrics = {
            **test_metrics,
            "train_MAE": train_metrics["MAE"],
            "train_RMSE": train_metrics["RMSE"],
            "train_R2": train_metrics["R2"],
            "test_MAE": test_metrics["MAE"],
            "test_RMSE": test_metrics["RMSE"],
            "test_R2": test_metrics["R2"],
            "gap_MAE": float(test_metrics["MAE"] - train_metrics["MAE"]),
            "gap_R2": float(train_metrics["R2"] - test_metrics["R2"]),
            "oob_score": float(getattr(model, "oob_score_", float("nan"))),
            "label_column": "latency_ms",
            "metric_family": "regression",
            "model_class": "RandomForestRegressor",
            "n_features": len(feature_cols),
            "note": (
                "Latency model excludes latency_ms and latency_throughput_ratio "
                "from features (no label leakage). Cost packaging gates do not "
                "apply; see latency_metrics.json."
            ),
        }
        metrics_path = os.path.join(self.config.root_dir, "latency_metrics.json")
        with open(metrics_path, "w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2)

        schema = {
            "label_column": "latency_ms",
            "feature_order": feature_cols,
            "n_features": len(feature_cols),
            "excluded_leakage_columns": list(LATENCY_LEAKAGE_COLS),
        }
        schema_path = os.path.join(self.config.root_dir, "latency_feature_columns.json")
        with open(schema_path, "w", encoding="utf-8") as handle:
            json.dump(schema, handle, indent=2)

        logging.info(
            "Latency model saved — test_R2=%.6f test_MAE=%.6f features=%d",
            metrics["test_R2"],
            metrics["test_MAE"],
            len(feature_cols),
        )

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

            model = _rf_from_params(self.params)
            model.fit(X_train, y_train)
            logging.info("RandomForest cost training completed.")

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

            self._train_latency_model(train, test)

        except Exception as e:
            raise CustomException(e, sys) from e
