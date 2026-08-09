"""Unit tests for model_lab selection helpers."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from model_lab.selection.pipeline import _fingerprint


def test_fingerprint_is_stable():
    params = {"n_estimators": 100, "max_depth": None, "random_state": 42}
    assert _fingerprint(params) == _fingerprint(params)
    assert len(_fingerprint(params)) == 64
