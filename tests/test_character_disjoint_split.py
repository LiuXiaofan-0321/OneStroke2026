from __future__ import annotations

import csv
from pathlib import Path

from onestroke_model.data.character_split import (
    assign_character_disjoint,
    build_character_disjoint_split,
)


def _rows(num_characters: int = 10, samples_per_character: int = 4) -> list[dict[str, str]]:
    return [
        {
            "sample_id": f"{char_id}/{sample_index}",
            "char_id": str(char_id),
            "sample_index": str(sample_index),
            "writer_id": "",
            "source_id": "",
            "has_all_masks": "true",
            "errors": "",
        }
        for char_id in range(num_characters)
        for sample_index in range(samples_per_character)
    ]


def test_character_disjoint_assignment_is_deterministic_and_balanced() -> None:
    first_rows, first_report = assign_character_disjoint(
        _rows(), seed=20260811, train_ratio=0.7, val_ratio=0.15
    )
    second_rows, second_report = assign_character_disjoint(
        _rows(), seed=20260811, train_ratio=0.7, val_ratio=0.15
    )
    assert first_rows == second_rows
    assert first_report["characters"] == second_report["characters"]
    assert first_report["actual_character_counts"] == {"train": 7, "val": 2, "test": 1}
    assert all(first_report["assertions"].values())


def test_every_character_occurs_in_exactly_one_split() -> None:
    rows, _ = assign_character_disjoint(
        _rows(num_characters=12, samples_per_character=3),
        seed=7,
        train_ratio=0.6,
        val_ratio=0.2,
    )
    assignments: dict[str, set[str]] = {}
    for row in rows:
        assignments.setdefault(str(row["char_id"]), set()).add(str(row["split"]))
    assert assignments
    assert all(len(splits) == 1 for splits in assignments.values())


def test_writer_overlap_is_reported_not_hidden() -> None:
    rows = _rows(num_characters=6, samples_per_character=2)
    for row in rows:
        row["writer_id"] = "shared-writer"
    _, report = assign_character_disjoint(
        rows, seed=1, train_ratio=0.5, val_ratio=0.25
    )
    assert report["identity_overlap"]["writer_id"]["cross_split_value_count"] == 1
    assert report["identity_overlap"]["writer_id"]["cross_split_values"]["shared-writer"] == [
        "test",
        "train",
        "val",
    ]


def test_written_split_contains_hash_and_provenance(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    fieldnames = list(_rows()[0])
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_rows())
    output = tmp_path / "splits.csv"
    report_path = tmp_path / "report.json"
    report = build_character_disjoint_split(
        manifest,
        output,
        report_path,
        seed=20260811,
        project_root=tmp_path,
    )
    assert output.is_file()
    assert report_path.is_file()
    assert len(report["manifest_sha256"]) == 64
    assert len(report["split_sha256"]) == 64
    assert report["assertions"]["train_test_character_overlap_zero"] is True
