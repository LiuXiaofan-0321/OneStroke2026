from __future__ import annotations

import csv
from pathlib import Path

from onestroke_model.journal_statistics import (
    alignment_paired_statistics,
    controlled_perturbation_statistics,
    feedback_failure_taxonomy,
)


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_controlled_statistics_separate_nuisance_and_structural_drop(tmp_path: Path) -> None:
    rows = []
    for reference_id in ("a", "b"):
        for severity, score in ((4.0, 99.0), (8.0, 97.0), (12.0, 95.0), (16.0, 93.0)):
            rows.append(
                {
                    "reference_id": reference_id,
                    "perturbation": "global_translation",
                    "family": "nuisance",
                    "severity": severity,
                    "status": "valid",
                    "score_drop_from_identity": 100.0 - score,
                    "prototype_structure_score": score,
                }
            )
    path = tmp_path / "controlled.csv"
    _write(path, rows)
    result = controlled_perturbation_statistics(path, bootstrap_iterations=20)
    translation = next(
        row for row in result if row["perturbation"] == "global_translation"
    )
    assert translation["analysis_metric"] == "absolute_score_drop"
    assert translation["n_valid"] == 8
    assert translation["adjacent_nonincreasing_rate"] == 1.0


def test_alignment_statistics_use_positive_benefit_orientation(tmp_path: Path) -> None:
    rows = []
    for reference_id in ("a", "b"):
        for variant, drop in (
            ("no_alignment", 30.0),
            ("current_constrained", 5.0),
            ("wide_similarity", 10.0),
        ):
            rows.append(
                {
                    "reference_id": reference_id,
                    "perturbation": "global_translation",
                    "family": "nuisance",
                    "severity": 4.0,
                    "alignment_variant": variant,
                    "observation_key": reference_id,
                    "valid": True,
                    "score_drop": drop,
                }
            )
    path = tmp_path / "alignment.csv"
    _write(path, rows)
    result = alignment_paired_statistics(path, bootstrap_iterations=20)
    comparison = next(
        row
        for row in result
        if row["comparison"] == "current_constrained_vs_no_alignment"
        and row["scope_type"] == "family"
    )
    assert comparison["benefit_delta_positive_favors_current"] == 25.0
    assert comparison["rank_biserial_positive_favors_current"] == 1.0


def test_feedback_taxonomy_marks_multi_region_definition_failure(tmp_path: Path) -> None:
    feedback = tmp_path / "feedback.csv"
    _write(
        feedback,
        [
            {
                "reference_id": "r",
                "style_id": "s",
                "target_char": "字",
                "perturbation": "extra_direction_fragment",
                "severity": 0.2,
                "rule_variant": "current",
                "status": "valid",
                "exact_region_localization": False,
                "truth_json": (
                    '{"affected_regions":["r0c0","r0c1"],'
                    '"target_channel":"vec1",'
                    '"difference_type":"extra_user_structure"}'
                ),
                "findings_json": (
                    '[{"finding_id":"local_direction_structure",'
                    '"channel":"vec1","difference_type":"extra_user_structure",'
                    '"region":"r0c0"}]'
                ),
            }
        ],
    )
    audit = tmp_path / "audit.csv"
    _write(
        audit,
        [
            {
                "reference_id": "r",
                "perturbation": "extra_direction_fragment",
                "severity": 0.2,
                "status": "valid",
                "selected_scale": 1.0,
                "selected_rotation_degrees": 0.0,
                "selected_translation_x": 0.0,
                "selected_translation_y": 0.0,
            }
        ],
    )
    detailed, summary = feedback_failure_taxonomy(feedback, audit)
    assert detailed[0]["primary_failure_type"] == "multi_region_or_grid_boundary_truth"
    assert summary[0]["count"] == 1
