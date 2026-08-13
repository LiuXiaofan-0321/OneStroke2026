from __future__ import annotations

from pathlib import Path

import numpy as np

from onestroke_model.expert_validation import (
    analyze_expert_ratings,
    icc_2_1_and_2_k,
    select_expert_rating_pairs,
    write_expert_study_package,
)


def _candidates(count: int = 30) -> list[dict[str, object]]:
    return [
        {
            "pair_id": f"pair-{index}",
            "target_char": str(index % 6),
            "style_id": f"style-{index % 2}",
            "system_score": float(index * 100 / max(1, count - 1)),
            "candidate_asset": f"candidate-{index}.png",
            "reference_asset": f"reference-{index}.png",
        }
        for index in range(count)
    ]


def test_blinded_package_hides_scores_and_includes_repeats(tmp_path: Path) -> None:
    internal, form, metadata = select_expert_rating_pairs(
        _candidates(),
        target_pairs=20,
        duplicate_fraction=0.10,
        seed=7,
    )
    assert len(internal) == 22
    assert sum(bool(row["is_repeat"]) for row in internal) == 2
    assert all("system_score" not in row for row in form)
    assert metadata["evaluator_form_exposes_system_score"] is False
    write_expert_study_package(
        tmp_path,
        internal_rows=internal,
        form_rows=form,
        metadata=metadata,
    )
    assert (tmp_path / "expert_rating_pairs.csv").is_file()
    assert (tmp_path / "expert_rating_form.csv").is_file()
    assert (tmp_path / "expert_rating_instructions.md").is_file()


def test_icc_is_high_for_consistent_raters() -> None:
    matrix = np.asarray(
        [
            [1, 1, 1],
            [2, 2, 2],
            [3, 3, 3],
            [4, 4, 4],
            [5, 5, 5],
        ],
        dtype=float,
    )
    result = icc_2_1_and_2_k(matrix)
    assert result["icc_2_1"] is not None
    assert float(result["icc_2_1"]) > 0.99
    assert float(result["icc_2_k"]) > 0.99


def test_analysis_uses_canonical_pairs_and_reports_repeat_consistency() -> None:
    internal, _, _ = select_expert_rating_pairs(
        _candidates(12),
        target_pairs=10,
        duplicate_fraction=0.20,
        seed=3,
    )
    ratings = []
    for row in internal:
        for evaluator, offset in (("e1", 0), ("e2", 0), ("e3", 1)):
            base = 1 + int(float(row["system_score"]) // 25)
            ratings.append(
                {
                    "blinded_pair_id": row["blinded_pair_id"],
                    "evaluator_id": evaluator,
                    "rating": min(5, base + offset),
                }
            )
    aggregate, report = analyze_expert_ratings(
        internal,
        ratings,
        bootstrap_iterations=20,
        seed=1,
    )
    assert len(aggregate) == len(internal)
    assert report["evaluator_count"] == 3
    assert report["spearman_system_vs_expert_mean"] is not None
    assert report["icc"]["icc_2_k"] is not None
    assert report["intra_rater_repeat_consistency"]["paired_repeat_ratings"] > 0


def test_analysis_handles_csv_string_boole_for_repeat_selection() -> None:
    internal, _, _ = select_expert_rating_pairs(
        _candidates(12),
        target_pairs=10,
        duplicate_fraction=0.20,
        seed=3,
    )
    as_csv_strings = [
        {
            **row,
            "is_repeat": "True" if row["is_repeat"] else "False",
        }
        for row in internal
    ]
    ratings = [
        {
            "blinded_pair_id": row["blinded_pair_id"],
            "evaluator_id": evaluator,
            "rating": 3,
        }
        for row in as_csv_strings
        for evaluator in ("e1", "e2")
    ]
    aggregate, report = analyze_expert_ratings(
        as_csv_strings,
        ratings,
        bootstrap_iterations=10,
        seed=1,
    )
    assert report["canonical_rated_pairs"] == 10
    assert len(aggregate) == 12
