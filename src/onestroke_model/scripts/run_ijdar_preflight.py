"""Run the repository, dataset, reference, and cache IJDAR preflight."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.ijdar_preflight import build_preflight_report, write_preflight_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit OneStroke IJDAR experiment prerequisites.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--manifest",
        default="artifacts/data_recovery/manifest_resolved.csv",
    )
    parser.add_argument("--splits", default="artifacts/data_audit/splits.csv")
    parser.add_argument(
        "--reference-manifest",
        default="references/calli_tongji_beta_manifest.csv",
    )
    parser.add_argument(
        "--cache-index",
        default="references/cache/segformer_b2_v1/index.json",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/preflight",
    )
    args = parser.parse_args()
    report = build_preflight_report(
        args.project_root,
        manifest=args.manifest,
        splits=args.splits,
        reference_manifest=args.reference_manifest,
        cache_index=args.cache_index,
    )
    paths = write_preflight_outputs(args.output_dir, report)
    print(
        json.dumps(
            {
                "task1_status": report["task1"]["status"],
                "workflow_status": {
                    name: value["status"] for name, value in report["workflows"].items()
                },
                "reference_cache_status": report["reference_cache"]["status"],
                "outputs": {name: str(path.resolve()) for name, path in paths.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
