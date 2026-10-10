"""Offline Phase 0 verification and optional training JSONL admission check."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from airline_data.leakage_checker import LeakageChecker, LeakageError
from airline_data.splits import (
    UPSTREAM_COMMIT,
    SplitValidationError,
    build_split_payloads,
    load_splits,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--write", action="store_true", help="Regenerate only the two split manifests"
    )
    parser.add_argument("--jsonl", type=Path, help="Validate a training JSONL file")
    parser.add_argument("--stage", choices=["teacher", "sft", "grpo"])
    args = parser.parse_args()
    if (args.jsonl is None) != (args.stage is None):
        parser.error("--jsonl and --stage must be supplied together")
    try:
        if args.write:
            official, project = build_split_payloads(args.root)
            directory = args.root / "configs/splits"
            directory.mkdir(parents=True, exist_ok=True)
            for filename, payload in [
                ("official_airline.json", official),
                ("train_dev_split.json", project),
            ]:
                (directory / filename).write_text(
                    json.dumps(payload, indent=2) + "\n", encoding="utf-8"
                )
        splits = load_splits(args.root)
        report = {
            "commit": UPSTREAM_COMMIT,
            "official_train": len(splits.official_train),
            "train": len(splits.train),
            "dev": len(splits.dev),
            "test": len(splits.test),
            "pairwise_disjoint": True,
            "snapshot_sha256_verified": True,
        }
        if args.jsonl is not None:
            report["checked_records"] = LeakageChecker(args.root).validate_jsonl(
                args.jsonl, stage=args.stage
            )
        print(json.dumps(report, indent=2))
        return 0
    except (SplitValidationError, LeakageError, OSError) as exc:
        print(f"Data protocol check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
