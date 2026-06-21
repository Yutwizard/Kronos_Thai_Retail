"""Shared fixtures for the Kronos-TH test suite."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture
def tmp_cache(tmp_path):
    d = tmp_path / "raw"
    d.mkdir()
    return d
