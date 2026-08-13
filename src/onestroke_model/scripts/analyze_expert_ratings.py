"""Analyze completed blinded expert structural-similarity ratings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.expert_validation import (
    _read_csv,
    analyze_expert_ratings,
    write_expert_analysis_outputs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze expert ratings with cluster bootstrap and ICC.")
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--ratings", required=True)
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/expert_validation/analysis",
    )
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260811)
    args = parser.parse_args()
    aggregate, report = analyze_expert_ratings(
        _read_csv(Path(args.pairs)),
        _read_csv(Path(args.ratings)),
        bootstrap_iterations=args.bootstrap_iterations,
        seed=args.seed,
    )
    write_expert_analysis_outputs(args.output_dir, aggregate, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
