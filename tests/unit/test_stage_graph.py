"""Unit tests for pipeline stage graph wiring."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cloud-cost"))

from src.pipeline.stage_definitions import PIPELINE_STAGES


def test_stage_order():
    ids = [s.stage_id for s in PIPELINE_STAGES]
    assert ids == [
        "data_validation",
        "data_transformation",
        "model_trainer",
        "model_evaluation",
        "model_packaging",
    ]


def test_each_stage_has_dependencies():
    for stage in PIPELINE_STAGES:
        assert stage.dependencies
        assert stage.display_name
