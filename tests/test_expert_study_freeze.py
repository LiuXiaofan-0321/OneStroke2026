from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from onestroke_model.expert_study_freeze import (
    FROZEN_STATUS,
    _evaluator_order,
    _make_presentations,
    freeze_selection,
    validate_approved_selection,
)


def _rows(count: int = 150) -> list[dict[str, object]]:
    return [
        {
            "pair_id": f"pair-{index:03d}",
            "selection_rank": index + 1,
            "char_id": str(index % 40),
            "target_char": "禾",
            "candidate_instance_id": f"{index % 40}/{index}",
            "reference_instance_id": f"{index % 40}/{index + 1000}",
            "current_score": float(index % 100),
            "coverage_aware_score": float(index % 90),
            "candidate_image_sha256": f"ci-{index}",
            "reference_image_sha256": f"ri-{index}",
            "candidate_mask_sha256": f"cm-{index}",
            "reference_mask_sha256": f"rm-{index}",
            "same_image_detected": False,
            "same_mask_detected": False,
            "near_duplicate_suspected": False,
            "writer_identity_status": "UNRECOVERABLE_FROM_AVAILABLE_EVIDENCE",
            "different_writer_claim": False,
            "style_id": "unknown_legacy_collection",
            "cross_style_verified": False,
        }
        for index in range(count)
    ]


def test_freeze_validates_150_and_refuses_overwrite(tmp_path: Path) -> None:
    rows = validate_approved_selection(_rows())
    frozen = tmp_path / "frozen_expert_pairs_v1.csv"
    result = freeze_selection(rows, frozen, approval_note="approved")
    assert len(result) == 150
    assert all(row["freeze_status"] == FROZEN_STATUS for row in result)
    with pytest.raises(FileExistsError):
        freeze_selection(rows, frozen, approval_note="approved")


def test_hidden_repeats_are_exactly_ten_percent_and_blinded() -> None:
    rows = validate_approved_selection(_rows())
    presentations = _make_presentations(
        rows,
        duplicate_fraction=0.10,
        seed=7,
    )
    assert len(presentations) == 165
    assert sum(bool(row["is_repeat"]) for row in presentations) == 15
    assert len({row["blinded_pair_id"] for row in presentations}) == 165
    source_counts = Counter(row["source_pair_id"] for row in presentations)
    assert Counter(source_counts.values()) == {1: 135, 2: 15}


def test_evaluator_orders_are_different_and_hide_adjacent_repeats() -> None:
    presentations = _make_presentations(
        validate_approved_selection(_rows()),
        duplicate_fraction=0.10,
        seed=7,
    )
    first = _evaluator_order(presentations, "E01", seed=7)
    second = _evaluator_order(presentations, "E02", seed=7)
    assert [row["blinded_pair_id"] for row in first] != [
        row["blinded_pair_id"] for row in second
    ]
    assert all(
        first[index]["source_pair_id"] != first[index - 1]["source_pair_id"]
        for index in range(1, len(first))
    )


def test_invalid_identity_or_duplicate_claim_cannot_be_frozen() -> None:
    rows = _rows()
    rows[0]["different_writer_claim"] = True
    with pytest.raises(ValueError):
        validate_approved_selection(rows)
