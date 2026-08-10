#!/usr/bin/env python3
import json
import os
import pickle
import sys
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from src.config.configuration import DataTransformationConfig
from src.exception.exception import CustomException
from src.feature_store import write_schema_snapshot
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
        # temporal = time-ordered holdout (reduces leakage vs random on timed rows)
        self.split_mode = os.environ.get("SPLIT_MODE", "temporal").strip().lower()
        if self.split_mode not in {"temporal", "random"}:
            self.split_mode = "temporal"

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

            if self.split_mode == "temporal" and "timestamp" in df.columns:
                df = df.sort_values("timestamp").reset_index(drop=True)
                logging.info("Sorted by timestamp for temporal holdout split.")

            df = self.feature_engineering(df)

            # Label is `cost`. Feature `target` is an operational categorical (scale_up/etc).
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

            if self.split_mode == "temporal":
                cut = int(len(df) * 0.8)
                if cut < 1 or cut >= len(df):
                    raise ValueError("Temporal split produced empty train or test")
                X_train, X_test = X.iloc[:cut], X.iloc[cut:]
                y_train, y_test = y.iloc[:cut], y.iloc[cut:]
            else:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42
                )

            train = pd.concat([X_train, y_train], axis=1)
            test = pd.concat([X_test, y_test], axis=1)

            os.makedirs(self.config.root_dir, exist_ok=True)
            feature_order = [c for c in feature_cols if c != target_col]
            feature_schema = {
                "model_version": self.model_version,
                "feature_order": feature_order,
                "n_features": len(feature_order),
                "split_mode": self.split_mode,
                "label_column": target_col,
                "excluded_leakage_columns": exclude_cols,
                "note": (
                    "Feature named 'target' is categorical scale intent, not the label. "
                    "Label column is 'cost'."
                ),
            }
            feature_cols_path = os.path.join(self.config.root_dir, "feature_columns.json")
            with open(feature_cols_path, "w") as f:
                json.dump(feature_schema, f, indent=2)
            logging.info(f"Feature schema saved at {feature_cols_path}")

            split_meta = {
                "split_mode": self.split_mode,
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "test_fraction": round(len(test) / max(len(train) + len(test), 1), 4),
            }
            with open(os.path.join(self.config.root_dir, "split_metadata.json"), "w") as f:
                json.dump(split_meta, f, indent=2)

            write_schema_snapshot(
                Path(self.config.root_dir) / "feature_store",
                feature_order=feature_order,
                model_version=self.model_version,
                split_mode=self.split_mode,
                extra={"label_column": target_col, "excluded": exclude_cols},
            )

            train.to_csv(os.path.join(self.config.root_dir, "train.csv"), index=False)
            test.to_csv(os.path.join(self.config.root_dir, "test.csv"), index=False)

            logging.info(
                "Data split done (%s): Train=%s, Test=%s",
                self.split_mode,
                train.shape,
                test.shape,
            )
            logging.info("Data Transformation completed successfully.")

        except Exception as e:
            raise CustomException(e, sys) from e
