"""Build the development analysis for the frozen spatial structure score."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.spatial_score_development import (
    analyze_development_rows,
    build_development_features,
    write_spatial_score_development,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frozen-pairs",
        default=(
            "artifacts/paper_ijdar/expert_validation/"
            "frozen_study_v1/frozen_expert_pairs_v1.csv"
        ),
    )
    parser.add_argument(
        "--canonical-ratings",
        default=(
            "artifacts/paper_ijdar/expert_validation/human_ratings_v1/"
            "paper_statistics/canonical_pair_ratings.csv"
        ),
    )
    parser.add_argument("--data-root", default="data")
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/spatial_score_development",
    )
    parser.add_argument("--bootstrap-iterations", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260814)
    args = parser.parse_args()

    frozen_path = Path(args.frozen_pairs)
    ratings_path = Path(args.canonical_ratings)

    import csv

    with frozen_path.open(encoding="utf-8-sig", newline="") as handle:
        frozen_rows = list(csv.DictReader(handle))
    with ratings_path.open(encoding="utf-8-sig", newline="") as handle:
        rating_rows = list(csv.DictReader(handle))

    features = build_development_features(
        frozen_pairs=frozen_rows,
        canonical_ratings=rating_rows,
        data_root=Path(args.data_root),
    )
    result = analyze_development_rows(
        features,
        bootstrap_iterations=args.bootstrap_iterations,
        bootstrap_seed=args.bootstrap_seed,
    )
    report = write_spatial_score_development(
        args.output_dir,
        result,
        frozen_pairs_path=frozen_path,
        ratings_path=ratings_path,
        data_root=Path(args.data_root),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
