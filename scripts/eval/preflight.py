"""Pre-flight checks for a held-out Test20 evaluation run.

Verifies that the hash-pinned airline data is materialized and that the split tau2
is about to read is exactly the official Test20 set. Reads only local files --
no model, no GPU, no network. Exits non-zero on the first problem.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from airline_data.eval_guard import EvalGuard, eval_source
from airline_data.runtime_lock import RuntimeDataError, tau2_data_dir, verify
from airline_data.splits import SPLIT_FILE, UPSTREAM_COMMIT, read_json


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=root)
    args = parser.parse_args()
    data_dir = tau2_data_dir(args.root)
    try:
        verified = verify(args.root)
        splits = read_json(data_dir / SPLIT_FILE.removeprefix("data/"))
        if not isinstance(splits, dict):
            raise RuntimeDataError("Materialized split file is not an object")
        guard = EvalGuard(args.root)
        selected = guard.validate_task_ids(splits.get("test"))
    except RuntimeDataError as exc:
        print(f"Pre-flight failed: {exc}", file=sys.stderr)
        print(
            "Run scripts/eval/prepare_data.py first, or point --root at the repo root.",
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "runtime_files_verified": verified,
                "tau2_data_dir": str(data_dir),
                "selection": "test20",
                "task_ids": sorted(guard.splits.test, key=int),
                "count": selected,
                "source": eval_source(),
                "pinned_commit": UPSTREAM_COMMIT,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
