from __future__ import annotations

import csv
from pathlib import Path

import pytest

from onestroke_model.data.data_contract import validate_data_contract
from onestroke_model.reproducibility import sha256_file


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_data_contract_accepts_clean_split_and_frozen_hashes(tmp_path: Path) -> None:
    image = tmp_path / "image.jpg"
    mask = tmp_path / "mask.npy"
    image.write_bytes(b"image")
    mask.write_bytes(b"mask")
    manifest = tmp_path / "manifest.csv"
    _write_csv(
        manifest,
        [
            {
                "sample_id": "a",
                "image_path": str(image),
                "vec1_path": str(mask),
                "vec2_path": str(mask),
                "vec3_path": str(mask),
                "vec4_path": str(mask),
                "vec5_path": str(mask),
                "keypoint_path": str(mask),
            }
        ],
    )
    splits = tmp_path / "splits.csv"
    _write_csv(splits, [{"sample_id": "a", "split": "train"}])
    exclusions = tmp_path / "exclusions.csv"
    _write_csv(exclusions, [{"sample_id": "b", "decision": "EXCLUDE"}])
    result = validate_data_contract(
        {
            "manifest": str(manifest),
            "splits": str(splits),
            "expected_manifest_sha256": sha256_file(manifest),
            "expected_splits_sha256": sha256_file(splits),
            "expected_split_counts": {"train": 1},
            "qc_exclusions": str(exclusions),
            "expected_qc_exclusions_sha256": sha256_file(exclusions),
        }
    )
    assert result["active_sample_count"] == 1
    assert result["qc_exclusion_count"] == 1


def test_data_contract_refuses_excluded_sample_in_active_split(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    image = tmp_path / "image.jpg"
    mask = tmp_path / "mask.npy"
    image.write_bytes(b"image")
    mask.write_bytes(b"mask")
    _write_csv(
        manifest,
        [
            {
                "sample_id": "a",
                "image_path": str(image),
                "vec1_path": str(mask),
                "vec2_path": str(mask),
                "vec3_path": str(mask),
                "vec4_path": str(mask),
                "vec5_path": str(mask),
                "keypoint_path": str(mask),
            }
        ],
    )
    splits = tmp_path / "splits.csv"
    _write_csv(splits, [{"sample_id": "a", "split": "test"}])
    exclusions = tmp_path / "exclusions.csv"
    _write_csv(exclusions, [{"sample_id": "a", "decision": "EXCLUDE"}])
    with pytest.raises(ValueError, match="QC-excluded"):
        validate_data_contract(
            {
                "manifest": str(manifest),
                "splits": str(splits),
                "qc_exclusions": str(exclusions),
            }
        )
