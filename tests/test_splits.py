from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from airline_data.splits import (
    SNAPSHOT_HASHES,
    SPLIT_FILE,
    TASK_FILE,
    UPSTREAM_COMMIT,
    SplitValidationError,
    build_split_payloads,
    load_splits,
    parse_json,
    read_json,
)


def test_official_and_project_partition(root: Path) -> None:
    splits = load_splits(root)
    assert len(splits.official_train) == 30
    assert len(splits.train) == 24
    assert len(splits.dev) == 6
    assert len(splits.test) == 20
    assert len(splits.all_ids) == 50
    assert set(splits.train + splits.dev) == set(splits.official_train)
    assert not set(splits.train) & set(splits.dev)
    assert not set(splits.train) & set(splits.test)
    assert not set(splits.dev) & set(splits.test)
    tasks = read_json(root / "vendor/tau2" / TASK_FILE)
    assert splits.all_ids == {task["id"] for task in tasks}


def test_saved_split_is_reproducible(root: Path) -> None:
    first = build_split_payloads(root)
    assert build_split_payloads(root) == first
    assert first[0] == read_json(root / "configs/splits/official_airline.json")
    assert first[1] == read_json(root / "configs/splits/train_dev_split.json")
    assert first[1]["seed"] == 42


def test_environment_dependency_matches_pin(root: Path) -> None:
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    environment = config["project"]["optional-dependencies"]["environment"]
    assert len(environment) == 1
    assert environment[0].endswith("@" + UPSTREAM_COMMIT)
    assert config["project"]["dependencies"] == []


@pytest.mark.parametrize("relative", [TASK_FILE, SPLIT_FILE, "LICENSE"])
def test_modified_snapshot_refused(copied_root: Path, relative: str) -> None:
    file = copied_root / "vendor/tau2" / relative
    file.write_bytes(file.read_bytes() + b"\n")
    with pytest.raises(SplitValidationError, match="SHA256 mismatch"):
        load_splits(copied_root)


def test_forged_lock_and_data_refused(copied_root: Path) -> None:
    file = copied_root / "configs/tau2.lock.json"
    lock = read_json(file)
    lock["files"][TASK_FILE]["sha256"] = "0" * 64
    file.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(SplitValidationError, match="trust anchors"):
        load_splits(copied_root)
    assert len(SNAPSHOT_HASHES) == 3


@pytest.mark.parametrize("filename", ["official_airline.json", "train_dev_split.json"])
@pytest.mark.parametrize("mutation", ["id", "duplicate", "source", "missing"])
def test_corrupt_split_refused(copied_root: Path, filename: str, mutation: str) -> None:
    file = copied_root / "configs/splits" / filename
    payload = read_json(file)
    if mutation == "id":
        payload["train"][0] = payload.get("test", payload.get("dev"))[0]
    elif mutation == "duplicate":
        payload["train"][1] = payload["train"][0]
    elif mutation == "source":
        payload["source"]["commit"] = "0" * 40
    else:
        del payload["source"]
    file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SplitValidationError, match="differs"):
        load_splits(copied_root)


@pytest.mark.parametrize("field,value", [("seed", 43), ("algorithm", "other")])
def test_seed_or_algorithm_change_refused(
    copied_root: Path, field: str, value: object
) -> None:
    file = copied_root / "configs/splits/train_dev_split.json"
    payload = read_json(file)
    payload[field] = value
    file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SplitValidationError, match="seeded partition"):
        load_splits(copied_root)


def test_missing_snapshot_refused(copied_root: Path) -> None:
    (copied_root / "vendor/tau2" / TASK_FILE).unlink()
    with pytest.raises(SplitValidationError, match="Missing snapshot"):
        load_splits(copied_root)


@pytest.mark.parametrize("text", ['{"id":1,"id":2}', "NaN", "Infinity", "{"])
def test_ambiguous_json_refused(text: str) -> None:
    with pytest.raises(SplitValidationError):
        parse_json(text)


def test_cli_offline_success(root: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(root / "scripts/check_splits.py")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["snapshot_sha256_verified"]
    assert report["pairwise_disjoint"]
    assert (report["train"], report["dev"], report["test"]) == (24, 6, 20)


def test_cli_corrupt_split_fails(root: Path, copied_root: Path) -> None:
    file = copied_root / "configs/splits/train_dev_split.json"
    file.write_text("{}", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/check_splits.py"),
            "--root",
            str(copied_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Data protocol check failed" in result.stderr


def test_cli_regeneration_is_byte_stable(root: Path, copied_root: Path) -> None:
    files = list((copied_root / "configs/splits").glob("*.json"))
    original = {file.name: file.read_bytes() for file in files}
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/check_splits.py"),
            "--root",
            str(copied_root),
            "--write",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert {file.name: file.read_bytes() for file in files} == original
