"""Verify pinned upstream bytes and derive the official/project partitions."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UPSTREAM_REPOSITORY = "https://github.com/sierra-research/tau2-bench"
UPSTREAM_COMMIT = "4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699"
TASK_FILE = "data/tau2/domains/airline/tasks.json"
SPLIT_FILE = "data/tau2/domains/airline/split_tasks.json"
SNAPSHOT_HASHES = {
    SPLIT_FILE: "b22ced4d9a9850ac9aea31c53bdcb6d6009058140bd9acc7db37c1d36222ba8b",
    TASK_FILE: "ccd8ba737b4cc371415af70151187788f728d6108d0916e73bb4317b40542052",
    "LICENSE": "e67c5aa0074dfcaefd3c3a1aedb94cb539234aecd15d5a972574e3200e6252fe",
}
SPLIT_SEED = 42
SPLIT_ALGORITHM = "python-random.Random(42).shuffle-official-train-order-v1"


class SplitValidationError(ValueError):
    """The project data protocol cannot be verified."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SplitValidationError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(text: str) -> Any:
    """Reject ambiguous duplicate keys and non-JSON numeric constants."""

    def reject_constant(value: str) -> None:
        raise SplitValidationError(f"Invalid JSON constant: {value}")

    try:
        return json.loads(
            text, object_pairs_hook=_unique_object, parse_constant=reject_constant
        )
    except json.JSONDecodeError as exc:
        raise SplitValidationError(f"Invalid JSON: {exc.msg}") from exc


def read_json(path: Path) -> Any:
    try:
        return parse_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise SplitValidationError(f"Cannot read {path}: {exc}") from exc


def _ids(value: Any, label: str, count: int | None = None) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise SplitValidationError(f"{label} must be a nonempty list")
    if any(not isinstance(task_id, str) or not task_id for task_id in value):
        raise SplitValidationError(f"{label} must contain nonempty string IDs")
    if len(set(value)) != len(value):
        raise SplitValidationError(f"{label} contains duplicate IDs")
    if count is not None and len(value) != count:
        raise SplitValidationError(f"{label} requires {count} IDs; got {len(value)}")
    return tuple(value)


def official_source() -> dict[str, str]:
    return {
        "repository": UPSTREAM_REPOSITORY,
        "commit": UPSTREAM_COMMIT,
        "task_file": TASK_FILE,
        "task_file_sha256": SNAPSHOT_HASHES[TASK_FILE],
        "split_file": SPLIT_FILE,
        "split_file_sha256": SNAPSHOT_HASHES[SPLIT_FILE],
    }


def training_source() -> dict[str, str]:
    """Required provenance fields for each future training record."""
    return {
        **official_source(),
        "domain": "airline",
        "split": "train24",
        "project_split": "configs/splits/train_dev_split.json",
        "split_algorithm": SPLIT_ALGORITHM,
    }


@dataclass(frozen=True)
class SplitBundle:
    official_train: tuple[str, ...]
    train: tuple[str, ...]
    dev: tuple[str, ...]
    test: tuple[str, ...]

    @property
    def all_ids(self) -> frozenset[str]:
        return frozenset(self.official_train + self.test)


def _verify_snapshot(root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    expected_lock = {
        "schema_version": 1,
        "repository": UPSTREAM_REPOSITORY,
        "commit": UPSTREAM_COMMIT,
        "files": {
            path: {
                "sha256": digest,
                "url": (
                    "https://raw.githubusercontent.com/sierra-research/tau2-bench/"
                    f"{UPSTREAM_COMMIT}/{path}"
                ),
            }
            for path, digest in SNAPSHOT_HASHES.items()
        },
    }
    if read_json(root / "configs/tau2.lock.json") != expected_lock:
        raise SplitValidationError("Upstream lock differs from pinned trust anchors")
    for relative, expected in SNAPSHOT_HASHES.items():
        path = root / "vendor/tau2" / relative
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise SplitValidationError(f"Missing snapshot file: {path}") from exc
        if digest != expected:
            raise SplitValidationError(f"Snapshot SHA256 mismatch: {relative}")

    tasks = read_json(root / "vendor/tau2" / TASK_FILE)
    if not isinstance(tasks, list) or any(not isinstance(t, dict) for t in tasks):
        raise SplitValidationError("Official tasks must be a list of objects")
    task_ids = _ids([task.get("id") for task in tasks], "official tasks", 50)
    splits = read_json(root / "vendor/tau2" / SPLIT_FILE)
    if not isinstance(splits, dict):
        raise SplitValidationError("Official splits must be an object")
    train = _ids(splits.get("train"), "official train", 30)
    test = _ids(splits.get("test"), "official test", 20)
    base = _ids(splits.get("base"), "official base", 50)
    if set(train) & set(test):
        raise SplitValidationError("Official train and test overlap")
    if set(train + test) != set(task_ids) or set(base) != set(task_ids):
        raise SplitValidationError("Official splits do not cover the actual task IDs")
    return train, test


def build_split_payloads(root: Path | str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build deterministically from verified upstream, never guessed task IDs."""
    train, test = _verify_snapshot(Path(root))
    shuffled = list(train)
    random.Random(SPLIT_SEED).shuffle(shuffled)
    official = {
        "schema_version": 1,
        "domain": "airline",
        "source": official_source(),
        "train": list(train),
        "test": list(test),
    }
    project = {
        "schema_version": 1,
        "domain": "airline",
        "source": official_source(),
        "parent_split": "configs/splits/official_airline.json",
        "seed": SPLIT_SEED,
        "algorithm": SPLIT_ALGORITHM,
        "train": shuffled[:24],
        "dev": shuffled[24:],
    }
    return official, project


def load_splits(root: Path | str) -> SplitBundle:
    """Check saved manifests, cardinalities, provenance and exact seeded partition."""
    root = Path(root)
    official, project = build_split_payloads(root)
    saved_official = read_json(root / "configs/splits/official_airline.json")
    saved_project = read_json(root / "configs/splits/train_dev_split.json")
    if saved_official != official:
        raise SplitValidationError("Saved official split differs from pinned upstream")
    if saved_project != project:
        raise SplitValidationError(
            "Saved train/dev split differs from seeded partition"
        )
    train = _ids(saved_project["train"], "train24", 24)
    dev = _ids(saved_project["dev"], "dev6", 6)
    test = _ids(saved_official["test"], "test20", 20)
    if set(train) & set(dev) or set(train) & set(test) or set(dev) & set(test):
        raise SplitValidationError("Train, dev and test must be pairwise disjoint")
    if set(train + dev) != set(saved_official["train"]):
        raise SplitValidationError("Train24 and Dev6 must partition official Train30")
    return SplitBundle(tuple(saved_official["train"]), train, dev, test)
