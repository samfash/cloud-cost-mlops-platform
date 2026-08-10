#!/usr/bin/env python3
"""CI gate: fail if offline holdout metrics miss packaging floors / golden bounds."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "cloud-cost" / "artifacts" / "model_evaluation" / "metrics.json"
CONFIG = ROOT / "cloud-cost" / "config" / "config.yaml"


def _load_floors() -> tuple[float, float]:
    text = CONFIG.read_text(encoding="utf-8")
    r2_floor = 0.9
    mae_ceiling = 0.05
    for line in text.splitlines():
        if "r2_floor:" in line:
            r2_floor = float(line.split(":")[1].strip())
        if "mae_ceiling:" in line:
            mae_ceiling = float(line.split(":")[1].strip())
    return r2_floor, mae_ceiling


def main() -> int:
    if not METRICS.is_file():
        print(f"MISSING {METRICS}", file=sys.stderr)
        return 1
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    r2_floor, mae_ceiling = _load_floors()
    r2 = float(metrics["R2"])
    mae = float(metrics["MAE"])
    print(f"holdout R2={r2:.6f} MAE={mae:.6f} (floor R2>={r2_floor}, MAE<={mae_ceiling})")
    if r2 < r2_floor:
        print("FAIL: R2 below floor", file=sys.stderr)
        return 2
    if mae > mae_ceiling:
        print("FAIL: MAE above ceiling", file=sys.stderr)
        return 3
    if "gap_R2" in metrics:
        print(f"bias/variance gap_R2={float(metrics['gap_R2']):.6f}")
    if "baseline_mean_MAE" in metrics:
        print(
            "baseline_mean_MAE="
            f"{float(metrics['baseline_mean_MAE']):.6f} "
            f"lift_MAE={float(metrics.get('lift_MAE_vs_baseline', 0)):.6f}"
        )
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
