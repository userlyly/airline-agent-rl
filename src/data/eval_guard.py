"""Held-out Test20 admission for evaluation.

``LeakageChecker`` deliberately has no ``eval`` stage: it exists to keep held-out
IDs out of *training* data, and Test20 content is meant never to reach a model
during training. Evaluation is the one place that content is supposed to be seen,
so it needs the opposite check -- the selection must be *exactly* the frozen
official Test20 split, no more and no less. This module is that independent guard.

A run that quietly evaluates a subset, re-evaluates the same task twice, or
reaches for a Dev6 ID must fail here rather than produce a number that looks
comparable to a frozen baseline but is not.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from airline_data.splits import SplitValidationError, load_splits, official_source

EVAL_SPLIT = "test20"


class EvalGuardError(SplitValidationError):
    """The evaluation selection is not exactly the frozen held-out split.

    Subclasses ``SplitValidationError`` so a protocol-level handler catches it;
    an invalid evaluation selection is a data-protocol failure, not a new one.
    """


class EvalGuard:
    def __init__(self, root: Path | str) -> None:
        self.splits = load_splits(root)

    def validate_task_ids(
        self, task_ids: Iterable[str], *, split: str = EVAL_SPLIT
    ) -> int:
        """Require the selection to equal the official Test20 set exactly."""
        if split != EVAL_SPLIT:
            raise EvalGuardError(f"Unknown evaluation split: {split!r}")
        if isinstance(task_ids, str | bytes | Mapping):
            raise EvalGuardError("Task IDs must be an iterable of string IDs")
        try:
            selected = list(task_ids)
        except TypeError as exc:
            raise EvalGuardError("Task IDs must be iterable") from exc
        for task_id in selected:
            if not isinstance(task_id, str) or task_id not in self.splits.all_ids:
                raise EvalGuardError(f"Invalid official Task ID: {task_id!r}")
        if len(set(selected)) != len(selected):
            raise EvalGuardError("Evaluation selection repeats a Task ID")
        expected = set(self.splits.test)
        chosen = set(selected)
        missing = sorted(expected - chosen, key=int)
        unexpected = sorted(chosen - expected, key=int)
        if missing or unexpected:
            raise EvalGuardError(
                "Evaluation must cover exactly the official Test20 split; "
                f"missing={missing} unexpected={unexpected}"
            )
        return len(selected)


def eval_source(split: str = EVAL_SPLIT) -> dict[str, str]:
    """Provenance block describing a held-out evaluation run."""
    return {
        **official_source(),
        "domain": "airline",
        "split": split,
        "role": "held-out evaluation",
    }
