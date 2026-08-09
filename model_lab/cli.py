"""CLI for trial election and submission model training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from model_lab.selector import select_chosen_trial


def build_submission(lab_root: Path) -> Path:
    sub = lab_root / "submission"
    sub.mkdir(exist_ok=True)

    chosen = select_chosen_trial(lab_root / "trials", lab_root / "constraints.yaml")
    with open(sub / "chosen.json", "w", encoding="utf-8") as f:
        json.dump(chosen, f, indent=2)
        f.write("\n")

    params = dict(chosen["params"])
    with open(sub / "params.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(params, f, sort_keys=True)

    train = pd.read_csv(lab_root / "data" / "train.csv")
    eval_df = pd.read_csv(lab_root / "data" / "eval.csv")
    feature_cols = [c for c in train.columns if c != "target"]

    model = RandomForestRegressor(n_jobs=1, **params)
    model.fit(train[feature_cols], train["target"])
    pred = model.predict(eval_df[feature_cols])
    mse = mean_squared_error(eval_df["target"], pred)
    metrics = {
        "MAE": float(mean_absolute_error(eval_df["target"], pred)),
        "MSE": float(mse),
        "RMSE": float(np.sqrt(mse)),
        "R2": float(r2_score(eval_df["target"], pred)),
    }

    joblib.dump(model, sub / "model.pkl", compress=3)
    with open(sub / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
        f.write("\n")

    print(chosen["trial_id"])
    print(json.dumps(metrics, indent=2))
    return sub


def main() -> None:
    parser = argparse.ArgumentParser(description="Elect and train model_lab submission")
    parser.add_argument(
        "--lab-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Path to model_lab package root",
    )
    args = parser.parse_args()
    build_submission(args.lab_root)


if __name__ == "__main__":
    main()
