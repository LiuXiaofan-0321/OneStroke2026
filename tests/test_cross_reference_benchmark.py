from __future__ import annotations

from pathlib import Path

import numpy as np

from onestroke_model.cross_reference_benchmark import (
    audit_pair_availability,
    score_cross_reference_pairs,
    select_cross_reference_pairs,
    summarize_cross_reference_scores,
    write_cross_reference_outputs,
)


def _references() -> list[dict[str, str]]:
    return [
        {"reference_id": "a1", "style_id": "a", "target_char": "永"},
        {"reference_id": "a2", "style_id": "a", "target_char": "永"},
        {"reference_id": "b1", "style_id": "b", "target_char": "永"},
        {"reference_id": "a3", "style_id": "a", "target_char": "人"},
    ]


def _mask(offset: int = 0) -> np.ndarray:
    masks = np.zeros((64, 64, 6), dtype=bool)
    masks[28:35, 12 + offset : 50 + offset, 0] = True
    masks[20:45, 30:34, 1] = True
    masks[28, 12 + offset, 5] = True
    return masks


def test_availability_reports_supported_pair_types() -> None:
    report = audit_pair_availability(_references())
    assert report["availability"]["same_character_same_style_different_instance"][
        "available_unordered_pairs"
    ] == 1
    assert report["availability"]["same_character_cross_style"][
        "available_unordered_pairs"
    ] == 2


def test_pair_selection_is_deterministic_score_independent_and_has_no_self_pairs() -> None:
    first = select_cross_reference_pairs(_references(), seed=9, negative_pairs=2)
    second = select_cross_reference_pairs(_references(), seed=9, negative_pairs=2)
    assert first == second
    assert all(
        row["candidate_reference_id"] != row["reference_reference_id"] for row in first
    )
    assert sum(row["pair_type"] == "different_character_negative" for row in first) == 2


def test_scoring_and_summary_use_cached_masks() -> None:
    pairs = select_cross_reference_pairs(_references(), seed=9, negative_pairs=1)
    cached = [
        {**row, "masks": _mask(index)}
        for index, row in enumerate(_references())
    ]
    scores = score_cross_reference_pairs(pairs, cached)
    summary, statistics = summarize_cross_reference_scores(
        scores, bootstrap_iterations=20, seed=1
    )
    assert len(scores) == len(pairs)
    assert {row["pair_type"] for row in summary} == {
        "same_character_same_style_different_instance",
        "same_character_cross_style",
        "different_character_negative",
    }
    assert "effects_vs_negative" in statistics


def test_blocked_output_contains_pairs_but_no_fabricated_scores(tmp_path: Path) -> None:
    availability = audit_pair_availability(_references())
    pairs = select_cross_reference_pairs(_references(), seed=1, negative_pairs=1)
    report = write_cross_reference_outputs(
        tmp_path,
        availability=availability,
        pairs=pairs,
        scores=None,
        input_metadata={"cache_status": "BLOCKED"},
    )
    assert report["formal_results_available"] is False
    assert (tmp_path / "cross_reference_pair_availability.json").is_file()
    assert (tmp_path / "cross_reference_pairs.csv").is_file()
    assert (tmp_path / "BLOCKED.md").is_file()
    assert not (tmp_path / "cross_reference_scores.csv").exists()


def test_successful_output_removes_stale_blocked_marker(tmp_path: Path) -> None:
    availability = audit_pair_availability(_references())
    pairs = select_cross_reference_pairs(_references(), seed=1, negative_pairs=1)
    cached = [
        {**row, "masks": _mask(index)}
        for index, row in enumerate(_references())
    ]
    scores = score_cross_reference_pairs(pairs, cached)
    (tmp_path / "BLOCKED.md").write_text("stale", encoding="utf-8")

    report = write_cross_reference_outputs(
        tmp_path,
        availability=availability,
        pairs=pairs,
        scores=scores,
        input_metadata={"cache_status": "PASS"},
    )

    assert report["formal_results_available"] is True
    assert not (tmp_path / "BLOCKED.md").exists()
