from __future__ import annotations

from onestroke_model.confirmatory_pair_selection import select_confirmatory_pairs


def _pair(char_id: int, index: int) -> dict[str, object]:
    return {
        "pair_id": f"P-{char_id}-{index}",
        "char_id": str(char_id),
        "target_char": f"C{char_id}",
        "candidate_instance_id": f"{char_id}/c{index}",
        "reference_instance_id": f"{char_id}/r{index}",
        "same_instance_detected": False,
        "same_image_detected": False,
        "same_mask_detected": False,
        "near_duplicate_suspected": False,
    }


def test_confirmatory_selection_excludes_development_pairs_and_instances() -> None:
    pool = [_pair(char_id, index) for char_id in range(4) for index in range(6)]
    development = [
        {
            **_pair(char_id, 0),
            "candidate_instance_id": f"{char_id}/c0",
            "reference_instance_id": f"{char_id}/r0",
        }
        for char_id in range(4)
    ]

    selected, reserves, metadata = select_confirmatory_pairs(
        pool,
        development,
        target_pair_count=10,
        base_pairs_per_character=2,
    )

    development_pair_ids = {row["pair_id"] for row in development}
    development_instances = {
        str(row[field])
        for row in development
        for field in ("candidate_instance_id", "reference_instance_id")
    }
    selected_instances = {
        str(row[field])
        for row in selected
        for field in ("candidate_instance_id", "reference_instance_id")
    }

    assert len(selected) == 10
    assert len({row["char_id"] for row in selected}) == 4
    assert not ({row["pair_id"] for row in selected} & development_pair_ids)
    assert not (selected_instances & development_instances)
    assert metadata["selection_uses_spatial_score"] is False
    assert metadata["instance_overlap_with_development"] == 0
    assert reserves
