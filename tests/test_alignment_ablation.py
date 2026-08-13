from __future__ import annotations

from pathlib import Path

from onestroke_model.alignment_ablation import (
    ERROR_MASKING_RATIO_FORMULA,
    error_masking_ratio,
    run_alignment_ablation,
    score_alignment_variant,
    summarize_alignment_ablation,
    write_alignment_ablation_outputs,
)
from onestroke_model.controlled_perturbations import (
    PerturbationDefinition,
    apply_perturbation,
)
from onestroke_model.perturbation_benchmark import synthetic_references
from onestroke_model.style_scoring import score_masks


def _definitions() -> tuple[PerturbationDefinition, ...]:
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
            severities=(0.1, 0.2),
            unit="fraction",
            expected_behavior="decreasing",
            description="test",
        ),
    )


def test_current_variant_matches_production_score() -> None:
    _, references = synthetic_references(128)
    reference = references[0]
    outcome = apply_perturbation(
        reference["masks"],
        reference["reference_id"],
        "global_translation",
        4.0,
    )
    expected, _ = score_masks(outcome.masks, reference["masks"])
    actual = score_alignment_variant(
        outcome.masks,
        reference["masks"],
        "current_constrained",
    )
    assert abs(
        actual["prototype_structure_score"] - expected["prototype_structure_score"]
    ) < 1e-9


def test_no_alignment_is_more_sensitive_to_recoverable_translation() -> None:
    _, references = synthetic_references(128)
    reference = references[0]
    outcome = apply_perturbation(
        reference["masks"],
        reference["reference_id"],
        "global_translation",
        8.0,
    )
    no_alignment = score_alignment_variant(
        outcome.masks,
        reference["masks"],
        "no_alignment",
    )
    constrained = score_alignment_variant(
        outcome.masks,
        reference["masks"],
        "current_constrained",
    )
    assert constrained["prototype_structure_score"] > no_alignment[
        "prototype_structure_score"
    ]


def test_error_masking_ratio_formula_is_explicit_and_unclipped() -> None:
    assert "no_alignment_structural_drop" in ERROR_MASKING_RATIO_FORMULA
    assert error_masking_ratio(20.0, 5.0) == 0.75
    assert error_masking_ratio(20.0, 25.0) == -0.25
    assert error_masking_ratio(0.0, 0.0) is None


def test_ablation_smoke_writes_all_variants(tmp_path: Path) -> None:
    metadata, references = synthetic_references(128)
    rows, baselines = run_alignment_ablation(
        references[:1],
        definitions=_definitions(),
    )
    (tmp_path / "BLOCKED.md").write_text("stale", encoding="utf-8")
    summary, curves = summarize_alignment_ablation(rows, _definitions())
    assert {row["alignment_variant"] for row in summary} == {
        "no_alignment",
        "current_constrained",
        "wide_similarity",
    }
    assert curves
    report = write_alignment_ablation_outputs(
        tmp_path,
        rows=rows,
        baselines=baselines,
        input_metadata=metadata,
        definitions=_definitions(),
    )
    assert report["formal_results_available"] is True
    assert not (tmp_path / "BLOCKED.md").exists()
    assert (tmp_path / "alignment_ablation_results.csv").is_file()
    assert (tmp_path / "alignment_ablation_preregistered_config.json").is_file()


def test_missing_cache_output_contains_no_scores(tmp_path: Path) -> None:
    report = write_alignment_ablation_outputs(
        tmp_path,
        rows=None,
        baselines=None,
        input_metadata={"cache_status": "BLOCKED"},
        definitions=_definitions(),
    )
    assert report["formal_results_available"] is False
    assert (tmp_path / "BLOCKED.md").is_file()
    assert not (tmp_path / "alignment_ablation_results.csv").exists()
