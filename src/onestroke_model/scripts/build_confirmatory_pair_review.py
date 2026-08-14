"""Build the score-independent confirmatory pair review package."""

from __future__ import annotations

import argparse
import json

from onestroke_model.confirmatory_pair_selection import (
    build_confirmatory_candidate_review,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-pool",
        default=(
            "artifacts/paper_ijdar/expert_validation/candidate_review_v1/"
            "natural_pair_candidates_400.csv"
        ),
    )
    parser.add_argument(
        "--development-pairs",
        default=(
            "artifacts/paper_ijdar/expert_validation/frozen_study_v1/"
            "frozen_expert_pairs_v1.csv"
        ),
    )
    parser.add_argument("--data-root", default="data")
    parser.add_argument(
        "--output-dir",
        default=(
            "artifacts/paper_ijdar/expert_validation/"
            "spatial_score_confirmatory_candidates_v1"
        ),
    )
    parser.add_argument("--target-pairs", type=int, default=100)
    args = parser.parse_args()
    result = build_confirmatory_candidate_review(
        candidate_pool_path=args.candidate_pool,
        development_pairs_path=args.development_pairs,
        data_root=args.data_root,
        output_dir=args.output_dir,
        target_pair_count=args.target_pairs,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
