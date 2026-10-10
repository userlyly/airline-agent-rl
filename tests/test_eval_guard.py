from __future__ import annotations

from pathlib import Path

import pytest

from airline_data.eval_guard import EVAL_SPLIT, EvalGuard, EvalGuardError, eval_source
from airline_data.splits import UPSTREAM_COMMIT


@pytest.fixture
def guard(root: Path) -> EvalGuard:
    return EvalGuard(root)


def test_exact_test20_accepted(guard: EvalGuard) -> None:
    assert guard.validate_task_ids(guard.splits.test) == 20
    assert len(guard.splits.test) == 20


def test_order_does_not_matter(guard: EvalGuard) -> None:
    assert guard.validate_task_ids(reversed(guard.splits.test)) == 20
    assert guard.validate_task_ids(iter(guard.splits.test)) == 20


def test_subset_refused(guard: EvalGuard) -> None:
    with pytest.raises(EvalGuardError, match="missing="):
        guard.validate_task_ids(guard.splits.test[:-1])


def test_extra_train_id_refused(guard: EvalGuard) -> None:
    selection = [*guard.splits.test, guard.splits.train[0]]
    with pytest.raises(EvalGuardError, match="unexpected="):
        guard.validate_task_ids(selection)


def test_extra_dev_id_refused(guard: EvalGuard) -> None:
    selection = [*guard.splits.test, guard.splits.dev[0]]
    with pytest.raises(EvalGuardError, match="unexpected="):
        guard.validate_task_ids(selection)


def test_duplicate_id_refused(guard: EvalGuard) -> None:
    duplicate = [*guard.splits.test[:-1], guard.splits.test[0]]
    with pytest.raises(EvalGuardError, match="repeats a Task ID"):
        guard.validate_task_ids(duplicate)


def test_empty_selection_refused(guard: EvalGuard) -> None:
    with pytest.raises(EvalGuardError, match="missing="):
        guard.validate_task_ids([])


@pytest.mark.parametrize("selection", [None, "0", {"task_id": "0"}, 5])
def test_non_iterable_selection_refused(guard: EvalGuard, selection: object) -> None:
    with pytest.raises(EvalGuardError, match="iterable"):
        guard.validate_task_ids(selection)


@pytest.mark.parametrize("task_id", [None, 0, True, "50", "", " 2", "synthetic"])
def test_invalid_id_refused(guard: EvalGuard, task_id: object) -> None:
    selection = [*guard.splits.test[:-1], task_id]
    with pytest.raises(EvalGuardError, match="Invalid official Task ID"):
        guard.validate_task_ids(selection)


@pytest.mark.parametrize("split", ["train24", "dev6", "base", "test", ""])
def test_unknown_eval_split_refused(guard: EvalGuard, split: str) -> None:
    with pytest.raises(EvalGuardError, match="Unknown evaluation split"):
        guard.validate_task_ids(guard.splits.test, split=split)


def test_default_split_is_test20() -> None:
    assert EVAL_SPLIT == "test20"


def test_eval_source_records_provenance(guard: EvalGuard) -> None:
    source = eval_source()
    assert source["commit"] == UPSTREAM_COMMIT
    assert source["split"] == EVAL_SPLIT
    assert source["domain"] == "airline"
    # A held-out evaluation source must never look like a training source.
    assert source["role"] == "held-out evaluation"


def test_guard_is_distinct_from_leakage_checker(guard: EvalGuard) -> None:
    """Evaluation admits what training refuses; the two guards must not merge."""
    from airline_data.leakage_checker import LeakageChecker

    checker = LeakageChecker(Path(__file__).resolve().parents[1])
    with pytest.raises(ValueError, match="Test task"):
        checker.validate_task_ids(guard.splits.test, stage="teacher")
