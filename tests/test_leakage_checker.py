from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from airline_data.leakage_checker import LeakageChecker, LeakageError
from airline_data.splits import training_source

STAGES = ["teacher", "sft", "grpo"]


@pytest.mark.parametrize("stage", STAGES)
def test_all_train24_records_accepted(checker: LeakageChecker, stage: str) -> None:
    assert checker.validate_task_ids(checker.splits.train, stage=stage) == 24
    for task_id in checker.splits.train:
        checker.validate_record(
            {"task_id": task_id, "source": training_source()}, stage=stage
        )


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("partition", ["test", "dev"])
def test_every_heldout_id_refused(
    checker: LeakageChecker, stage: str, partition: str
) -> None:
    for task_id in getattr(checker.splits, partition):
        # Even a forged train24 source cannot make held-out IDs admissible.
        record = {"task_id": task_id, "source": training_source()}
        with pytest.raises(LeakageError, match=partition.capitalize() + " task"):
            checker.validate_record(record, stage=stage)
        with pytest.raises(LeakageError):
            checker.validate_task_ids([task_id], stage=stage)


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("task_id", [None, "", "50", "synthetic-task", 0, True, " 0"])
def test_invalid_or_missing_id_refused(
    checker: LeakageChecker, valid_record: dict, stage: str, task_id: object
) -> None:
    record = deepcopy(valid_record)
    record["task_id"] = task_id
    with pytest.raises(LeakageError, match="Invalid official Task ID"):
        checker.validate_record(record, stage=stage)
    del record["task_id"]
    with pytest.raises(LeakageError):
        checker.validate_record(record, stage=stage)


@pytest.mark.parametrize("field", list(training_source()))
@pytest.mark.parametrize("mutation", ["missing", "wrong"])
def test_each_provenance_field_required(
    checker: LeakageChecker, valid_record: dict, field: str, mutation: str
) -> None:
    record = deepcopy(valid_record)
    if mutation == "missing":
        del record["source"][field]
    else:
        record["source"][field] = "untrusted-source"
    with pytest.raises(LeakageError, match="source." + field):
        checker.validate_record(record, stage="sft")


@pytest.mark.parametrize("source", [None, "official", {}, [], 1])
def test_missing_or_invalid_source_refused(
    checker: LeakageChecker, valid_record: dict, source: object
) -> None:
    valid_record["source"] = source
    with pytest.raises(LeakageError):
        checker.validate_record(valid_record, stage="teacher")
    del valid_record["source"]
    with pytest.raises(LeakageError):
        checker.validate_record(valid_record, stage="teacher")


@pytest.mark.parametrize("stage", ["test", "eval", "", None, []])
def test_unknown_stage_refused(
    checker: LeakageChecker, valid_record: dict, stage: object
) -> None:
    with pytest.raises(LeakageError, match="Stage must"):
        checker.validate_record(valid_record, stage=stage)


@pytest.mark.parametrize("ids", [[], iter(()), "0", None, {"task_id": "0"}])
def test_invalid_or_empty_task_selection_refused(
    checker: LeakageChecker, ids: object
) -> None:
    with pytest.raises(LeakageError):
        checker.validate_task_ids(ids, stage="grpo")


@pytest.mark.parametrize("stage", STAGES)
def test_jsonl_all_records_checked(
    checker: LeakageChecker, tmp_path: Path, stage: str
) -> None:
    path = tmp_path / "training.jsonl"
    records = [
        {"task_id": task_id, "source": training_source()}
        for task_id in checker.splits.train
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    assert checker.validate_jsonl(path, stage=stage) == 24
    records[-1]["task_id"] = checker.splits.test[0]
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    with pytest.raises(LeakageError, match=r":24:.*Test task"):
        checker.validate_jsonl(path, stage=stage)


@pytest.mark.parametrize(
    "bad_line", ["\n", "{\n", "[]\n", "null\n", "{}\n", '{"task_id": NaN}\n']
)
def test_jsonl_malformed_line_refused(
    checker: LeakageChecker, valid_record: dict, tmp_path: Path, bad_line: str
) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(valid_record) + "\n" + bad_line, encoding="utf-8")
    with pytest.raises(LeakageError, match=r":2:"):
        checker.validate_jsonl(path, stage="sft")


def test_jsonl_duplicate_id_field_refused(
    checker: LeakageChecker, valid_record: dict, tmp_path: Path
) -> None:
    # A decoder that accepts duplicate keys could hide a Test20 ID.
    line = json.dumps(valid_record)
    line = '{"task_id": "' + checker.splits.test[0] + '",' + line[1:]
    path = tmp_path / "ambiguous.jsonl"
    path.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(LeakageError, match="Duplicate JSON key"):
        checker.validate_jsonl(path, stage="teacher")


def test_jsonl_missing_empty_and_non_utf8_refused(
    checker: LeakageChecker, tmp_path: Path
) -> None:
    path = tmp_path / "missing.jsonl"
    with pytest.raises(LeakageError, match="Cannot read"):
        checker.validate_jsonl(path, stage="teacher")
    path.write_text("", encoding="utf-8")
    with pytest.raises(LeakageError, match="Empty training JSONL"):
        checker.validate_jsonl(path, stage="teacher")
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(LeakageError, match="Cannot read"):
        checker.validate_jsonl(path, stage="teacher")


def test_cli_rejects_test_record(
    root: Path, checker: LeakageChecker, valid_record: dict, tmp_path: Path
) -> None:
    valid_record["task_id"] = checker.splits.test[0]
    path = tmp_path / "leak.jsonl"
    path.write_text(json.dumps(valid_record) + "\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/check_splits.py"),
            "--jsonl",
            str(path),
            "--stage",
            "teacher",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Test task" in result.stderr
