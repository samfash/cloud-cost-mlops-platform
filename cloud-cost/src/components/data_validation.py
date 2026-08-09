#!/usr/bin/env python3
import sys

import pandas as pd

from src.config.configuration import DataValidationConfig
from src.exception.exception import CustomException
from src.logging.logger import logging


class DataValidation:
    def __init__(self, config: DataValidationConfig):
        self.config = config

    def validate_all_columns(self) -> bool:
        """
        Validate that all expected columns exist in the CSV.
        Writes validation status and missing columns to STATUS_FILE.
        """
        try:
            # Load CSV
            data = pd.read_csv(self.config.local_data_file)

            # Trim column names
            data.columns = [col.strip() for col in data.columns]

            all_cols = list(data.columns)
            all_schema = list(self.config.all_schema.keys())

            # Find missing columns
            missing_cols = [col for col in all_schema if col not in all_cols]

            if missing_cols:
                validation_status = False
                logging.warning(f"Missing columns: {missing_cols}")
            else:
                validation_status = True
                logging.info("All columns validated successfully.")

            # Write status file
            with open(self.config.STATUS_FILE, "w") as f:
                f.write(f"Validation status: {validation_status}\n")
                if missing_cols:
                    f.write(f"Missing columns: {missing_cols}\n")

            return validation_status

        except Exception as e:
            raise CustomException(e, sys) from e
