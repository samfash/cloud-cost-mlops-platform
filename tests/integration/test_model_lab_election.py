"""Integration test for model_lab REXX election (requires regina)."""

import shutil
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

regina = shutil.which("regina")
pytestmark = pytest.mark.skipif(regina is None, reason="regina-rexx not installed")


def test_select_chosen_trial_on_shipped_registry():
    from model_lab.selector import select_chosen_trial

    lab = ROOT / "model_lab"
    chosen = select_chosen_trial(lab / "trials", lab / "constraints.yaml")
    assert chosen["trial_id"] == "trial_200"
    assert chosen["params"]["n_estimators"] == 800
