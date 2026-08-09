"""Selection pipeline — election delegated to legacy/elect.rexx (Regina)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

ELECT_REXX = Path(__file__).resolve().parents[1] / "legacy" / "elect.rexx"


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_trials(trials_dir: Path) -> list[dict[str, Any]]:
    trials: list[dict[str, Any]] = []
    for path in sorted(Path(trials_dir).glob("*.json")):
        with open(path, encoding="utf-8") as f:
            trials.append(json.load(f))
    return trials


def _fingerprint(params: dict[str, Any]) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _encode_payload(
    trials: list[dict[str, Any]],
    constraints: dict[str, Any],
    excludes: list[str],
) -> str:
    lines: list[str] = [
        f"N_ESTIMATORS_MIN {constraints['n_estimators_min']}",
        f"N_ESTIMATORS_MAX {constraints['n_estimators_max']}",
        f"REQUIRED_MAX_FEATURES {constraints['required_max_features']}",
        f"REQUIRED_RANDOM_STATE {constraints['required_random_state']}",
        (
            f"REQUIRE_UNLIMITED_DEPTH "
            f"{1 if constraints.get('require_unlimited_depth', True) else 0}"
        ),
        f"PRED_VAR_MAX {constraints['pred_var_max']}",
    ]
    lines.extend(f"EXCLUDE {fp}" for fp in excludes)
    for trial in trials:
        params = trial["params"]
        depth = params.get("max_depth")
        depth_tok = "_" if depth is None else str(depth)
        lines.extend(
            [
                "TRIAL",
                f"ID {trial['trial_id']}",
                f"N_ESTIMATORS {params['n_estimators']}",
                f"MAX_DEPTH {depth_tok}",
                f"MAX_FEATURES {params['max_features']}",
                f"RANDOM_STATE {params['random_state']}",
                f"RMSE {trial['metrics']['RMSE']}",
                f"MAE {trial['metrics']['MAE']}",
                f"R2 {trial['metrics']['R2']}",
                f"PRED_VAR {trial['pred_var']}",
                f"FINGERPRINT {_fingerprint(params)}",
            ]
        )
    lines.append("END")
    return "\n".join(lines) + "\n"


def select_chosen_trial(
    trials_dir: str | Path,
    constraints_path: str | Path,
) -> dict[str, Any]:
    trials_dir = Path(trials_dir)
    constraints_path = Path(constraints_path)
    lab_root = trials_dir.parent
    constraints = _load_yaml(constraints_path)
    trials = _load_trials(trials_dir)

    excludes: list[str] = []
    excl_path = lab_root / "config" / "exclude_fingerprints.txt"
    if excl_path.is_file():
        excludes.extend(
            line.strip().lower()
            for line in excl_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    payload = _encode_payload(trials, constraints, excludes)
    proc = subprocess.run(
        ["regina", str(ELECT_REXX)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "elect.rexx failed")
    winner_id = proc.stdout.strip().splitlines()[-1].strip()
    for trial in trials:
        if trial["trial_id"] == winner_id:
            return trial
    raise RuntimeError(f"unknown winner id from elect.rexx: {winner_id!r}")
