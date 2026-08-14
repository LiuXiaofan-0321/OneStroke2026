from __future__ import annotations

from onestroke_model.spatial_score_development import analyze_development_rows


def test_grouped_development_analysis_produces_complete_oof_predictions() -> None:
    rows = []
    for char_id in range(10):
        for pair_index in range(3):
            value = (char_id * 3 + pair_index + 1) / 31
            rows.append(
                {
                    "char_id": str(char_id),
                    "human_mean": 1.0 + 4.0 * value,
                    "production_score": 100.0 * value,
                    "coverage_aware_score": 100.0 * value,
                    "polar_js_similarity": value,
                    "grid_js_similarity": value,
                    "projection_js_similarity": value,
                    "spatial_structure_score": 100.0 * value,
                    "group_cv_fold": char_id % 5,
                }
            )

    result = analyze_development_rows(
        rows,
        bootstrap_iterations=50,
        bootstrap_seed=7,
    )

    assert len(result["rows"]) == 30
    assert len(result["folds"]) == 5
    assert all(
        "spatial_group_cv_oof_score" in row for row in result["rows"]
    )
    assert (
        result["report"]["correlation_with_human_mean"][
            "spatial_group_cv_oof_score"
        ]["rho"]
        > 0.99
    )
    assert set(
        result["report"]["component_ablation"]["correlation_with_human_mean"]
    ) == {
        "grid_js_similarity",
        "polar_js_similarity",
        "projection_js_similarity",
    }
