"""Build the frozen 840-to-769 dataset QC exclusion layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.data.dataset_qc import build_dataset_qc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="artifacts/data_recovery/source_manifest_identity_v1.csv",
    )
    parser.add_argument(
        "--dataset-root",
        default="data/legacy_gt_v1/output_img",
    )
    parser.add_argument(
        "--standard-splits",
        default="artifacts/data_audit/splits.csv",
    )
    parser.add_argument(
        "--character-disjoint-splits",
        default=(
            "artifacts/paper_ijdar/character_disjoint/"
            "splits_character_disjoint.csv"
        ),
    )
    parser.add_argument("--output-dir", default="artifacts/data_qc")
    parser.add_argument("--mismatch-iou-threshold", type=float, default=0.80)
    args = parser.parse_args()
    report = build_dataset_qc(
        Path(args.manifest),
        Path(args.dataset_root),
        Path(args.standard_splits),
        Path(args.character_disjoint_splits),
        Path(args.output_dir),
        mismatch_iou_threshold=args.mismatch_iou_threshold,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
