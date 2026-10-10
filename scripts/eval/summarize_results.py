"""Summarize a tau2 airline run into reproducible success metrics.

Reads a ``results.json`` produced by ``tau2 run`` and writes ``summary.json`` and
``summary.md``. Nothing here calls a model: the airline reward basis is ``DB`` and
``COMMUNICATE``, both computed locally by tau2, so a summary is a pure function of
the recorded file.

Use ``--split test20`` (the default) to slice a run that covered more tasks -- for
example an official ``base`` 50-task run -- down to the frozen held-out set. The
slice is checked against the pinned Test20 IDs and refused if it is not an exact
match, so a partial run cannot be reported as a comparable baseline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from airline_data.splits import SplitValidationError
from airline_data.summary import build_summary, format_rate, render_markdown, scope_of


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--split", choices=["test20", "all"], default="test20")
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument(
        "--out",
        type=Path,
        help="Output directory; defaults to outputs/<run name>/ next to the results",
    )
    args = parser.parse_args()
    try:
        summary = build_summary(args.results, split=args.split, root=args.root)
    except (SplitValidationError, OSError) as exc:
        print(f"Summary failed: {exc}", file=sys.stderr)
        return 1
    out = args.out or args.root / "outputs" / args.results.parent.name
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    (out / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    scope = scope_of(summary)
    print(
        f"{scope['successes']}/{scope['evaluated']} "
        f"({format_rate(scope['success_rate'])}) -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
