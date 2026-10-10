"""Materialize and verify the hash-pinned airline data tau2 needs to run.

Writes only into the ignored ``data/`` tree. Nothing here calls a model, opens a
GPU, or reaches the network: it copies pinned bytes and re-hashes them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from airline_data.runtime_lock import (
    RuntimeDataError,
    materialize,
    tau2_data_dir,
    verify,
)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument(
        "--source",
        type=Path,
        default=root.parent / "tau2-bench",
        help="Local upstream tau2-bench checkout at the pinned commit",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Do not copy anything; only re-hash already materialized files",
    )
    args = parser.parse_args()
    try:
        if args.verify_only:
            verified = verify(args.root)
        else:
            verified = materialize(args.root, args.source)
    except (RuntimeDataError, OSError) as exc:
        print(f"Runtime data check failed: {exc}", file=sys.stderr)
        return 1
    report = {
        "runtime_files_verified": verified,
        "tau2_data_dir": str(tau2_data_dir(args.root)),
        "mode": "verify-only" if args.verify_only else "materialize",
    }
    if not args.verify_only:
        report["source"] = str(args.source)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
