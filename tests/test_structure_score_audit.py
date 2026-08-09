from __future__ import annotations

import numpy as np
import pytest

from onestroke_model.perturbation_benchmark import synthetic_references
from onestroke_model.structure_score_audit import (
    compute_score_components,
    empty_direction_credit,
    keypoint_empty_credit_exposed,
    score_v1_coverage_corrected,
    score_v1_current,
    score_v2_nonredundant_candidate,
)
from onestroke_model.style_scoring import score_masks


def _single_direction_pair() -> tuple[np.ndarray, np.ndarray]:
    reference = np.zeros((48, 48, 6), dtype=bool)
    user = np.zeros_like(reference)
    reference[20:24, 10:30, 0] = True
    user[20:24, 10:20, 0] = True
    return user, reference


def test_v1_recomputation_matches_production_score() -> None:
    _, references = synthetic_references(128)
    masks = references[0]["masks"]
    user = masks.copy()
    user[60:64, 60:70, 0] = False
    evidence, aligned = score_masks(user, masks)
    components = compute_score_components(user, aligned)
    assert score_v1_current(components) == pytest.approx(
        evidence["prototype_structure_score"], abs=1e-12
    )


def test_both_empty_direction_channels_are_not_free_evidence_in_coverage_candidate() -> None:
    user, reference = _single_direction_pair()
    components = compute_score_components(user, reference)
    assert components.active_direction_count == 1
    assert components.direction_macro_all > components.direction_macro_active
    assert empty_direction_credit(components) > 0
    # The coverage-aware score should be substantially lower because four empty
    # direction channels and the absent keypoint channel no longer donate perfect credit.
    assert score_v1_coverage_corrected(components) < score_v1_current(components) - 20.0


def test_both_empty_keypoint_channel_is_missing_not_positive_evidence_for_candidates() -> None:
    user, reference = _single_direction_pair()
    components = compute_score_components(user, reference)
    assert components.keypoint_available is False
    assert components.keypoint_f1_radius_3 == 1.0
    assert keypoint_empty_credit_exposed(components) is True
    # With no keypoint evidence, the nonredundant candidate collapses to the
    # active direction score rather than receiving a 20-point free match.
    assert score_v2_nonredundant_candidate(components) == pytest.approx(
        100.0 * components.direction_macro_active
    )


def test_one_sided_keypoint_presence_is_real_mismatch_and_remains_available() -> None:
    user, reference = _single_direction_pair()
    reference[8:11, 8:11, 5] = True
    components = compute_score_components(user, reference)
    assert components.keypoint_available is True
    assert components.keypoint_f1_radius_3 == 0.0
    assert keypoint_empty_credit_exposed(components) is False


def test_keypoint_tolerance_profile_is_exported() -> None:
    reference = np.zeros((48, 48, 6), dtype=bool)
    user = np.zeros_like(reference)
    reference[20:24, 10:30, 0] = True
    user[..., 0] = reference[..., 0]
    reference[10:13, 10:13, 5] = True
    user[10:13, 13:16, 5] = True
    components = compute_score_components(user, reference)
    assert components.keypoint_f1_radius_0 < components.keypoint_f1_radius_3
    assert components.keypoint_f1_radius_3 <= components.keypoint_f1_radius_5
    assert components.user_keypoint_component_count == 1
    assert components.reference_keypoint_component_count == 1
    assert components.keypoint_component_center_f1_radius_3 == pytest.approx(1.0)


def test_component_center_f1_uses_one_to_one_matching() -> None:
    reference = np.zeros((48, 48, 6), dtype=bool)
    user = np.zeros_like(reference)
    reference[20:24, 10:30, 0] = True
    user[..., 0] = reference[..., 0]

    # Two separated reference keypoint components, both within a generous 5 px
    # radius of the single user component. One user point must not match twice.
    reference[10:12, 10:12, 5] = True
    reference[10:12, 16:18, 5] = True
    user[10:12, 13:15, 5] = True
    components = compute_score_components(user, reference)
    assert components.user_keypoint_component_count == 1
    assert components.reference_keypoint_component_count == 2
    # Maximum matching has one pair: P=1, R=1/2, F1=2/3.
    assert components.keypoint_component_center_f1_radius_5 == pytest.approx(2.0 / 3.0)


def test_source_reference_presence_prevents_alignment_clipping_from_becoming_free_credit() -> None:
    source = np.zeros((48, 48, 6), dtype=bool)
    aligned = np.zeros_like(source)
    user = np.zeros_like(source)
    # vec1 existed in the source reference but was lost by a hypothetical clipped alignment.
    source[8:12, 8:24, 0] = True
    # vec2 survives and matches, so the sample still has valid direction evidence.
    source[24:28, 10:30, 1] = True
    aligned[24:28, 10:30, 1] = True
    user[24:28, 10:30, 1] = True
    # Keypoint evidence also existed in the source but disappeared after alignment.
    source[6:9, 6:9, 5] = True

    components = compute_score_components(
        user,
        aligned,
        source_reference_masks=source,
    )
    assert components.direction_dice[0] == 1.0  # exact current empty-empty semantics
    assert components.direction_dice_coverage[0] == 0.0
    assert components.alignment_lost_direction_count == 1
    assert components.keypoint_available is True
    assert components.keypoint_f1_radius_3 == 1.0  # current semantics
    assert components.keypoint_f1_radius_3_coverage == 0.0
    assert components.alignment_lost_keypoint_evidence is True


def test_coverage_corrected_candidate_is_conservative_relative_to_v1() -> None:
    rng = np.random.default_rng(20260809)
    for _ in range(50):
        reference = np.zeros((32, 32, 6), dtype=bool)
        user = np.zeros_like(reference)
        # Ensure at least one direction channel exists, then randomly expose others.
        reference[8:16, 8:16, 0] = True
        user[8:16, 10:18, 0] = True
        for channel in range(1, 5):
            if rng.random() < 0.5:
                reference[4 + channel : 9 + channel, 4:14, channel] = True
            if rng.random() < 0.5:
                user[5 + channel : 10 + channel, 5:15, channel] = True
        if rng.random() < 0.5:
            reference[20:23, 20:23, 5] = True
        if rng.random() < 0.5:
            user[20:23, 21:24, 5] = True
        components = compute_score_components(user, reference, source_reference_masks=reference)
        assert score_v1_coverage_corrected(components) <= score_v1_current(components) + 1e-12
