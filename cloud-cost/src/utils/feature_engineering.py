#!/usr/bin/env python3
import sys

import pandas as pd

from src.exception.exception import CustomException
from src.logging.logger import logging

# Categorical columns that get a `<col>_encoded` counterpart via LabelEncoder.
CATEGORICAL_COLUMNS = ["cloud_provider", "region", "vm_type", "target"]


def add_temporal_features(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
    try:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        df["hour"] = df[timestamp_col].dt.hour
        df["day"] = df[timestamp_col].dt.day
        df["month"] = df[timestamp_col].dt.month
        df["day_of_week"] = df[timestamp_col].dt.dayofweek
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
        return df.drop(timestamp_col, axis=1)
    except Exception as e:
        raise CustomException(e, sys) from e


def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df["cpu_memory_ratio"] = df["cpu_usage"] / (df["memory_usage"] + 1)
        df["total_io"] = df["net_io"] + df["disk_io"]
        df["io_ratio"] = df["net_io"] / (df["disk_io"] + 1)
        df["resource_efficiency"] = df["throughput"] / (df["cpu_usage"] + df["memory_usage"] + 1)
        df["latency_throughput_ratio"] = df["latency_ms"] / (df["throughput"] + 1)
        df["resource_intensity"] = df["cpu_usage"] * df["memory_usage"] * df["utilization"]
        df["ram_per_vcpu"] = df["RAM_GB"] / df["vCPU"]
        return df
    except Exception as e:
        raise CustomException(e, sys) from e


def encode_categorical_columns(
    df: pd.DataFrame, label_encoders: dict, categorical_cols=CATEGORICAL_COLUMNS
) -> pd.DataFrame:
    try:
        for col in categorical_cols:
            if label_encoders and col in label_encoders:
                le = label_encoders[col]
                known_classes = set(le.classes_)
                df[col + "_encoded"] = df[col].apply(
                    lambda v, encoder=le, known=known_classes: (
                        encoder.transform([v])[0] if v in known else 0
                    )
                )
            else:
                logging.warning(
                    f"No label encoder found for '{col}', defaulting encoded value to 0"
                )
                df[col + "_encoded"] = 0
        return df
    except Exception as e:
        raise CustomException(e, sys) from e
