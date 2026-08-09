"""Unit tests for Git blob digest helper."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cloud-cost"))

from src.pipeline.dependency_tracker import git_blob_sha256


def test_git_blob_sha256_stable(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello")
    d1 = git_blob_sha256(f)
    d2 = git_blob_sha256(f)
    assert d1 == d2
    assert d1 is not None
    assert len(d1) == 64


def test_git_blob_missing(tmp_path: Path):
    assert git_blob_sha256(tmp_path / "missing.bin") is None
