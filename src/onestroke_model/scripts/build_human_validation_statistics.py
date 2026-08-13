"""Build paper-grade statistics from the frozen human-rating study."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from onestroke_model.human_validation_statistics import (
    build_human_validation_statistics,
    write_human_validation_statistics,
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build canonical-only human validation statistics and tables."
    )
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--ratings", required=True)
    parser.add_argument(
        "--raw-returns-dir",
        help="Optional directory containing the unmodified evaluator return CSV files.",
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "artifacts/paper_ijdar/expert_validation/"
            "human_ratings_v1/paper_statistics"
        ),
    )
    parser.add_argument("--bootstrap-iterations", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260812)
    args = parser.parse_args()

    raw_return_rows: list[dict[str, str]] = []
    if args.raw_returns_dir:
        raw_dir = Path(args.raw_returns_dir)
        for path in sorted(raw_dir.glob("*.csv")):
            raw_return_rows.extend(_read_csv(path))

    result = build_human_validation_statistics(
        _read_csv(Path(args.pairs)),
        _read_csv(Path(args.ratings)),
        raw_return_rows=raw_return_rows,
        bootstrap_iterations=args.bootstrap_iterations,
        seed=args.seed,
    )
    write_human_validation_statistics(args.output_dir, result)
    print(json.dumps(result["report"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
