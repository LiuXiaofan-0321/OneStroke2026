"""Create empty, explicitly pending expert-study artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.expert_validation import write_pending_expert_study_package


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare pending expert-study templates.")
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/expert_validation/study_package",
    )
    parser.add_argument("--target-pairs", type=int, default=180)
    parser.add_argument("--target-evaluators", type=int, default=3)
    parser.add_argument("--duplicate-fraction", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=20260811)
    args = parser.parse_args()
    metadata = write_pending_expert_study_package(
        args.output_dir,
        target_pairs=args.target_pairs,
        target_evaluators=args.target_evaluators,
        duplicate_fraction=args.duplicate_fraction,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                **metadata,
                "output_dir": str(Path(args.output_dir).resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
