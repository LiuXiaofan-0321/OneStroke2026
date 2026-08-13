"""Preflight or execute the frozen character-disjoint benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.character_disjoint_benchmark import (
    run_character_disjoint_benchmark,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--split-report",
        default=(
            "artifacts/data_qc/"
            "character_disjoint_splits_qc_v1_report.json"
        ),
    )
    parser.add_argument(
        "--output-plan",
        default=(
            "artifacts/paper_ijdar/character_disjoint/"
            "character_disjoint_execution_plan.json"
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually train/calibrate/evaluate. Without this flag, the command "
            "is a dry-run and cannot start training."
        ),
    )
    args = parser.parse_args()
    result = run_character_disjoint_benchmark(
        args.project_root,
        split_report_path=args.split_report,
        execute=args.execute,
        output_plan=args.output_plan,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
