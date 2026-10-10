"""Fail-closed admission checks for future teacher/SFT/GRPO data."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from airline_data.splits import (
    SplitValidationError,
    load_splits,
    parse_json,
    training_source,
)

TRAINING_STAGES = frozenset({"teacher", "sft", "grpo"})


class LeakageError(ValueError):
    """Training data was refused; callers must not continue collection or training."""


class LeakageChecker:
    def __init__(self, root: Path | str):
        # Validate the repository manifests before accepting any IDs or records.
        self.splits = load_splits(root)

    @staticmethod
    def _check_stage(stage: str) -> None:
        if not isinstance(stage, str) or stage not in TRAINING_STAGES:
            raise LeakageError("Stage must be teacher, sft or grpo")

    def _check_id(self, task_id: Any) -> None:
        if not isinstance(task_id, str) or task_id not in self.splits.all_ids:
            raise LeakageError(f"Invalid official Task ID: {task_id!r}")
        if task_id in self.splits.test:
            raise LeakageError(f"Test task {task_id} is forbidden in training data")
        if task_id in self.splits.dev:
            raise LeakageError(f"Dev task {task_id} is forbidden in training data")
        if task_id not in self.splits.train:
            raise LeakageError(f"Task {task_id} is outside Train24")

    def validate_task_ids(self, task_ids: Iterable[str], *, stage: str) -> int:
        """Admission guard before any future model/API call. Return checked count."""
        self._check_stage(stage)
        if isinstance(task_ids, str | bytes | Mapping):
            raise LeakageError("Task IDs must be an iterable of string IDs")
        try:
            iterator = iter(task_ids)
        except TypeError as exc:
            raise LeakageError("Task IDs must be iterable") from exc
        count = 0
        for task_id in iterator:
            self._check_id(task_id)
            count += 1
        if not count:
            raise LeakageError("Empty task selection is refused")
        return count

    def validate_record(self, record: Any, *, stage: str) -> None:
        self._check_stage(stage)
        if not isinstance(record, dict):
            raise LeakageError("Training record must be a JSON object")
        self._check_id(record.get("task_id"))
        source = record.get("source")
        if not isinstance(source, dict):
            raise LeakageError("Missing or invalid source object")
        for field, expected in training_source().items():
            if source.get(field) != expected:
                raise LeakageError(f"Missing or mismatched source.{field}")

    def validate_jsonl(self, path: Path | str, *, stage: str) -> int:
        """Stream every record; reject the first bad line with file/line context."""
        self._check_stage(stage)
        path = Path(path)
        count = 0
        try:
            with path.open(encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, start=1):
                    try:
                        record = parse_json(line)
                        self.validate_record(record, stage=stage)
                    except (LeakageError, SplitValidationError) as exc:
                        raise LeakageError(f"{path}:{line_number}: {exc}") from exc
                    count += 1
        except (OSError, UnicodeError) as exc:
            raise LeakageError(f"Cannot read training JSONL {path}: {exc}") from exc
        if not count:
            raise LeakageError(f"{path}: Empty training JSONL is refused")
        return count
