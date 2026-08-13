"""Execution planning for frozen character-disjoint experiments."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from onestroke_model.config import load_yaml
from onestroke_model.reproducibility import canonical_csv_sha256, sha256_file
from onestroke_model.utils.io import read_csv_rows

DEFAULT_CONFIGS = (
    "configs/paper_ijdar/character_disjoint_unet_seed_20260811.yaml",
    "configs/paper_ijdar/character_disjoint_unet_seed_314159.yaml",
    "configs/paper_ijdar/character_disjoint_unet_seed_271828.yaml",
    "configs/paper_ijdar/character_disjoint_deeplabv3plus_seed_20260811.yaml",
    "configs/paper_ijdar/character_disjoint_deeplabv3plus_seed_314159.yaml",
    "configs/paper_ijdar/character_disjoint_deeplabv3plus_seed_271828.yaml",
    "configs/paper_ijdar/character_disjoint_segformer_b2_seed_20260811.yaml",
    "configs/paper_ijdar/character_disjoint_segformer_b2_seed_314159.yaml",
    "configs/paper_ijdar/character_disjoint_segformer_b2_seed_271828.yaml",
)
FROZEN_SPLIT_SHA256 = "eec9bf5c0910a2e9f6046991f1458519cd903d31deea3e0a4d33c555ff53a09e"
QC_CLEAN_SPLIT_SHA256 = "e9303314d1b70d3f92efcdc5c0807f833148cbe64c2702379f0ac951ed2a1e2b"
QC_EXCLUSIONS_SHA256 = "bd2b0641d0e6f53f6f18f6604232c02ff99e9d989eb39125f6a9af41e8573a1a"
EXPECTED_SPLIT_SAMPLE_COUNTS = {"train": 539, "val": 114, "test": 116}
EXPECTED_SPLIT_CHARACTER_COUNTS = {"train": 28, "val": 6, "test": 6}
EXPECTED_COMPLETE_SAMPLES = 769


def _resolve_project_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute() and path.exists():
        return path.resolve()
    if path.is_absolute():
        # Frozen reports may contain the path of the machine on which they were
        # generated. Prefer the current repository's canonical artifact name.
        candidate = root / "artifacts/paper_ijdar/character_disjoint" / path.name
        if candidate.exists():
            return candidate.resolve()
        return path
    return (root / path).resolve()


def _validate_frozen_split(
    split_path: Path,
    split_report: dict[str, Any],
    *,
    expected_split_sha256: str = QC_CLEAN_SPLIT_SHA256,
    expected_sample_counts: dict[str, int] = EXPECTED_SPLIT_SAMPLE_COUNTS,
    expected_character_counts: dict[str, int] = EXPECTED_SPLIT_CHARACTER_COUNTS,
) -> dict[str, Any]:
    actual_hash = canonical_csv_sha256(split_path)
    if actual_hash != expected_split_sha256:
        raise ValueError(
            "frozen character-disjoint split hash mismatch: "
            f"expected={expected_split_sha256} actual={actual_hash}"
        )
    if split_report.get("split_sha256") != expected_split_sha256:
        raise ValueError("split report does not declare the frozen SHA-256")
    if expected_split_sha256 == QC_CLEAN_SPLIT_SHA256:
        if split_report.get("source_character_assignment_sha256") != FROZEN_SPLIT_SHA256:
            raise ValueError("QC split report lost the original frozen character assignment")
        if split_report.get("qc_exclusions_sha256") != QC_EXCLUSIONS_SHA256:
            raise ValueError("QC split report declares a different exclusion list")
    if not all(split_report["assertions"].values()):
        raise ValueError("character-disjoint split assertions are not all true")
    if split_report["actual_sample_counts"] != expected_sample_counts:
        raise ValueError("frozen split sample counts changed")
    if split_report["actual_character_counts"] != expected_character_counts:
        raise ValueError("frozen split character counts changed")

    with split_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_total = sum(expected_sample_counts.values())
    if len(rows) != expected_total:
        raise ValueError(
            f"frozen split must contain {expected_total} rows, got {len(rows)}"
        )
    sample_ids = [row["sample_id"] for row in rows]
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("frozen split contains duplicate sample IDs")
    split_characters = {
        name: {row["char_id"] for row in rows if row["split"] == name}
        for name in EXPECTED_SPLIT_SAMPLE_COUNTS
    }
    if any(
        split_characters[left] & split_characters[right]
        for left, right in (("train", "val"), ("train", "test"), ("val", "test"))
    ):
        raise ValueError("frozen split is no longer character-disjoint")
    return {
        "split_sha256": actual_hash,
        "sample_ids": set(sample_ids),
        "sample_counts": {
            name: sum(row["split"] == name for row in rows)
            for name in expected_sample_counts
        },
        "character_counts": {
            name: len(split_characters[name])
            for name in expected_character_counts
        },
    }


def _local_data_ready(
    manifest_path: Path,
    *,
    expected_sample_ids: set[str],
) -> tuple[bool, int, int, list[str]]:
    if not manifest_path.is_file():
        return False, 0, len(expected_sample_ids), ["resolved manifest is missing"]
    rows = [
        row
        for row in read_csv_rows(manifest_path)
        if str(row.get("has_all_masks", "")).lower() in {"true", "1", "yes"}
        and not row.get("errors", "")
    ]
    fields = (
        "image_path",
        "vec1_path",
        "vec2_path",
        "vec3_path",
        "vec4_path",
        "vec5_path",
        "keypoint_path",
    )
    problems: list[str] = []
    manifest_ids = {row["sample_id"] for row in rows}
    if manifest_ids != expected_sample_ids:
        missing = sorted(expected_sample_ids - manifest_ids)
        extra = sorted(manifest_ids - expected_sample_ids)
        problems.append(
            f"manifest/split IDs differ: missing={missing[:5]} extra={extra[:5]}"
        )
    if any(
        "references/cache" in str(row.get(field, "")).replace("\\", "/")
        for row in rows
        for field in fields
    ):
        problems.append("model-derived reference cache appears in GT manifest")
    ready = 0
    for row in rows:
        missing_fields = [
            field
            for field in fields
            if not Path(row.get(field, "")).is_file()
        ]
        if missing_fields:
            if len(problems) < 20:
                problems.append(
                    f"{row['sample_id']}: missing {','.join(missing_fields)}"
                )
        else:
            ready += 1
    is_ready = (
        not problems
        and len(rows) == len(expected_sample_ids)
        and ready == len(expected_sample_ids)
    )
    return is_ready, ready, len(rows), problems


def _commands(config_path: Path, output_dir: Path) -> list[str]:
    checkpoint = output_dir / "checkpoints" / "best.pt"
    thresholds = output_dir / "thresholds_val.json"
    metrics = output_dir / "test_metrics.json"
    return [
        f'python train.py --config "{config_path.as_posix()}"',
        (
            "python -m onestroke_model.scripts.calibrate_thresholds "
            f'--config "{config_path.as_posix()}" '
            f'--checkpoint "{checkpoint.as_posix()}" '
            f'--output "{thresholds.as_posix()}"'
        ),
        (
            f'python eval.py --config "{config_path.as_posix()}" '
            f'--checkpoint "{checkpoint.as_posix()}" '
            f'--thresholds-json "{thresholds.as_posix()}" '
            f'--split test --output "{metrics.as_posix()}"'
        ),
    ]


def build_character_disjoint_run_plan(
    project_root: str | Path,
    *,
    split_report_path: str | Path,
    config_paths: Sequence[str | Path] = DEFAULT_CONFIGS,
    expected_split_sha256: str = QC_CLEAN_SPLIT_SHA256,
    expected_sample_counts: dict[str, int] = EXPECTED_SPLIT_SAMPLE_COUNTS,
    expected_character_counts: dict[str, int] = EXPECTED_SPLIT_CHARACTER_COUNTS,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    report_path = _resolve_project_path(root, split_report_path)
    if not report_path.is_file():
        raise ValueError(f"character-disjoint split report not found: {report_path}")
    split_report = json.loads(report_path.read_text(encoding="utf-8"))
    split_path = _resolve_project_path(root, split_report["split_csv"])
    if not split_path.is_file():
        raise ValueError(f"frozen split CSV not found: {split_path}")
    split_validation = _validate_frozen_split(
        split_path,
        split_report,
        expected_split_sha256=expected_split_sha256,
        expected_sample_counts=expected_sample_counts,
        expected_character_counts=expected_character_counts,
    )

    plans: list[dict[str, Any]] = []
    for config_value in config_paths:
        config_path = _resolve_project_path(root, config_value)
        config = load_yaml(config_path)
        manifest_path = _resolve_project_path(root, config["data"]["manifest"])
        data_ready, ready_rows, total_rows, data_problems = _local_data_ready(
            manifest_path,
            expected_sample_ids=split_validation["sample_ids"],
        )
        model_name = str(config.get("model", {}).get("name", ""))
        task1_blocked = (
            config.get("research_status") == "BLOCKED_BY_TASK1"
            or (
                model_name == "deeplabv3plus"
                and not (
                    (root / "src/onestroke_model/models/deeplabv3plus.py").is_file()
                    or (root / "src/onestroke_model/models/deeplab.py").is_file()
                )
            )
        )
        status = (
            "BLOCKED_BY_TASK1"
            if task1_blocked
            else ("READY" if data_ready else "BLOCKED_DATA_PATHS")
        )
        output_dir = Path(config["output_dir"])
        plans.append(
            {
                "experiment_name": config["experiment_name"],
                "model_name": model_name,
                "seed": config["seed"],
                "config": str(config_path),
                "config_sha256": sha256_file(config_path),
                "status": status,
                "manifest": str(manifest_path),
                "manifest_sha256": (
                    sha256_file(manifest_path) if manifest_path.is_file() else None
                ),
                "locally_resolvable_samples": ready_rows,
                "usable_samples": total_rows,
                "data_problems": data_problems,
                "commands": _commands(
                    config_path.relative_to(root),
                    output_dir,
                ),
                "threshold_policy": "calibrate on validation only; test is evaluation-only",
            }
        )
    task1_runs = [run for run in plans if run["model_name"] == "deeplabv3plus"]
    task1_ready = bool(task1_runs) and all(run["status"] == "READY" for run in task1_runs)
    return {
        "schema_version": 1,
        "mode": "DRY_RUN_PLAN_ONLY",
        "training_executed": False,
        "split_sha256": split_validation["split_sha256"],
        "source_character_assignment_sha256": FROZEN_SPLIT_SHA256,
        "qc_exclusions_sha256": QC_EXCLUSIONS_SHA256,
        "split_report": str(report_path),
        "split_csv": str(split_path),
        "split_character_counts": split_validation["character_counts"],
        "split_sample_counts": split_validation["sample_counts"],
        "task1_ready": task1_ready,
        "runs": plans,
        "execution_policy": (
            "Dry-run only unless --execute is explicitly supplied. Full execution is "
            "refused unless every model, config, and data path is ready. Thresholds are "
            "calibrated on validation only; each test run is final evaluation-only."
        ),
    }
