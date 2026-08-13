"""Restore and fully verify the recovered 840-sample legacy GT dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.data.legacy_gt_recovery import (
    LEGACY_ARCHIVE_SHA256,
    restore_legacy_ground_truth,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path("data/legacy_gt_v1/output_img"),
    )
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=Path("artifacts/data_recovery/source_manifest_identity_v1.csv"),
        help=(
            "Portable 894-row sample-identity manifest used to verify the archive."
        ),
    )
    parser.add_argument(
        "--resolved-manifest",
        type=Path,
        default=Path("artifacts/data_recovery/manifest_resolved.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("artifacts/data_recovery/verification_report.json"),
    )
    parser.add_argument(
        "--expected-sha256",
        default=LEGACY_ARCHIVE_SHA256,
        help="Pinned archive hash. Changing this requires a new provenance review.",
    )
    args = parser.parse_args()

    def progress(done: int, total: int, sample_id: str) -> None:
        print(f"verify={done}/{total} sample_id={sample_id}", flush=True)

    report = restore_legacy_ground_truth(
        args.archive,
        args.destination,
        args.source_manifest,
        args.resolved_manifest,
        args.report,
        expected_archive_sha256=args.expected_sha256,
        progress=progress,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
