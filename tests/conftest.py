from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from airline_data.leakage_checker import LeakageChecker
from airline_data.splits import training_source


@pytest.fixture
def root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def copied_root(root: Path, tmp_path: Path) -> Path:
    for directory in ("configs", "vendor"):
        shutil.copytree(root / directory, tmp_path / directory)
    return tmp_path


@pytest.fixture
def checker(root: Path) -> LeakageChecker:
    return LeakageChecker(root)


@pytest.fixture
def valid_record(checker: LeakageChecker) -> dict:
    return {"task_id": checker.splits.train[0], "source": training_source()}
