from __future__ import annotations

import numpy as np
import pytest

from onestroke_model.spatial_structure_score import (
    SPATIAL_SCORE_WEIGHTS,
    compute_spatial_structure_components,
    jensen_shannon_similarity,
    spatial_structure_score,
)


def _masks() -> np.ndarray:
    masks = np.zeros((64, 64, 6), dtype=bool)
    masks[12:18, 10:52, 0] = True
    masks[12:52, 29:35, 1] = True
    masks[42:48, 15:30, 2] = True
    masks[42:48, 34:49, 3] = True
    masks[28:34, 28:36, 4] = True
    masks[28:31, 30:33, 5] = True
    return masks


def test_identical_masks_receive_perfect_spatial_score() -> None:
    masks = _masks()

    components = compute_spatial_structure_components(masks, masks)

    assert components.polar_js_similarity == pytest.approx(1.0)
    assert components.grid_js_similarity == pytest.approx(1.0)
    assert components.projection_js_similarity == pytest.approx(1.0)
    assert spatial_structure_score(components) == pytest.approx(100.0)


def test_local_structural_change_reduces_spatial_score() -> None:
    reference = _masks()
    changed = reference.copy()
    changed[42:48, 34:49, 3] = False
    changed[48:54, 42:57, 3] = True

    identical = spatial_structure_score(
        compute_spatial_structure_components(reference, reference)
    )
    perturbed = spatial_structure_score(
        compute_spatial_structure_components(changed, reference)
    )

    assert 0.0 <= perturbed < identical


def test_jensen_shannon_similarity_is_symmetric_and_bounded() -> None:
    first = np.asarray([1.0, 2.0, 7.0])
    second = np.asarray([7.0, 2.0, 1.0])

    forward = jensen_shannon_similarity(first, second)
    reverse = jensen_shannon_similarity(second, first)

    assert 0.0 <= forward <= 1.0
    assert forward == pytest.approx(reverse)
    assert jensen_shannon_similarity(first, first) == pytest.approx(1.0)


def test_spatial_weights_are_frozen_and_normalized() -> None:
    assert SPATIAL_SCORE_WEIGHTS == {
        "polar_js_similarity": 0.70,
        "grid_js_similarity": 0.15,
        "projection_js_similarity": 0.15,
    }
    assert sum(SPATIAL_SCORE_WEIGHTS.values()) == pytest.approx(1.0)
