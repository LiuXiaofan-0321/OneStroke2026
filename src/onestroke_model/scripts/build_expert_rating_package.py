"""Build a blinded expert structural-similarity rating package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.expert_validation import (
    _read_csv,
    select_expert_rating_pairs,
    write_expert_study_package,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample blinded expert rating pairs.")
    parser.add_argument("--candidates", required=True)
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/expert_validation/study_package",
    )
    parser.add_argument("--target-pairs", type=int, default=180)
    parser.add_argument("--duplicate-fraction", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=20260811)
    args = parser.parse_args()
    internal, form, metadata = select_expert_rating_pairs(
        _read_csv(Path(args.candidates)),
        target_pairs=args.target_pairs,
        duplicate_fraction=args.duplicate_fraction,
        seed=args.seed,
    )
    metadata["candidate_source"] = str(Path(args.candidates).resolve())
    write_expert_study_package(
        args.output_dir,
        internal_rows=internal,
        form_rows=form,
        metadata=metadata,
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
