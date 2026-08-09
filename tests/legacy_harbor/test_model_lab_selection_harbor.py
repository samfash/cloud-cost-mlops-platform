import hashlib
import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
import yaml
from model_lab.selector import select_chosen_trial
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

APP = Path("/app")
LAB = APP / "model_lab"
TRIALS = LAB / "trials"
CONSTRAINTS = LAB / "constraints.yaml"
WEIGHTS = LAB / "config" / "score_weights.yaml"
EXCLUDES = LAB / "config" / "exclude_fingerprints.txt"
TRAIN = LAB / "data" / "train.csv"
EVAL = LAB / "data" / "eval.csv"
SUB = LAB / "submission"
FIXTURES = LAB / "fixtures"
MANIFEST = FIXTURES / "submission_manifest.txt"
EXAMPLE_PARAMS = FIXTURES / "example_params.yaml"
EXAMPLE_METRICS = FIXTURES / "example_metrics.json"
SELECTOR = LAB / "selector.py"
SELECTION_DIR = LAB / "selection"
ELECT_REXX = LAB / "legacy" / "elect.rexx"
ACCEPTANCE = LAB / "acceptance"
PIPELINE = SELECTION_DIR / "pipeline.py"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def fingerprint(params: dict) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_excludes(path: Path) -> set[str]:
    out: set[str] = set()
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line.lower())
    return out


def midrank_borda_points(values: list[float], *, higher_is_better: bool) -> list[float]:
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i], reverse=higher_is_better)
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n and values[order[j]] == values[order[i]]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = avg_rank
        i = j
    return [float(n) - r for r in ranks]


def channel_majority_winner(a_metrics: dict, b_metrics: dict) -> int:
    wins_a = 0
    wins_b = 0
    if a_metrics["RMSE"] < b_metrics["RMSE"]:
        wins_a += 1
    elif a_metrics["RMSE"] > b_metrics["RMSE"]:
        wins_b += 1
    if a_metrics["MAE"] < b_metrics["MAE"]:
        wins_a += 1
    elif a_metrics["MAE"] > b_metrics["MAE"]:
        wins_b += 1
    if a_metrics["R2"] > b_metrics["R2"]:
        wins_a += 1
    elif a_metrics["R2"] < b_metrics["R2"]:
        wins_b += 1
    if wins_a > wins_b:
        return 1
    if wins_b > wins_a:
        return -1
    return 0


def copeland_scores(metrics_list: list[dict]) -> list[float]:
    n = len(metrics_list)
    scores = [0.0] * n
    for i in range(n):
        for j in range(i + 1, n):
            verdict = channel_majority_winner(metrics_list[i], metrics_list[j])
            if verdict > 0:
                scores[i] += 1.0
            elif verdict < 0:
                scores[j] += 1.0
    return scores


def reference_select(trials_dir: Path, constraints_path: Path) -> dict:
    """Independent reference: eligibility, denylist, Borda midranks, Copeland."""
    with open(constraints_path, encoding="utf-8") as f:
        constraints = yaml.safe_load(f)
    lab_root = Path(trials_dir).parent
    excludes = load_excludes(lab_root / "config" / "exclude_fingerprints.txt")

    trials = []
    for path in sorted(Path(trials_dir).glob("*.json")):
        with open(path, encoding="utf-8") as f:
            trials.append(json.load(f))

    def eligible(trial: dict) -> bool:
        params = trial["params"]
        n_est = params["n_estimators"]
        depth_ok = not (
            constraints.get("require_unlimited_depth", True)
            and params.get("max_depth") is not None
        )
        return (
            constraints["n_estimators_min"] <= n_est <= constraints["n_estimators_max"]
            and params.get("max_features") == constraints["required_max_features"]
            and params.get("random_state") == constraints["required_random_state"]
            and depth_ok
            and float(trial["pred_var"]) <= float(constraints["pred_var_max"])
        )

    survivors = [
        t
        for t in trials
        if eligible(t) and fingerprint(t["params"]) not in excludes
    ]
    assert survivors

    rmses = [float(t["metrics"]["RMSE"]) for t in survivors]
    maes = [float(t["metrics"]["MAE"]) for t in survivors]
    r2s = [float(t["metrics"]["R2"]) for t in survivors]
    borda = [
        a + b + c
        for a, b, c in zip(
            midrank_borda_points(rmses, higher_is_better=False),
            midrank_borda_points(maes, higher_is_better=False),
            midrank_borda_points(r2s, higher_is_better=True),
            strict=True,
        )
    ]
    copeland = copeland_scores([t["metrics"] for t in survivors])

    best = None
    best_borda = float("-inf")
    best_copeland = float("-inf")
    best_pred_var = float("inf")
    best_fp = ""
    best_id = ""
    for i, trial in enumerate(survivors):
        pred_var = float(trial["pred_var"])
        fp = fingerprint(trial["params"])
        tid = trial["trial_id"]
        replace = False
        if best is None:
            replace = True
        elif borda[i] != best_borda:
            replace = borda[i] > best_borda
        elif copeland[i] != best_copeland:
            replace = copeland[i] > best_copeland
        elif pred_var != best_pred_var:
            replace = pred_var < best_pred_var
        elif fp != best_fp:
            replace = fp < best_fp
        else:
            replace = tid < best_id
        if replace:
            best = trial
            best_borda = borda[i]
            best_copeland = copeland[i]
            best_pred_var = pred_var
            best_fp = fp
            best_id = tid
    assert best is not None
    return best


def compute_metrics(model) -> dict:
    eval_df = pd.read_csv(EVAL)
    feature_cols = [c for c in eval_df.columns if c != "target"]
    pred = model.predict(eval_df[feature_cols])
    mse = mean_squared_error(eval_df["target"], pred)
    return {
        "MAE": float(mean_absolute_error(eval_df["target"], pred)),
        "MSE": float(mse),
        "RMSE": float(np.sqrt(mse)),
        "R2": float(r2_score(eval_df["target"], pred)),
        "pred": pred,
    }


def train_from_params(params: dict):
    train = pd.read_csv(TRAIN)
    feature_cols = [c for c in train.columns if c != "target"]
    model = RandomForestRegressor(n_jobs=1, **params)
    model.fit(train[feature_cols], train["target"])
    return model


def _stage_lab(tmp_path: Path) -> tuple[Path, Path]:
    lab = tmp_path / "model_lab"
    trials_dir = lab / "trials"
    trials_dir.mkdir(parents=True)
    config_dir = lab / "config"
    config_dir.mkdir()
    shutil.copy(WEIGHTS, config_dir / "score_weights.yaml")
    shutil.copy(EXCLUDES, config_dir / "exclude_fingerprints.txt")
    constraints_path = lab / "constraints.yaml"
    shutil.copy(CONSTRAINTS, constraints_path)
    return trials_dir, constraints_path


def _write_trials(trials_dir: Path, trials: list[dict]) -> None:
    for trial in trials:
        with open(trials_dir / f"{trial['trial_id']}.json", "w", encoding="utf-8") as f:
            json.dump(trial, f)


@pytest.fixture(scope="session")
def input_hashes():
    """Record hashes of immutable inputs before exercising the submission."""
    trial_hashes = {p.name: sha256(p) for p in sorted(TRIALS.glob("*.json"))}
    return {
        "trials": trial_hashes,
        "train": sha256(TRAIN),
        "eval": sha256(EVAL),
        "constraints": sha256(CONSTRAINTS),
        "weights": sha256(WEIGHTS),
        "excludes": sha256(EXCLUDES),
    }


@pytest.fixture(scope="session")
def expected_chosen():
    return reference_select(TRIALS, CONSTRAINTS)


@pytest.fixture(scope="session")
def example_params():
    with open(EXAMPLE_PARAMS, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def example_metrics():
    with open(EXAMPLE_METRICS, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def required_submission_names():
    return {
        line.strip()
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


@pytest.fixture(scope="session")
def submission(input_hashes, expected_chosen):
    assert SUB.is_dir()
    with open(SUB / "chosen.json", encoding="utf-8") as f:
        chosen = json.load(f)
    with open(SUB / "params.yaml", encoding="utf-8") as f:
        params = yaml.safe_load(f)
    with open(SUB / "metrics.json", encoding="utf-8") as f:
        metrics = json.load(f)
    model = joblib.load(SUB / "model.pkl")
    return {
        "chosen": chosen,
        "params": params,
        "metrics": metrics,
        "model": model,
        "expected": expected_chosen,
        "hashes": input_hashes,
    }


def test_selector_matches_reference_on_shipped_trials(expected_chosen):
    """Shipped registry selection must match the social-choice reference."""
    got = select_chosen_trial(TRIALS, CONSTRAINTS)
    assert got["trial_id"] == expected_chosen["trial_id"]
    assert got == expected_chosen


def test_election_uses_legacy_rexx():
    """Election must go through Regina and model_lab/legacy/elect.rexx."""
    assert ELECT_REXX.is_file()
    source = PIPELINE.read_text(encoding="utf-8")
    assert "regina" in source
    assert "elect.rexx" in source


def test_acceptance_examples(tmp_path):
    """Acceptance examples in the prompt must match select_chosen_trial."""
    for case_path in sorted(ACCEPTANCE.glob("*.json")):
        with open(case_path, encoding="utf-8") as f:
            case = json.load(f)
        trials_dir, constraints_path = _stage_lab(tmp_path / case_path.stem)
        excl = case.get("excludes") or []
        (trials_dir.parent / "config" / "exclude_fingerprints.txt").write_text(
            "\n".join(excl) + "\n",
            encoding="utf-8",
        )
        with open(constraints_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(case["constraints"], f)
        _write_trials(trials_dir, case["trials"])
        got = select_chosen_trial(trials_dir, constraints_path)
        assert got["trial_id"] == case["expected_trial_id"], case_path.name


def test_borda_not_linear_blend(tmp_path):
    """A linear min-max blend winner must lose under Borda midranks."""
    trials_dir, constraints_path = _stage_lab(tmp_path)
    (trials_dir.parent / "config" / "exclude_fingerprints.txt").write_text(
        "# none\n", encoding="utf-8"
    )
    # blend_bait: spectacular RMSE/R2 but catastrophic MAE (linear-blend magnet).
    # borda_champ: consistently strong across all three channels.
    blend_bait = {
        "trial_id": "syn_blend_bait",
        "params": {
            "n_estimators": 200,
            "max_depth": None,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
            "max_features": "sqrt",
            "random_state": 42,
        },
        "metrics": {"RMSE": 0.05, "MAE": 9.00, "R2": 0.995},
        "pred_var": 2.0,
    }
    borda_champ = {
        "trial_id": "syn_borda_champ",
        "params": {
            "n_estimators": 210,
            "max_depth": None,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
            "max_features": "sqrt",
            "random_state": 42,
        },
        "metrics": {"RMSE": 0.30, "MAE": 0.28, "R2": 0.92},
        "pred_var": 2.0,
    }
    filler = {
        "trial_id": "syn_filler",
        "params": {
            "n_estimators": 220,
            "max_depth": None,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
            "max_features": "sqrt",
            "random_state": 42,
        },
        "metrics": {"RMSE": 0.60, "MAE": 0.55, "R2": 0.70},
        "pred_var": 2.0,
    }
    mid = {
        "trial_id": "syn_mid",
        "params": {
            "n_estimators": 230,
            "max_depth": None,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
            "max_features": "sqrt",
            "random_state": 42,
        },
        "metrics": {"RMSE": 0.45, "MAE": 0.40, "R2": 0.80},
        "pred_var": 2.0,
    }
    _write_trials(trials_dir, [blend_bait, borda_champ, filler, mid])
    got = select_chosen_trial(trials_dir, constraints_path)
    assert got["trial_id"] == "syn_borda_champ"


def test_average_midranks_on_ties(tmp_path):
    """Tied channel values must use average midranks for Borda points."""
    trials_dir, constraints_path = _stage_lab(tmp_path)
    (trials_dir.parent / "config" / "exclude_fingerprints.txt").write_text(
        "# none\n", encoding="utf-8"
    )
    # A and B tie on RMSE; midranks must split the top ordinal places.
    trials = [
        {
            "trial_id": "syn_a",
            "params": {
                "n_estimators": 200,
                "max_depth": None,
                "min_samples_split": 2,
                "min_samples_leaf": 1,
                "max_features": "sqrt",
                "random_state": 42,
            },
            "metrics": {"RMSE": 1.0, "MAE": 0.5, "R2": 0.5},
            "pred_var": 3.0,
        },
        {
            "trial_id": "syn_b",
            "params": {
                "n_estimators": 210,
                "max_depth": None,
                "min_samples_split": 2,
                "min_samples_leaf": 1,
                "max_features": "sqrt",
                "random_state": 42,
            },
            "metrics": {"RMSE": 1.0, "MAE": 0.6, "R2": 0.6},
            "pred_var": 3.0,
        },
        {
            "trial_id": "syn_c",
            "params": {
                "n_estimators": 220,
                "max_depth": None,
                "min_samples_split": 2,
                "min_samples_leaf": 1,
                "max_features": "sqrt",
                "random_state": 42,
            },
            "metrics": {"RMSE": 2.0, "MAE": 0.7, "R2": 0.4},
            "pred_var": 3.0,
        },
    ]
    _write_trials(trials_dir, trials)
    expected = reference_select(trials_dir, constraints_path)
    got = select_chosen_trial(trials_dir, constraints_path)
    assert got["trial_id"] == expected["trial_id"]


def test_copeland_breaks_borda_ties(tmp_path):
    """Equal Borda totals must fall through to Copeland."""
    trials_dir, constraints_path = _stage_lab(tmp_path)
    (trials_dir.parent / "config" / "exclude_fingerprints.txt").write_text(
        "# none\n", encoding="utf-8"
    )
    _write_trials(
        trials_dir,
        [
            {
                "trial_id": "syn_c1",
                "params": {
                    "n_estimators": 200,
                    "max_depth": None,
                    "min_samples_split": 2,
                    "min_samples_leaf": 1,
                    "max_features": "sqrt",
                    "random_state": 42,
                },
                "metrics": {"RMSE": 0.1, "MAE": 2.0, "R2": 0.5},
                "pred_var": 3.0,
            },
            {
                "trial_id": "syn_c2",
                "params": {
                    "n_estimators": 210,
                    "max_depth": None,
                    "min_samples_split": 2,
                    "min_samples_leaf": 1,
                    "max_features": "sqrt",
                    "random_state": 42,
                },
                "metrics": {"RMSE": 2.0, "MAE": 0.1, "R2": 0.5},
                "pred_var": 3.0,
            },
            {
                "trial_id": "syn_c3",
                "params": {
                    "n_estimators": 220,
                    "max_depth": None,
                    "min_samples_split": 2,
                    "min_samples_leaf": 1,
                    "max_features": "sqrt",
                    "random_state": 42,
                },
                "metrics": {"RMSE": 1.0, "MAE": 1.0, "R2": 0.9},
                "pred_var": 3.0,
            },
        ],
    )
    expected = reference_select(trials_dir, constraints_path)
    got = select_chosen_trial(trials_dir, constraints_path)
    assert got["trial_id"] == expected["trial_id"]


def test_exclude_fingerprints_are_honored(tmp_path):
    """Denylisted fingerprints must lose even with superior metrics."""
    trials_dir, constraints_path = _stage_lab(tmp_path)
    strong = {
        "n_estimators": 300,
        "max_depth": None,
        "min_samples_split": 2,
        "min_samples_leaf": 1,
        "max_features": "sqrt",
        "random_state": 42,
    }
    weak = {
        "n_estimators": 200,
        "max_depth": None,
        "min_samples_split": 2,
        "min_samples_leaf": 1,
        "max_features": "sqrt",
        "random_state": 42,
    }
    (trials_dir.parent / "config" / "exclude_fingerprints.txt").write_text(
        fingerprint(strong) + "\n", encoding="utf-8"
    )
    _write_trials(
        trials_dir,
        [
            {
                "trial_id": "syn_strong_denied",
                "params": strong,
                "metrics": {"RMSE": 0.1, "MAE": 0.1, "R2": 0.99},
                "pred_var": 1.0,
            },
            {
                "trial_id": "syn_weak_allowed",
                "params": weak,
                "metrics": {"RMSE": 1.0, "MAE": 0.9, "R2": 0.7},
                "pred_var": 1.0,
            },
        ],
    )
    got = select_chosen_trial(trials_dir, constraints_path)
    assert got["trial_id"] == "syn_weak_allowed"


def test_pred_var_cap_excludes_strong_unstable(tmp_path):
    """Trials above pred_var_max must be excluded even with superior metrics."""
    trials_dir, constraints_path = _stage_lab(tmp_path)
    (trials_dir.parent / "config" / "exclude_fingerprints.txt").write_text(
        "# none\n", encoding="utf-8"
    )
    with open(CONSTRAINTS, encoding="utf-8") as f:
        constraints = yaml.safe_load(f)
    _write_trials(
        trials_dir,
        [
            {
                "trial_id": "syn_stable",
                "params": {
                    "n_estimators": 200,
                    "max_depth": None,
                    "min_samples_split": 2,
                    "min_samples_leaf": 1,
                    "max_features": "sqrt",
                    "random_state": 42,
                },
                "metrics": {"RMSE": 1.0, "MAE": 0.9, "R2": 0.7},
                "pred_var": float(constraints["pred_var_max"]) - 0.1,
            },
            {
                "trial_id": "syn_unstable_strong",
                "params": {
                    "n_estimators": 300,
                    "max_depth": None,
                    "min_samples_split": 2,
                    "min_samples_leaf": 1,
                    "max_features": "sqrt",
                    "random_state": 42,
                },
                "metrics": {"RMSE": 0.1, "MAE": 0.1, "R2": 0.99},
                "pred_var": float(constraints["pred_var_max"]) + 1.0,
            },
        ],
    )
    got = select_chosen_trial(trials_dir, constraints_path)
    assert got["trial_id"] == "syn_stable"


def test_inclusive_n_estimators_bound(tmp_path):
    """n_estimators_max must be inclusive so boundary trials remain eligible."""
    trials_dir, constraints_path = _stage_lab(tmp_path)
    (trials_dir.parent / "config" / "exclude_fingerprints.txt").write_text(
        "# none\n", encoding="utf-8"
    )
    with open(CONSTRAINTS, encoding="utf-8") as f:
        constraints = yaml.safe_load(f)
    boundary = {
        "trial_id": "syn_boundary",
        "params": {
            "n_estimators": constraints["n_estimators_max"],
            "max_depth": None,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
            "max_features": "sqrt",
            "random_state": 42,
        },
        "metrics": {"RMSE": 0.5, "MAE": 0.4, "R2": 0.9},
        "pred_var": 1.0,
    }
    _write_trials(trials_dir, [boundary])
    got = select_chosen_trial(trials_dir, constraints_path)
    assert got["trial_id"] == "syn_boundary"


def test_chosen_json_matches_selector(submission):
    """submission/chosen.json must equal select_chosen_trial output."""
    got = select_chosen_trial(TRIALS, CONSTRAINTS)
    assert submission["chosen"] == got


def test_submission_files_match_manifest(required_submission_names):
    """submission/ must contain exactly the manifest filenames."""
    names = {p.name for p in SUB.iterdir() if p.is_file()}
    assert names == required_submission_names


def test_params_match_fixture_layout_and_model(submission, example_params):
    """params.yaml must mirror the fixture layout and the fitted model."""
    params = submission["params"]
    model = submission["model"]
    chosen_params = submission["chosen"]["params"]
    assert set(params.keys()) == set(example_params.keys())
    assert params == chosen_params
    assert params["n_estimators"] == model.n_estimators
    assert params["max_depth"] == model.max_depth
    assert params["min_samples_split"] == model.min_samples_split
    assert params["min_samples_leaf"] == model.min_samples_leaf
    assert params["max_features"] == model.max_features
    assert params["random_state"] == model.random_state
    assert params["max_depth"] is None
    assert model.max_depth is None
    assert params["random_state"] == 42


def test_model_is_compressed_random_forest(submission):
    """model.pkl must be a compressed joblib RandomForestRegressor dump."""
    model = submission["model"]
    assert isinstance(model, RandomForestRegressor)
    with open(SUB / "model.pkl", "rb") as f:
        first = f.read(1)
    assert first != b"\x80", "model.pkl must be compressed joblib, not raw pickle"


def test_metrics_match_fixture_keys_and_model(submission, example_metrics):
    """metrics.json must mirror fixture keys and recompute from the model."""
    metrics = submission["metrics"]
    assert set(metrics.keys()) == set(example_metrics.keys())
    for key in example_metrics:
        assert isinstance(metrics[key], (int, float))
        assert np.isfinite(metrics[key])
    recomputed = compute_metrics(submission["model"])
    for key in example_metrics:
        assert metrics[key] == pytest.approx(recomputed[key], rel=0, abs=1e-12)
    assert np.isfinite(recomputed["pred"]).all()


def test_inputs_unchanged(submission):
    """Immutable lab inputs must remain unmodified."""
    hashes = submission["hashes"]
    assert sha256(TRAIN) == hashes["train"]
    assert sha256(EVAL) == hashes["eval"]
    assert sha256(CONSTRAINTS) == hashes["constraints"]
    assert sha256(WEIGHTS) == hashes["weights"]
    assert sha256(EXCLUDES) == hashes["excludes"]
    current = {p.name: sha256(p) for p in sorted(TRIALS.glob("*.json"))}
    assert current == hashes["trials"]


def test_retraining_is_reproducible(submission):
    """Retraining from params.yaml with n_jobs=1 must reproduce metrics."""
    params = submission["params"]
    model1 = train_from_params(params)
    model2 = train_from_params(params)
    m1 = compute_metrics(model1)
    m2 = compute_metrics(model2)
    with open(EXAMPLE_METRICS, encoding="utf-8") as f:
        keys = set(json.load(f).keys())
    for key in keys:
        assert m1[key] == pytest.approx(m2[key], rel=0, abs=1e-12)
        assert m1[key] == pytest.approx(submission["metrics"][key], rel=0, abs=1e-9)
    assert model1.n_estimators == params["n_estimators"]
    assert model1.max_depth is None


def test_selector_does_not_hardcode_winner(expected_chosen):
    """Selection sources must not hardcode the winning trial_id string."""
    sources = [SELECTOR.read_text(encoding="utf-8")]
    if SELECTION_DIR.is_dir():
        sources.extend(
            path.read_text(encoding="utf-8") for path in SELECTION_DIR.rglob("*.py")
        )
    if ELECT_REXX.is_file():
        sources.append(ELECT_REXX.read_text(encoding="utf-8"))
    blob = "\n".join(sources)
    assert expected_chosen["trial_id"] not in blob
