"""Build and freeze a deterministic character-disjoint split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.data.character_split import build_character_disjoint_split
from onestroke_model.reproducibility import (
    build_run_manifest,
    exact_command,
    utc_now_iso,
    write_run_manifest,
)


def main() -> None:
    started_at = utc_now_iso()
    parser = argparse.ArgumentParser(
        description="Build a deterministic train/val/test split with zero char_id overlap."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument(
        "--output",
        default="artifacts/paper_ijdar/character_disjoint/splits_character_disjoint.csv",
    )
    parser.add_argument(
        "--report",
        default=(
            "artifacts/paper_ijdar/character_disjoint/"
            "character_disjoint_split_report.json"
        ),
    )
    parser.add_argument("--seed", type=int, default=20260811)
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    args = parser.parse_args()
    report = build_character_disjoint_split(
        args.manifest,
        args.output,
        args.report,
        seed=args.seed,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
    )
    write_run_manifest(
        Path(args.report).parent,
        build_run_manifest(
            experiment_name="onestroke_character_disjoint_split_v1",
            status="COMPLETE",
            started_at=started_at,
            ended_at=utc_now_iso(),
            command=exact_command(),
            seed=args.seed,
            input_paths=[args.manifest, args.output],
            additional={
                "split_sha256": report["split_sha256"],
                "character_overlap": report["character_overlap"],
                "freeze_policy": report["freeze_policy"],
            },
        ),
    )
    print(
        json.dumps(
            {
                "split_sha256": report["split_sha256"],
                "actual_character_counts": report["actual_character_counts"],
                "actual_sample_counts": report["actual_sample_counts"],
                "character_overlap": report["character_overlap"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
