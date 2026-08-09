#!/usr/bin/env python3
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
            )

            model.fit(X_train, y_train)
            logging.info("RandomForest training completed.")

            # Save model
            model_path = os.path.join(self.config.root_dir, self.config.model_name)
            with open(model_path, "wb") as f:
                pickle.dump(model, f)
            logging.info(f"Model saved at {model_path}")

            # Evaluate
            y_pred = model.predict(X_test)
            mae = mean_absolute_error(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test, y_pred)

            metrics = {"MAE": mae, "MSE": mse, "RMSE": rmse, "R2": r2}
            logging.info(f"Model metrics: {metrics}")

            metrics_path = os.path.join(self.config.root_dir, "metrics.json")
            pd.Series(metrics).to_json(metrics_path)
            logging.info(f"Metrics saved at {metrics_path}")

        except Exception as e:
            raise CustomException(e, sys) from e
