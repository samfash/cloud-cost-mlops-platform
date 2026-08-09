"""Integration: second pipeline run skips when artifacts are valid."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CC = ROOT / "cloud-cost"


@pytest.mark.slow
def test_second_run_writes_identical_ledgers():
    head = CC / "artifacts" / "model_bundle" / "HEAD"
    if not head.is_file():
        pytest.skip("Train first: python main.py")

    meta = CC / "artifacts" / ".pipeline"
    before = {
        p.name: p.read_bytes()
        for p in meta.glob("*.json")
    }
    assert before, "expected pipeline ledgers after training"

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(CC)])
    subprocess.run(
        [sys.executable, "main.py"],
        cwd=CC,
        env=env,
        check=True,
    )
    after = {
        p.name: p.read_bytes()
        for p in meta.glob("*.json")
    }
    assert before == after
