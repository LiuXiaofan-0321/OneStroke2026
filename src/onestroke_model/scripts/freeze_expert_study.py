"""Freeze the approved 150 pairs and build offline human-rating packages."""

from __future__ import annotations

import argparse
import json

from onestroke_model.expert_study_freeze import build_frozen_expert_study


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze approved expert pairs and create blinded offline rating tools."
    )
    parser.add_argument(
        "--approved-selection",
        default=(
            "artifacts/paper_ijdar/expert_validation/"
            "candidate_review_v1/candidate_selection_150.csv"
        ),
    )
    parser.add_argument(
        "--data-root",
        default="data/legacy_gt_v1/output_img",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/expert_validation/frozen_study_v1",
    )
    parser.add_argument(
        "--evaluator-ids",
        nargs="+",
        default=["E01", "E02", "E03"],
    )
    parser.add_argument("--duplicate-fraction", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=20260812)
    parser.add_argument(
        "--approval-note",
        default="Project lead approved all 150 internally reviewed pairs.",
    )
    args = parser.parse_args()
    metadata = build_frozen_expert_study(
        approved_selection_path=args.approved_selection,
        dataset_root=args.data_root,
        output_dir=args.output_dir,
        evaluator_ids=args.evaluator_ids,
        duplicate_fraction=args.duplicate_fraction,
        seed=args.seed,
        approval_note=args.approval_note,
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
