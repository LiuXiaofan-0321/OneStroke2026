from __future__ import annotations

import json
from pathlib import Path

import pytest

from onestroke_model.controlled_perturbations import PerturbationDefinition
from onestroke_model.perturbation_benchmark import synthetic_references
from onestroke_model.structure_score_audit_benchmark import (
    audit_invariants,
    component_correlations,
    coverage_summary,
    run_structure_score_audit,
    summarize_weight_sensitivity,
    variant_behavior,
    variant_overall_summary,
    weight_sensitivity_grid,
    write_structure_score_audit_outputs,
)


def _small_suite() -> tuple[PerturbationDefinition, ...]:
    return (
        PerturbationDefinition(
            name="global_translation",
            family="nuisance",
            severities=(4.0, 8.0),
            unit="pixels",
            expected_behavior="invariant",
            description="test",
        ),
        PerturbationDefinition(
            name="direction_terminal_deletion",
            family="structural",
            severities=(0.05, 0.20),
            unit="target_channel_fraction",
            expected_behavior="decreasing",
            description="test",
        ),
    )


def test_audit_preserves_current_score_and_alignment_objective() -> None:
    _, references = synthetic_references(128)
    rows, coverage = run_structure_score_audit(references[:2], _small_suite())
    invariants = audit_invariants(rows)
    assert len(coverage) == 2
    assert invariants["max_abs_v1_recompute_minus_production"] == pytest.approx(0.0, abs=1e-12)
    assert invariants["max_abs_ink_iou_minus_alignment_objective"] == pytest.approx(0.0, abs=1e-12)
    identity = [row for row in rows if row["perturbation"] == "identity"]
    assert all(float(row["v1_current"]) == pytest.approx(100.0) for row in identity)
    assert all(float(row["v1_coverage_corrected"]) == pytest.approx(100.0) for row in identity)
    assert all(float(row["v2_nonredundant_candidate"]) == pytest.approx(100.0) for row in identity)


def test_synthetic_all_channel_fixture_leaves_coverage_corrected_equal_to_v1() -> None:
    _, references = synthetic_references(128)
    rows, _ = run_structure_score_audit(references[:1], _small_suite())
    valid = [row for row in rows if row["status"] == "valid"]
    assert all(int(row["active_direction_count"]) == 5 for row in valid)
    assert all(bool(row["keypoint_available"]) for row in valid)
    assert all(
        float(row["v1_current"]) == pytest.approx(float(row["v1_coverage_corrected"]), abs=1e-12)
        for row in valid
    )


def test_variant_behavior_keeps_translation_invariant_and_deletion_nonincreasing() -> None:
    _, references = synthetic_references(128)
    rows, _ = run_structure_score_audit(references[:2], _small_suite())
    behavior = variant_behavior(rows, _small_suite())
    translation = [row for row in behavior if row["perturbation"] == "global_translation"]
    deletion = [row for row in behavior if row["perturbation"] == "direction_terminal_deletion"]
    assert translation
    assert deletion
    assert all(float(row["max_abs_score_drop"]) == pytest.approx(0.0, abs=1e-12) for row in translation)
    assert all(float(row["adjacent_nonincreasing_pair_rate"]) == pytest.approx(1.0) for row in deletion)


def test_component_correlations_are_machine_readable() -> None:
    _, references = synthetic_references(128)
    rows, _ = run_structure_score_audit(references[:2], _small_suite())
    correlations = component_correlations(rows)
    assert any(
        row["subset"] == "structural"
        and row["component_a"] == "direction_macro_active"
        and row["component_b"] == "ink_iou"
        for row in correlations
    )





def test_overall_summary_macro_counts_perturbation_definitions() -> None:
    _, references = synthetic_references(128)
    rows, coverage = run_structure_score_audit(references[:2], _small_suite())
    overall = variant_overall_summary(rows, _small_suite())
    assert overall
    assert all(int(row["n_nuisance_perturbations_in_macro"]) == 1 for row in overall)
    assert all(int(row["n_structural_perturbations_in_macro"]) == 1 for row in overall)

    coverage_stats = coverage_summary(coverage)
    assert coverage_stats["median_keypoint_radius3_fraction_of_reference_bbox_diagonal"] > 0
    assert (
        coverage_stats["p05_keypoint_radius3_fraction_of_reference_bbox_diagonal"]
        <= coverage_stats["median_keypoint_radius3_fraction_of_reference_bbox_diagonal"]
        <= coverage_stats["p95_keypoint_radius3_fraction_of_reference_bbox_diagonal"]
    )

def test_weight_sensitivity_is_audit_grid_not_hidden_tuning() -> None:
    _, references = synthetic_references(128)
    rows, _ = run_structure_score_audit(references[:2], _small_suite())
    grid = weight_sensitivity_grid(rows, _small_suite(), step=0.05)
    assert len(grid) == 231
    current = [row for row in grid if row["is_current_0.55_0.25_0.20"]]
    assert len(current) == 1
    summary = summarize_weight_sensitivity(grid)
    assert summary["n_weight_triples"] == 231
    assert "not a license to retune" in summary["warning"]

def test_output_bundle_contains_raw_and_summary_artifacts(tmp_path: Path) -> None:
    metadata, references = synthetic_references(128)
    rows, coverage = run_structure_score_audit(references[:1], _small_suite())
    (tmp_path / "BLOCKED.md").write_text("stale", encoding="utf-8")
    report = write_structure_score_audit_outputs(
        tmp_path,
        rows,
        coverage,
        input_metadata=metadata,
        runtime_metadata={"test": True},
        definitions=_small_suite(),
    )
    expected = {
        "score_audit_results.csv",
        "reference_coverage.csv",
        "component_correlation.csv",
        "keypoint_metric_comparison.csv",
        "component_sensitivity.csv",
        "score_variant_correlation.csv",
        "score_variant_behavior.csv",
        "score_variant_overall.csv",
        "score_variant_overall_by_style.csv",
        "reference_coverage_by_style.csv",
        "weight_sensitivity_grid.csv",
        "structure_score_audit_report.json",
        "structure_score_audit_report.md",
    }
    assert expected.issubset({path.name for path in tmp_path.iterdir()})
    assert not (tmp_path / "BLOCKED.md").exists()
    parsed = json.loads((tmp_path / "structure_score_audit_report.json").read_text(encoding="utf-8"))
    assert parsed["audit_name"] == report["audit_name"]
