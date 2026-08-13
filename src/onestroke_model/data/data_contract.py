"""Fail-closed validation for frozen manifests, splits, and QC exclusions."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from onestroke_model.reproducibility import sha256_file
from onestroke_model.utils.io import read_csv_rows


def _resolve(path_value: str | Path, project_root: Path) -> Path:
    path = Path(path_value)
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def _expected_counts(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): int(count) for key, count in value.items()}


def _resolve_manifest_value(manifest_path: Path, value: str, project_root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (project_root / path).resolve()


def validate_data_contract(
    data_config: dict[str, Any],
    *,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate a training/evaluation data contract before loading any samples."""

    root = Path(project_root or Path.cwd()).resolve()
    manifest_path = _resolve(data_config["manifest"], root)
    splits_path = _resolve(data_config["splits"], root)
    if not manifest_path.is_file():
        raise ValueError(f"data manifest not found: {manifest_path}")
    if not splits_path.is_file():
        raise ValueError(f"data split file not found: {splits_path}")

    manifest_rows = read_csv_rows(manifest_path)
    split_rows = read_csv_rows(splits_path)
    manifest_ids = [str(row["sample_id"]).strip() for row in manifest_rows]
    split_ids = [str(row["sample_id"]).strip() for row in split_rows]
    if len(set(manifest_ids)) != len(manifest_ids):
        raise ValueError("data manifest contains duplicate sample_id values")
    if len(set(split_ids)) != len(split_ids):
        raise ValueError("data split contains duplicate sample_id values")
    missing_from_manifest = sorted(set(split_ids) - set(manifest_ids))
    if missing_from_manifest:
        raise ValueError(
            "data split references samples absent from the manifest: "
            f"{missing_from_manifest[:10]}"
        )
    if any(
        "references/cache" in str(row.get(field, "")).replace("\\", "/")
        for row in manifest_rows
        for field in (
            "image_path",
            "vec1_path",
            "vec2_path",
            "vec3_path",
            "vec4_path",
            "vec5_path",
            "keypoint_path",
        )
    ):
        raise ValueError("model-derived reference cache is prohibited as segmentation GT")
    required_path_fields = (
        "image_path",
        "vec1_path",
        "vec2_path",
        "vec3_path",
        "vec4_path",
        "vec5_path",
        "keypoint_path",
    )
    missing_files: list[str] = []
    for row in manifest_rows:
        for field in required_path_fields:
            value = str(row.get(field, "")).strip()
            if not value or not _resolve_manifest_value(
                manifest_path, value, root
            ).is_file():
                missing_files.append(f"{row.get('sample_id', '')}:{field}")
                if len(missing_files) >= 20:
                    break
        if len(missing_files) >= 20:
            break
    if missing_files:
        raise ValueError(f"data manifest has missing files: {missing_files}")

    expected_manifest_hash = str(data_config.get("expected_manifest_sha256", "")).strip()
    actual_manifest_hash = sha256_file(manifest_path)
    if expected_manifest_hash and actual_manifest_hash != expected_manifest_hash:
        raise ValueError(
            "manifest SHA-256 mismatch: "
            f"expected={expected_manifest_hash} actual={actual_manifest_hash}"
        )
    expected_split_hash = str(data_config.get("expected_splits_sha256", "")).strip()
    actual_split_hash = sha256_file(splits_path)
    if expected_split_hash and actual_split_hash != expected_split_hash:
        raise ValueError(
            "split SHA-256 mismatch: "
            f"expected={expected_split_hash} actual={actual_split_hash}"
        )

    counts = Counter(str(row.get("split", "")).strip() for row in split_rows)
    expected_counts = _expected_counts(data_config.get("expected_split_counts"))
    if expected_counts and dict(counts) != expected_counts:
        raise ValueError(
            f"split counts changed: expected={expected_counts} actual={dict(counts)}"
        )

    exclusions_path: Path | None = None
    exclusion_hash: str | None = None
    exclusion_ids: set[str] = set()
    if data_config.get("qc_exclusions"):
        exclusions_path = _resolve(data_config["qc_exclusions"], root)
        if not exclusions_path.is_file():
            raise ValueError(f"QC exclusions file not found: {exclusions_path}")
        exclusion_hash = sha256_file(exclusions_path)
        expected_exclusion_hash = str(
            data_config.get("expected_qc_exclusions_sha256", "")
        ).strip()
        if expected_exclusion_hash and exclusion_hash != expected_exclusion_hash:
            raise ValueError(
                "QC exclusion SHA-256 mismatch: "
                f"expected={expected_exclusion_hash} actual={exclusion_hash}"
            )
        exclusion_ids = {
            str(row["sample_id"]).strip()
            for row in read_csv_rows(exclusions_path)
            if str(row.get("decision", "")).strip().upper() == "EXCLUDE"
        }
        leaked_exclusions = sorted(set(split_ids) & exclusion_ids)
        if leaked_exclusions:
            raise ValueError(
                "QC-excluded samples remain in the active split: "
                f"{leaked_exclusions[:10]}"
            )

    return {
        "manifest": str(manifest_path),
        "manifest_sha256": actual_manifest_hash,
        "splits": str(splits_path),
        "splits_sha256": actual_split_hash,
        "split_counts": dict(counts),
        "qc_exclusions": str(exclusions_path) if exclusions_path else None,
        "qc_exclusions_sha256": exclusion_hash,
        "qc_exclusion_count": len(exclusion_ids),
        "active_sample_count": len(split_rows),
        "reference_cache_used_as_ground_truth": False,
    }
