from __future__ import annotations

import csv
from pathlib import Path

import pytest

from onestroke_model.scripts.audit_course_legacy_overlap import (
    audit_course_legacy_overlap,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _fixture_paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "character_map_source": tmp_path / "character_map.csv",
        "course_manifest": tmp_path / "course_manifest.csv",
        "qc_manifest": tmp_path / "qc_manifest.csv",
        "splits_path": tmp_path / "splits.csv",
        "output_dir": tmp_path / "output",
    }


def _write_base_fixture(paths: dict[str, Path]) -> None:
    _write_csv(
        paths["character_map_source"],
        ["char_id", "target_char"],
        [
            {"char_id": "0", "target_char": "永"},
            {"char_id": "1", "target_char": "和"},
        ],
    )
    _write_csv(
        paths["qc_manifest"],
        ["sample_id", "image_path"],
        [
            {"sample_id": "train-0", "image_path": "images/train-0.png"},
            {"sample_id": "test-0", "image_path": "images/test-0.png"},
            {"sample_id": "test-1", "image_path": "images/test-1.png"},
        ],
    )
    _write_csv(
        paths["splits_path"],
        ["sample_id", "char_id", "split"],
        [
            {"sample_id": "train-0", "char_id": "0", "split": "train"},
            {"sample_id": "test-0", "char_id": "0", "split": "test"},
            {"sample_id": "test-1", "char_id": "1", "split": "test"},
        ],
    )


def test_no_overlap_writes_header_only_candidate_file(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)
    _write_base_fixture(paths)
    _write_csv(
        paths["course_manifest"],
        ["style_id", "target_char", "review_status"],
        [
            {
                "style_id": "course_a",
                "target_char": "天",
                "review_status": "approved",
            }
        ],
    )

    manifest = audit_course_legacy_overlap(**paths)

    assert manifest["status"] == "COMPLETE_NO_ELIGIBLE_PAIRS"
    assert manifest["total_style_specific_overlap_count"] == 0
    assert manifest["eligible_qc_test_sample_count"] == 0
    assert _read_csv(paths["output_dir"] / "eligible_course_scoring_pairs.csv") == []


def test_overlap_selects_only_qc_test_samples(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)
    _write_base_fixture(paths)
    _write_csv(
        paths["course_manifest"],
        ["style_id", "target_char", "review_status"],
        [
            {
                "style_id": "course_a",
                "target_char": "永",
                "review_status": "approved",
            },
            {
                "style_id": "course_a",
                "target_char": "和",
                "review_status": "rejected",
            },
        ],
    )

    manifest = audit_course_legacy_overlap(**paths)
    candidates = _read_csv(paths["output_dir"] / "eligible_course_scoring_pairs.csv")

    assert manifest["status"] == "COMPLETE"
    assert manifest["total_style_specific_overlap_count"] == 1
    assert manifest["eligible_qc_test_sample_count"] == 1
    assert candidates == [
        {
            "style_id": "course_a",
            "char_id": "0",
            "target_char": "永",
            "sample_id": "test-0",
            "image_path": "images/test-0.png",
            "split": "test",
        }
    ]


def test_conflicting_character_mapping_is_rejected(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)
    _write_base_fixture(paths)
    _write_csv(
        paths["character_map_source"],
        ["char_id", "target_char"],
        [
            {"char_id": "0", "target_char": "永"},
            {"char_id": "0", "target_char": "和"},
        ],
    )
    _write_csv(
        paths["course_manifest"],
        ["style_id", "target_char", "review_status"],
        [
            {
                "style_id": "course_a",
                "target_char": "永",
                "review_status": "approved",
            }
        ],
    )

    with pytest.raises(ValueError, match="inconsistent target_char"):
        audit_course_legacy_overlap(**paths)
