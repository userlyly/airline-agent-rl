"""Reduce a tau2 airline run to reproducible success metrics.

The airline reward basis is ``DB`` and ``COMMUNICATE``, both computed locally by
tau2 without any model call, so a summary is a pure function of the recorded
``results.json``.

Slicing a run down to the held-out Test20 set goes through ``EvalGuard``: the
slice must be exactly the frozen split, so a partial or extended run can never be
reported as a comparable baseline.
"""

from __future__ import annotations

import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from airline_data.eval_guard import EvalGuard, eval_source
from airline_data.splits import SplitValidationError, read_json

# tau2.metrics.agent_metrics treats reward within this tolerance of 1.0 as success.
SUCCESS_TOLERANCE = 1e-6


def _reward(simulation: dict[str, Any]) -> float | None:
    reward_info = simulation.get("reward_info")
    if not isinstance(reward_info, dict):
        return None
    reward = reward_info.get("reward")
    return float(reward) if isinstance(reward, int | float) else None


def _is_success(reward: float | None) -> bool:
    return reward is not None and abs(reward - 1.0) <= SUCCESS_TOLERANCE


def format_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _totals(simulations: list[dict[str, Any]]) -> dict[str, Any]:
    rewards = [_reward(s) for s in simulations]
    scored = [r for r in rewards if r is not None]
    successes = sum(1 for r in rewards if _is_success(r))
    return {
        "simulations": len(simulations),
        "evaluated": len(scored),
        "unevaluated": len(rewards) - len(scored),
        "successes": successes,
        # A zero denominator is reported as null, never as 0.0 or 1.0.
        "success_rate": (successes / len(scored)) if scored else None,
    }


def _component_means(simulations: list[dict[str, Any]]) -> dict[str, float | None]:
    totals: dict[str, float] = {}
    counts: Counter[str] = Counter()
    for simulation in simulations:
        breakdown = (simulation.get("reward_info") or {}).get("reward_breakdown")
        if not isinstance(breakdown, dict):
            continue
        for name, value in breakdown.items():
            if isinstance(value, int | float):
                totals[str(name)] = totals.get(str(name), 0.0) + float(value)
                counts[str(name)] += 1
    return {
        name: (totals[name] / counts[name] if counts[name] else None)
        for name in sorted(totals)
    }


def _per_task(simulations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[float | None]] = {}
    for simulation in simulations:
        grouped.setdefault(str(simulation.get("task_id")), []).append(
            _reward(simulation)
        )
    rows = []
    for task_id, rewards in grouped.items():
        scored = [r for r in rewards if r is not None]
        rows.append(
            {
                "task_id": task_id,
                "trials": len(rewards),
                "successes": sum(1 for r in rewards if _is_success(r)),
                "unevaluated": len(rewards) - len(scored),
                "reward_mean": (sum(scored) / len(scored)) if scored else None,
                # Sample std over the trials of this task: 0.0 means every trial
                # produced the same reward, i.e. the repeats added no information.
                "reward_std": statistics.stdev(scored) if len(scored) > 1 else None,
            }
        )
    return sorted(rows, key=lambda row: int(row["task_id"]))


def _trial_spread(simulations: list[dict[str, Any]]) -> dict[str, int]:
    """How many tasks actually varied across trials — the repeat-run sanity check."""
    grouped: dict[str, list[float | None]] = {}
    for simulation in simulations:
        grouped.setdefault(str(simulation.get("task_id")), []).append(
            _reward(simulation)
        )
    repeated = [rewards for rewards in grouped.values() if len(rewards) > 1]
    varying = sum(1 for rewards in repeated if len(set(rewards)) > 1)
    return {
        "tasks": len(grouped),
        "tasks_with_repeated_trials": len(repeated),
        "tasks_with_varying_rewards": varying,
        "tasks_with_identical_rewards": len(repeated) - varying,
    }


def _run_metadata(info: dict[str, Any]) -> dict[str, Any]:
    def pick(section: str) -> dict[str, Any]:
        block = info.get(section)
        if not isinstance(block, dict):
            return {}
        return {
            key: block.get(key)
            for key in ("implementation", "llm", "llm_args")
            if key in block
        }

    return {
        "git_commit": info.get("git_commit"),
        "seed": info.get("seed"),
        "num_trials": info.get("num_trials"),
        "max_steps": info.get("max_steps"),
        "max_errors": info.get("max_errors"),
        "agent": pick("agent_info"),
        "user": pick("user_info"),
    }


def build_summary(
    results_path: Path, *, split: str, root: Path | None
) -> dict[str, Any]:
    """Summarize ``results_path``; ``split="test20"`` also slices the held-out set.

    Every scope-dependent metric describes the same scope: with ``test20`` the
    per-task rows, reward components, termination reasons and cost cover the
    held-out subset, while ``all_tasks`` keeps the whole run for context.
    """
    payload = read_json(results_path)
    if not isinstance(payload, dict):
        raise SplitValidationError(f"{results_path}: results must be a JSON object")
    simulations = payload.get("simulations")
    if not isinstance(simulations, list) or not simulations:
        raise SplitValidationError(f"{results_path}: no simulations recorded")
    info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
    scope = simulations
    sliced: dict[str, Any] = {}
    if split != "all":
        if root is None:
            raise SplitValidationError(
                "A repository root is required for the test20 split"
            )
        guard = EvalGuard(root)
        held_out = set(guard.splits.test)
        scope = [s for s in simulations if str(s.get("task_id")) in held_out]
        # The slice itself must cover Test20 exactly, so a partial run cannot be
        # reported as a frozen held-out baseline.
        guard.validate_task_ids({str(s.get("task_id")) for s in scope})
        sliced = {
            "held_out": _totals(scope),
            "provenance": eval_source(),
        }
    return {
        "source_results": str(results_path),
        "run": _run_metadata(info),
        "selection": split,
        "all_tasks": _totals(simulations),
        **sliced,
        "per_task": _per_task(scope),
        "trial_spread": _trial_spread(scope),
        "termination_reasons": dict(
            sorted(Counter(s.get("termination_reason") for s in scope).items())
        ),
        "reward_components": _component_means(scope),
        "cost": {
            "agent": sum(float(s.get("agent_cost") or 0.0) for s in scope),
            "user": sum(float(s.get("user_cost") or 0.0) for s in scope),
        },
    }


def scope_of(summary: dict[str, Any]) -> dict[str, Any]:
    """The metrics a report should quote: held-out if present, else the whole run."""
    return summary.get("held_out") or summary["all_tasks"]


def render_markdown(summary: dict[str, Any]) -> str:
    scope = scope_of(summary)
    label = "Test20" if "held_out" in summary else "all tasks"
    lines = [
        f"# Airline run summary — {label}",
        "",
        f"- Source: `{summary['source_results']}`",
        f"- tau2 commit: `{summary['run'].get('git_commit')}`",
        f"- Selection: `{summary['selection']}`",
        "",
        "## Result",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Simulations | {scope['simulations']} |",
        f"| Evaluated | {scope['evaluated']} |",
        f"| Unevaluated | {scope['unevaluated']} |",
        f"| Successes | {scope['successes']} |",
        f"| Success rate | {format_rate(scope['success_rate'])} |",
        "",
        "## Reward components",
        "",
        "| Component | Mean |",
        "| --- | --- |",
    ]
    for name, value in summary["reward_components"].items():
        lines.append(f"| {name} | {format_rate(value)} |")
    lines += [
        "",
        "## Per task",
        "",
        "| Task | Trials | Successes | Reward mean | Reward std |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in summary["per_task"]:
        lines.append(
            f"| {row['task_id']} | {row['trials']} | {row['successes']} | "
            f"{format_rate(row['reward_mean'])} | {format_rate(row['reward_std'])} |"
        )
    spread = summary["trial_spread"]
    lines += [
        "",
        f"Trials varied on {spread['tasks_with_varying_rewards']} of "
        f"{spread['tasks_with_repeated_trials']} repeated tasks "
        f"({spread['tasks_with_identical_rewards']} produced an identical reward "
        "on every trial).",
    ]
    lines += ["", "## Termination reasons", "", "| Reason | Count |", "| --- | --- |"]
    for reason, count in summary["termination_reasons"].items():
        lines.append(f"| {reason} | {count} |")
    lines.append("")
    return "\n".join(lines)
