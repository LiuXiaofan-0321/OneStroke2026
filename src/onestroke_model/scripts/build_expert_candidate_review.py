"""Build the internal-review candidate pool for expert structural validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.expert_candidate_pairs import build_expert_candidate_review


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit recovered legacy GT, score 400 natural same-character pairs, "
            "and select 150 candidate-only pairs for internal review."
        )
    )
    parser.add_argument(
        "--manifest",
        default="artifacts/data_recovery/manifest_resolved.csv",
    )
    parser.add_argument(
        "--data-root",
        default="data/legacy_gt_v1/output_img",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/expert_validation/candidate_review_v1",
    )
    parser.add_argument(
        "--legacy-git-dir",
        default="../tmp/data_recovery_forensics/OneStroke.git",
    )
    parser.add_argument("--seed", type=int, default=20260812)
    parser.add_argument("--pairs-per-character", type=int, default=10)
    parser.add_argument("--selected-pairs", type=int, default=150)
    parser.add_argument(
        "--image-mask-iou-threshold",
        type=float,
        default=0.80,
        help="Hard-exclude obvious source-image/GT mismatches below this IoU.",
    )
    args = parser.parse_args()
    metadata = build_expert_candidate_review(
        manifest_path=args.manifest,
        dataset_root=args.data_root,
        output_dir=args.output_dir,
        legacy_git_dir=args.legacy_git_dir,
        seed=args.seed,
        pairs_per_character=args.pairs_per_character,
        selected_pairs=args.selected_pairs,
        image_mask_iou_exclusion_threshold=args.image_mask_iou_threshold,
    )
    print(
        json.dumps(
            {
                "status": metadata["study_status"],
                "candidate_pair_count": metadata["candidate_pair_count"],
                "selected_pair_count": metadata[
                    "selected_internal_review_pair_count"
                ],
                "writer_identity_status": metadata["writer_identity"]["conclusion"],
                "frozen_file_created": metadata["frozen_file_created"],
                "output_dir": str(Path(args.output_dir).resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
