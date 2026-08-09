from __future__ import annotations

import numpy as np

from onestroke_model.controlled_perturbations import (
    PreparedReferenceScorer,
    apply_perturbation,
    select_target_direction_channel,
)
from onestroke_model.style_scoring import score_masks


def _masks(size: int = 128) -> np.ndarray:
    m = np.zeros((size, size, 6), dtype=bool)
    c = size // 2
    m[c - 3 : c + 4, 24 : size - 24, 0] = True
    m[22 : size - 22, c - 3 : c + 4, 1] = True
    rr = np.arange(30, size - 30)
    for offset in range(-2, 3):
        cc = rr + offset - 6
        valid = (cc >= 0) & (cc < size)
        m[rr[valid], cc[valid], 2] = True
        cc2 = size - 1 - rr + offset + 5
        valid2 = (cc2 >= 0) & (cc2 < size)
        m[rr[valid2], cc2[valid2], 3] = True
    m[c + 17 : c + 23, c - 6 : c + 24, 4] = True
    m[c + 12 : c + 23, c + 19 : c + 24, 4] = True
    for y, x in ((c, c), (c + 20, c + 20), (30, 24)):
        m[y - 2 : y + 3, x - 2 : x + 3, 5] = True
    return m


def _assert_evidence_close(first: dict[str, object], second: dict[str, object]) -> None:
    for key in (
        "prototype_structure_score",
        "direction_macro_dice",
        "ink_iou",
        "keypoint_tolerant_f1_radius_3",
    ):
        assert np.isclose(float(first[key]), float(second[key]), atol=1e-12)
    first_transform = first["selected_transform"]
    second_transform = second["selected_transform"]
    assert isinstance(first_transform, dict)
    assert isinstance(second_transform, dict)
    for key in (
        "scale",
        "rotation_degrees",
        "translation_x",
        "translation_y",
        "alignment_ink_iou",
    ):
        assert np.isclose(float(first_transform[key]), float(second_transform[key]), atol=1e-12)


def test_prepared_reference_scorer_matches_production_score() -> None:
    reference = _masks()
    scorer = PreparedReferenceScorer(reference)
    cases = [
        reference,
        apply_perturbation(reference, "ref:A", "global_translation", 12).masks,
        apply_perturbation(reference, "ref:A", "global_rotation", 2).masks,
        apply_perturbation(reference, "ref:A", "direction_terminal_deletion", 0.20).masks,
        apply_perturbation(reference, "ref:A", "local_fragment_shift", 8).masks,
    ]
    for user in cases:
        production, production_aligned = score_masks(user, reference)
        prepared, prepared_aligned = scorer.score(user)
        _assert_evidence_close(production, prepared)
        assert np.array_equal(production_aligned, prepared_aligned)


def test_on_grid_allowed_global_transforms_can_be_recovered_exactly() -> None:
    reference = _masks()
    scorer = PreparedReferenceScorer(reference)
    for name, severity in (
        ("global_translation", 12),
        ("global_rotation", 1),
        ("global_scale_up", 0.05),
        ("global_scale_down", 0.05),
    ):
        outcome = apply_perturbation(reference, "ref:nuisance", name, severity)
        assert outcome.valid, (name, severity, outcome.invalid_reason)
        evidence, _ = scorer.score(outcome.masks)
        assert float(evidence["prototype_structure_score"]) >= 99.0, (name, severity, evidence)


def test_default_off_grid_nuisance_suite_produces_finite_scores() -> None:
    reference = _masks()
    scorer = PreparedReferenceScorer(reference)
    for name, severity in (
        ("global_rotation", 0.5),
        ("global_scale_up", 0.075),
        ("global_scale_down", 0.075),
        ("compound_allowed_transform", 1),
    ):
        outcome = apply_perturbation(reference, "ref:offgrid", name, severity)
        assert outcome.valid, (name, severity, outcome.invalid_reason)
        evidence, _ = scorer.score(outcome.masks)
        score = float(evidence["prototype_structure_score"])
        assert np.isfinite(score) and 0.0 <= score <= 100.0


def test_nested_terminal_deletion_is_nonincreasing() -> None:
    reference = _masks()
    scorer = PreparedReferenceScorer(reference)
    scores = []
    for fraction in (0.05, 0.10, 0.20, 0.30):
        outcome = apply_perturbation(
            reference, "ref:deletion", "direction_terminal_deletion", fraction
        )
        assert outcome.valid
        evidence, _ = scorer.score(outcome.masks)
        scores.append(float(evidence["prototype_structure_score"]))
    assert all(second <= first + 1e-9 for first, second in zip(scores[:-1], scores[1:]))
    assert scores[-1] < scores[0]


def test_keypoint_shift_audits_three_pixel_tolerance() -> None:
    reference = _masks()
    scorer = PreparedReferenceScorer(reference)
    near = apply_perturbation(reference, "ref:keypoint", "keypoint_shift", 2)
    far = apply_perturbation(reference, "ref:keypoint", "keypoint_shift", 12)
    assert near.valid and far.valid
    near_evidence, _ = scorer.score(near.masks)
    far_evidence, _ = scorer.score(far.masks)
    assert float(near_evidence["direction_macro_dice"]) == 1.0
    assert float(far_evidence["direction_macro_dice"]) == 1.0
    assert float(near_evidence["keypoint_tolerant_f1_radius_3"]) > float(
        far_evidence["keypoint_tolerant_f1_radius_3"]
    )
    assert float(near_evidence["prototype_structure_score"]) > float(
        far_evidence["prototype_structure_score"]
    )


def test_target_channel_selection_is_stable_and_reference_specific() -> None:
    reference = _masks()
    first = select_target_direction_channel(reference, "reference-A")
    second = select_target_direction_channel(reference, "reference-A")
    assert first == second
    assert first is not None and 0 <= first < 5


def test_prepared_reference_scorer_matches_production_across_default_suite() -> None:
    reference = _masks()
    scorer = PreparedReferenceScorer(reference)
    from onestroke_model.controlled_perturbations import DEFAULT_PERTURBATIONS

    for definition in DEFAULT_PERTURBATIONS:
        outcome = apply_perturbation(
            reference,
            "ref:full-parity",
            definition.name,
            definition.severities[0],
        )
        if not outcome.valid:
            continue
        production, production_aligned = score_masks(outcome.masks, reference)
        prepared, prepared_aligned = scorer.score(outcome.masks)
        _assert_evidence_close(production, prepared)
        assert np.array_equal(production_aligned, prepared_aligned)


def test_nuisance_global_transform_clipping_is_invalid_not_scored() -> None:
    reference = _masks()
    reference[:, :8, 0] = True
    reference[:, -8:, 1] = True
    outcome = apply_perturbation(
        reference, "ref:edge", "global_scale_up", 0.175
    )
    assert not outcome.valid
    assert outcome.invalid_reason is not None
    assert "clipping risk" in outcome.invalid_reason
    assert np.array_equal(outcome.masks, reference)
