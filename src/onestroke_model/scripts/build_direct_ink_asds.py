"""Run the paired direct-ink versus parsed-union ASDS ablation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.direct_ink_asds import (
    _read_csv,
    analyze_direct_ink_rows,
    build_direct_ink_rows,
    write_direct_ink_analysis,
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
        "--parsed-rows",
        default=(
            "artifacts/paper_ijdar/spatial_score_development/"
            "development_features_and_predictions.csv"
        ),
    )
    parser.add_argument("--data-root", default="data")
    parser.add_argument(
        "--output-dir", default="artifacts/paper_ijdar/direct_ink_asds"
    )
    parser.add_argument("--bootstrap-iterations", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260814)
    args = parser.parse_args()

    frozen_path = Path(args.frozen_pairs)
    parsed_path = Path(args.parsed_rows)
    data_root = Path(args.data_root)
    rows = build_direct_ink_rows(
        frozen_pairs=_read_csv(frozen_path),
        parsed_rows=_read_csv(parsed_path),
        data_root=data_root,
    )
    report = analyze_direct_ink_rows(
        rows,
        bootstrap_iterations=args.bootstrap_iterations,
        bootstrap_seed=args.bootstrap_seed,
    )
    write_direct_ink_analysis(
        args.output_dir,
        rows=rows,
        report=report,
        frozen_pairs_path=frozen_path,
        parsed_rows_path=parsed_path,
        data_root=data_root,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
