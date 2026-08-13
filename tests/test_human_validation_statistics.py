from __future__ import annotations

from pathlib import Path

from onestroke_model.human_validation_statistics import (
    build_human_validation_statistics,
    quadratic_weighted_kappa,
    write_human_validation_statistics,
)


def _study_rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    pairs: list[dict[str, object]] = []
    ratings: list[dict[str, object]] = []
    for index in range(8):
        source_id = f"pair-{index}"
        blinded_id = f"original-{index}"
        pairs.append(
            {
                "blinded_pair_id": blinded_id,
                "source_pair_id": source_id,
                "is_repeat": False,
                "target_char": str(index % 4),
                "system_score": float(index * 10),
                "coverage_aware_score": float(index * 10 + (index % 2)),
            }
        )
        base = 1 + index // 2
        for evaluator, offset in (("E01", 0), ("E02", 0), ("E03", 1)):
            ratings.append(
                {
                    "blinded_pair_id": blinded_id,
                    "evaluator_id": evaluator,
                    "rating": min(5, base + offset),
                }
            )
        if index < 2:
            repeat_id = f"repeat-{index}"
            pairs.append(
                {
                    "blinded_pair_id": repeat_id,
                    "source_pair_id": source_id,
                    "is_repeat": True,
                    "target_char": str(index % 4),
                    "system_score": float(index * 10),
                    "coverage_aware_score": float(index * 10 + (index % 2)),
                }
            )
            for evaluator, value in (("E01", base), ("E02", base + 1), ("E03", base + 1)):
                ratings.append(
                    {
                        "blinded_pair_id": repeat_id,
                        "evaluator_id": evaluator,
                        "rating": value,
                    }
                )
    return pairs, ratings


def test_quadratic_weighted_kappa_handles_perfect_agreement() -> None:
    assert quadratic_weighted_kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 1.0


def test_human_statistics_keep_repeats_out_of_icc_and_correlation() -> None:
    pairs, ratings = _study_rows()
    result = build_human_validation_statistics(
        pairs,
        ratings,
        bootstrap_iterations=50,
        seed=1,
    )
    report = result["report"]
    assert report["data_integrity"]["presentation_count"] == 10
    assert report["data_integrity"]["canonical_pair_count"] == 8
    assert report["canonical_inter_rater_reliability"]["n_targets"] == 8
    assert len(result["canonical_pair_ratings"]) == 8
    assert len(result["repeat_consistency"]) == 4
    assert result["repeat_consistency"][-1]["n_hidden_repeat_pairs"] == 6


def test_human_statistics_write_expected_outputs(tmp_path: Path) -> None:
    pairs, ratings = _study_rows()
    result = build_human_validation_statistics(
        pairs,
        ratings,
        bootstrap_iterations=20,
        seed=2,
    )
    write_human_validation_statistics(tmp_path, result)
    expected = (
        "human_validation_report.json",
        "HUMAN_VALIDATION_REPORT.md",
        "canonical_pair_ratings.csv",
        "per_evaluator_summary.csv",
        "per_character_summary.csv",
        "repeat_consistency.csv",
        "pair_disagreement_cases.csv",
        "table_human_validation.tex",
        "table_rater_reliability.tex",
    )
    assert all((tmp_path / name).is_file() for name in expected)
