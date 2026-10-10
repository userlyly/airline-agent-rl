from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from airline_data.eval_guard import EvalGuard
from airline_data.splits import SplitValidationError
from airline_data.summary import build_summary, render_markdown


def simulation(
    task_id: str,
    reward: float | None,
    *,
    db: float | None = None,
    communicate: float | None = None,
) -> dict[str, Any]:
    reward_info: dict[str, Any] = {}
    if reward is not None:
        breakdown = {
            key: value
            for key, value in (("DB", db), ("COMMUNICATE", communicate))
            if value is not None
        }
        reward_info = {"reward": reward, "reward_breakdown": breakdown}
    return {
        "task_id": task_id,
        "reward_info": reward_info or None,
        "termination_reason": "user_stop",
        "agent_cost": 0.0,
        "user_cost": 0.0,
    }


def write_results(path: Path, simulations: list[dict[str, Any]]) -> Path:
    payload = {
        "info": {
            "git_commit": "5bfa7e37b36656b37dc6d022156be6563c1007f3",
            "seed": 300,
            "num_trials": 1,
            "max_steps": 200,
            "max_errors": 10,
            "agent_info": {"implementation": "llm_agent", "llm": "openai/qwen3-4b"},
            "user_info": {
                "implementation": "user_simulator",
                "llm": "openai/gpt-5.6-sol",
            },
        },
        "simulations": simulations,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_successes_and_rate(root: Path, tmp_path: Path) -> None:
    guard = EvalGuard(root)
    ids = guard.splits.test
    simulations = [
        simulation(task_id, 1.0 if index < 5 else 0.0)
        for index, task_id in enumerate(ids)
    ]
    summary = build_summary(
        write_results(tmp_path / "r.json", simulations), split="test20", root=root
    )
    assert summary["all_tasks"]["successes"] == 5
    assert summary["held_out"]["successes"] == 5
    assert summary["held_out"]["simulations"] == 20
    assert summary["held_out"]["success_rate"] == pytest.approx(0.25)


def test_slice_of_a_base_run(root: Path, tmp_path: Path) -> None:
    guard = EvalGuard(root)
    simulations = [simulation(task_id, 1.0) for task_id in guard.splits.test]
    simulations += [simulation(task_id, 0.0) for task_id in guard.splits.train[:5]]
    summary = build_summary(
        write_results(tmp_path / "r.json", simulations), split="test20", root=root
    )
    assert summary["all_tasks"]["simulations"] == 25
    assert summary["all_tasks"]["successes"] == 20
    assert summary["held_out"]["successes"] == 20
    assert summary["held_out"]["success_rate"] == 1.0


def test_sliced_summary_never_reports_train_tasks(root: Path, tmp_path: Path) -> None:
    """Every scope-dependent metric must describe the held-out set, not the run."""
    guard = EvalGuard(root)
    simulations = [simulation(task_id, 0.0) for task_id in guard.splits.test]
    simulations += [simulation(task_id, 1.0) for task_id in guard.splits.train[:5]]
    summary = build_summary(
        write_results(tmp_path / "r.json", simulations), split="test20", root=root
    )
    assert len(summary["per_task"]) == 20
    assert {row["task_id"] for row in summary["per_task"]} == set(guard.splits.test)
    assert summary["termination_reasons"] == {"user_stop": 20}
    # The train tasks all scored 1.0; none of them may leak into the held-out view.
    assert summary["held_out"]["successes"] == 0
    markdown = render_markdown(summary)
    assert f"| {guard.splits.train[0]} |" not in markdown
    assert f"| {guard.splits.test[0]} |" in markdown


def test_partial_held_out_run_refused(root: Path, tmp_path: Path) -> None:
    guard = EvalGuard(root)
    simulations = [simulation(task_id, 1.0) for task_id in guard.splits.test[:10]]
    with pytest.raises(SplitValidationError, match="exactly the official Test20"):
        build_summary(
            write_results(tmp_path / "r.json", simulations), split="test20", root=root
        )


def test_unevaluated_simulations_are_reported(root: Path, tmp_path: Path) -> None:
    guard = EvalGuard(root)
    simulations = [simulation(task_id, 1.0) for task_id in guard.splits.test]
    simulations[0] = simulation(guard.splits.test[0], None)
    summary = build_summary(
        write_results(tmp_path / "r.json", simulations), split="test20", root=root
    )
    held_out = summary["held_out"]
    assert held_out["unevaluated"] == 1
    assert held_out["evaluated"] == 19
    # The denominator is what was actually scored, not the selection size.
    assert held_out["success_rate"] == pytest.approx(19 / 19)


def test_zero_denominator_is_null_not_zero(root: Path, tmp_path: Path) -> None:
    guard = EvalGuard(root)
    simulations = [simulation(task_id, None) for task_id in guard.splits.test]
    summary = build_summary(
        write_results(tmp_path / "r.json", simulations), split="test20", root=root
    )
    assert summary["held_out"]["evaluated"] == 0
    assert summary["held_out"]["success_rate"] is None
    assert "| Success rate | n/a |" in render_markdown(summary)


def test_component_means_and_termination(root: Path, tmp_path: Path) -> None:
    guard = EvalGuard(root)
    simulations = [
        simulation(task_id, 1.0, db=1.0, communicate=1.0)
        for task_id in guard.splits.test[:10]
    ]
    simulations += [
        simulation(task_id, 0.0, db=0.0, communicate=1.0)
        for task_id in guard.splits.test[10:]
    ]
    summary = build_summary(
        write_results(tmp_path / "r.json", simulations), split="test20", root=root
    )
    assert summary["reward_components"]["DB"] == pytest.approx(0.5)
    assert summary["reward_components"]["COMMUNICATE"] == pytest.approx(1.0)
    assert summary["termination_reasons"] == {"user_stop": 20}
    assert summary["per_task"][0]["task_id"] == min(guard.splits.test, key=int)


def test_split_all_needs_no_guard(root: Path, tmp_path: Path) -> None:
    summary = build_summary(
        write_results(tmp_path / "r.json", [simulation("0", 1.0)]),
        split="all",
        root=None,
    )
    assert summary["all_tasks"]["successes"] == 1
    assert "held_out" not in summary


def test_repeated_trials_report_spread(root: Path, tmp_path: Path) -> None:
    """5 trials x 20 tasks: the summarizer must expose whether repeats varied."""
    guard = EvalGuard(root)
    ids = guard.splits.test
    simulations = []
    for task_id in ids:
        if task_id == ids[0]:
            # Every trial scores the same: the repeats carry no information.
            simulations += [simulation(task_id, 1.0) for _ in range(5)]
        else:
            # Three successes, two failures.
            simulations += [simulation(task_id, 1.0) for _ in range(3)]
            simulations += [simulation(task_id, 0.0) for _ in range(2)]
    summary = build_summary(
        write_results(tmp_path / "r.json", simulations), split="test20", root=root
    )
    # 1 task x 5 successes + 19 tasks x 3 successes = 5 + 57 = 62 out of 100.
    assert summary["held_out"]["simulations"] == 100
    assert summary["held_out"]["successes"] == 62
    assert summary["held_out"]["success_rate"] == pytest.approx(0.62)
    spread = summary["trial_spread"]
    assert spread["tasks_with_repeated_trials"] == 20
    assert spread["tasks_with_varying_rewards"] == 19
    assert spread["tasks_with_identical_rewards"] == 1
    rows = {row["task_id"]: row for row in summary["per_task"]}
    assert rows[ids[0]]["reward_std"] == pytest.approx(0.0)
    assert rows[ids[1]]["reward_mean"] == pytest.approx(0.6)
    assert rows[ids[1]]["reward_std"] > 0.0
    assert all(row["trials"] == 5 for row in summary["per_task"])
    markdown = render_markdown(summary)
    assert "Trials varied on 19 of 20 repeated tasks" in markdown


def test_single_trial_has_no_spread(root: Path, tmp_path: Path) -> None:
    guard = EvalGuard(root)
    simulations = [simulation(task_id, 1.0) for task_id in guard.splits.test]
    summary = build_summary(
        write_results(tmp_path / "r.json", simulations), split="test20", root=root
    )
    assert summary["trial_spread"]["tasks_with_repeated_trials"] == 0
    assert all(row["reward_std"] is None for row in summary["per_task"])


@pytest.mark.parametrize(
    "payload,message",
    [
        ("[]", "must be a JSON object"),
        ('{"simulations": []}', "no simulations recorded"),
        ('{"simulations": null}', "no simulations recorded"),
        ('{"simulations":[{"task_id":"2","task_id":"6"}]}', "Duplicate JSON key"),
    ],
)
def test_malformed_results_refused(
    root: Path, tmp_path: Path, payload: str, message: str
) -> None:
    path = tmp_path / "r.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(SplitValidationError, match=message):
        build_summary(path, split="all", root=root)


def test_cli_writes_json_and_markdown(root: Path, tmp_path: Path) -> None:
    guard = EvalGuard(root)
    simulations = [simulation(task_id, 1.0) for task_id in guard.splits.test]
    results = write_results(tmp_path / "r.json", simulations)
    out = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/eval/summarize_results.py"),
            "--results",
            str(results),
            "--split",
            "test20",
            "--root",
            str(root),
            "--out",
            str(out),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "20/20 (1.000)" in result.stdout
    written = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert written["held_out"]["successes"] == 20
    assert "| Successes | 20 |" in (out / "summary.md").read_text(encoding="utf-8")
