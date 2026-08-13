from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from onestroke_model.expert_candidate_pairs import (
    CANDIDATE_STATUS,
    FREEZE_STATUS,
    WRITER_IDENTITY_STATUS,
    audit_samples,
    build_writer_forensics,
    construct_balanced_pairs,
    score_natural_pairs,
    select_internal_review_pairs,
)


def _eligible_rows(
    characters: int = 40,
    samples_per_character: int = 15,
) -> list[dict[str, object]]:
    return [
        {
            "sample_id": f"{char_id}/{sample_index}",
            "char_id": str(char_id),
            "eligible": True,
        }
        for char_id in range(characters)
        for sample_index in range(samples_per_character)
    ]


def test_balanced_candidate_builder_creates_400_unique_natural_pairs() -> None:
    pairs = construct_balanced_pairs(
        _eligible_rows(),
        pairs_per_character=10,
        seed=17,
    )
    assert len(pairs) == 400
    per_character = Counter(row["char_id"] for row in pairs)
    assert set(per_character.values()) == {10}
    unordered: set[tuple[str, str]] = set()
    for row in pairs:
        candidate = str(row["candidate_sample_id"])
        reference = str(row["reference_sample_id"])
        assert candidate != reference
        key = tuple(sorted((candidate, reference)))
        assert key not in unordered
        unordered.add(key)


def test_internal_selection_has_exact_150_and_three_or_four_per_character() -> None:
    candidates = []
    for char_id in range(40):
        for index in range(10):
            candidates.append(
                {
                    "pair_id": f"{char_id}-{index}",
                    "char_id": str(char_id),
                    "current_score": float(index * 10 + char_id / 100),
                    "coverage_aware_score": float(index * 10),
                    "coverage_correction_points": float(-char_id / 100),
                }
            )
    selected = select_internal_review_pairs(
        candidates,
        target_pairs=150,
        seed=23,
    )
    assert len(selected) == 150
    counts = Counter(row["char_id"] for row in selected)
    assert Counter(counts.values()) == {3: 10, 4: 30}
    for char_id, count in counts.items():
        scores = sorted(
            float(row["current_score"])
            for row in selected
            if row["char_id"] == char_id
        )
        assert scores[0] < scores[-1]


def _write_fixture_sample(
    root: Path,
    char_id: int,
    sample_index: int,
    *,
    duplicate_of: int | None = None,
    mismatched: bool = False,
) -> dict[str, str]:
    sample_dir = root / str(char_id) / str(sample_index)
    sample_dir.mkdir(parents=True, exist_ok=True)
    if duplicate_of is not None:
        source = root / str(char_id) / str(duplicate_of)
        Image.open(source / "0.jpg").save(sample_dir / "0.jpg")
        np.save(sample_dir / "0.npy", np.load(source / "0.npy"))
    else:
        image = np.full((32, 32), 255, dtype=np.uint8)
        image[8:24, 8 + sample_index : 12 + sample_index] = 0
        masks = np.zeros((32, 32, 6), dtype=np.uint8)
        if mismatched:
            masks[2:8, 20:28, 0] = 1
        else:
            masks[8:24, 8 + sample_index : 12 + sample_index, 0] = 1
        masks[14:16, 9 + sample_index : 11 + sample_index, 5] = 1
        Image.fromarray(image).save(sample_dir / "0.jpg")
        np.save(sample_dir / "0.npy", masks)
    return {
        "schema_version": "1",
        "data_version": "fixture",
        "sample_id": f"{char_id}/{sample_index}",
        "char_id": str(char_id),
        "char_name": "",
        "sample_index": str(sample_index),
        "source_id": "",
        "writer_id": "",
        "has_all_masks": "true",
        "errors": "",
    }


def test_quality_audit_excludes_bad_and_noncanonical_duplicate(
    tmp_path: Path,
) -> None:
    import csv

    data_root = tmp_path / "output_img"
    rows = [
        _write_fixture_sample(data_root, 0, 0),
        _write_fixture_sample(data_root, 0, 1, duplicate_of=0),
        _write_fixture_sample(data_root, 0, 2, mismatched=True),
    ]
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    records, quality, duplicates = audit_samples(
        manifest,
        data_root,
        image_mask_iou_exclusion_threshold=0.80,
    )
    lookup = {record.sample_id: record for record in records}
    assert lookup["0/0"].eligible
    assert not lookup["0/1"].eligible
    assert not lookup["0/2"].eligible
    assert len(duplicates) == 2
    assert all(row["writer_identity_status"] == WRITER_IDENTITY_STATUS for row in quality)


def test_candidate_constants_make_nonfrozen_status_explicit() -> None:
    assert CANDIDATE_STATUS == "CANDIDATE_ONLY_DO_NOT_RATE"
    assert FREEZE_STATUS == "NOT_FROZEN"


def test_real_scoring_fields_do_not_invent_writer_or_style_claims(
    tmp_path: Path,
) -> None:
    import csv

    data_root = tmp_path / "output_img"
    rows = [
        _write_fixture_sample(data_root, 0, 0),
        _write_fixture_sample(data_root, 0, 1),
    ]
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    records, _, _ = audit_samples(
        manifest,
        data_root,
        image_mask_iou_exclusion_threshold=0.80,
    )
    scored = score_natural_pairs(
        [
            {
                "pair_id": "fixture-pair",
                "char_id": "0",
                "candidate_sample_id": "0/0",
                "reference_sample_id": "0/1",
                "selection_seed": 1,
                "pair_generation_policy": "fixture",
            }
        ],
        records,
        data_root,
    )
    assert len(scored) == 1
    row = scored[0]
    assert row["writer_id"] == ""
    assert row["writer_identity_status"] == WRITER_IDENTITY_STATUS
    assert row["different_writer_claim"] is False
    assert row["style_id"] == "unknown_legacy_collection"
    assert row["cross_style_design"] is False
    assert row["cross_style_verified"] is False
    assert row["same_instance_detected"] is False
    assert row["same_image_detected"] is False
    assert row["same_mask_detected"] is False


def test_writer_forensics_scans_images_without_inventing_identity(
    tmp_path: Path,
) -> None:
    import csv

    data_root = tmp_path / "output_img"
    rows = [_write_fixture_sample(data_root, 0, 0)]
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = build_writer_forensics(manifest, dataset_root=data_root)
    assert report["writer_id_recoverable"] is False
    assert report["sample_index_is_writer_id"] is False
    assert report["image_metadata_scan"]["images_scanned"] == 1
    assert report["image_metadata_scan"]["identity_like_exif_fields"] == []
