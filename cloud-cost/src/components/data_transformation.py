#!/usr/bin/env python3
import json
import os
import pickle
import sys

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from src.config.configuration import DataTransformationConfig
from src.exception.exception import CustomException
from src.logging.logger import logging
from src.utils.feature_engineering import (
    CATEGORICAL_COLUMNS,
    add_engineered_features,
    add_temporal_features,
)

MODEL_VERSION = "1.0.0"


class DataTransformation:
    def __init__(self, config: DataTransformationConfig):
        self.config = config
        self.model_version = os.environ.get("MODEL_VERSION", MODEL_VERSION)

    def feature_engineering(self, df: pd.DataFrame):
        try:
            logging.info("Starting feature engineering...")

            # Temporal features (shared with inference)
            df = add_temporal_features(df, timestamp_col="timestamp")

            # Fit + apply categorical encoding.
            # Fitting only ever happens here; inference re-uses these same
            # encoders via src.utils.feature_engineering.encode_categorical_columns.
            label_encoders = {}
            for col in CATEGORICAL_COLUMNS:
                le = LabelEncoder()
                df[col + "_encoded"] = le.fit_transform(df[col])
                label_encoders[col] = le

            logging.info(f"Categorical encoding done: {CATEGORICAL_COLUMNS}")

            encoder_path = os.path.join(self.config.root_dir, "label_encoders.pkl")
            with open(encoder_path, "wb") as f:
                pickle.dump(label_encoders, f)
            logging.info(f"Label encoders saved at {encoder_path}")

            # Ratio / interaction features (shared with inference)
            df = add_engineered_features(df)

            logging.info("Feature engineering completed successfully.")
            return df

        except Exception as e:
            raise CustomException(e, sys) from e

    def start_initiate_data_transformation(self):
        try:
            logging.info("Data Transformation started.")

            df = pd.read_csv(self.config.data_path)
            df.columns = df.columns.str.strip()
            logging.info(f"Loaded data with shape: {df.shape}")

            df = self.feature_engineering(df)

            target_col = "cost"
            exclude_cols = ["cost", "price_per_hour", "cost_to_price_ratio"]
            categorical_cols = CATEGORICAL_COLUMNS

            feature_cols = [
                col
                for col in df.columns
                if col not in exclude_cols
                and (col.endswith("_encoded") or col not in categorical_cols)
            ]

            X = df[feature_cols]
            y = df[target_col]

            logging.info(f"Feature columns: {len(feature_cols)}, Target: {target_col}")

            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Combine back for saving
            train = pd.concat([X_train, y_train], axis=1)
            test = pd.concat([X_test, y_test], axis=1)

            # Save the exact feature column order so inference can align to it
            os.makedirs(self.config.root_dir, exist_ok=True)
            feature_order = [c for c in feature_cols if c != target_col]
            feature_schema = {
                "model_version": self.model_version,
                "feature_order": feature_order,
                "n_features": len(feature_order),
            }
            feature_cols_path = os.path.join(self.config.root_dir, "feature_columns.json")
            with open(feature_cols_path, "w") as f:
                json.dump(feature_schema, f, indent=2)
            logging.info(f"Feature schema saved at {feature_cols_path}")

            train.to_csv(os.path.join(self.config.root_dir, "train.csv"), index=False)
            test.to_csv(os.path.join(self.config.root_dir, "test.csv"), index=False)

            logging.info(f"Data split done: Train={train.shape}, Test={test.shape}")
            logging.info("Data Transformation completed successfully.")

        except Exception as e:
            raise CustomException(e, sys) from e
