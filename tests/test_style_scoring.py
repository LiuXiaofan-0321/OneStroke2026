from __future__ import annotations

import numpy as np

from onestroke_model.style_scoring import score_masks


def _masks(x0: int, y0: int) -> np.ndarray:
    masks = np.zeros((64, 64, 6), dtype=np.uint8)
    masks[y0 : y0 + 16, x0 : x0 + 8, :5] = 1
    masks[y0 + 7 : y0 + 9, x0 + 3 : x0 + 5, 5] = 1
    return masks


def test_restricted_alignment_improves_translated_same_structure() -> None:
    evidence, aligned = score_masks(_masks(30, 24), _masks(10, 8))

    assert aligned.shape == (64, 64, 6)
    assert evidence["selected_transform"]["translation_x"] > 0
    assert evidence["direction_macro_dice"] > 0.95
    assert evidence["prototype_structure_score"] > 95.0


def test_score_reports_pre_alignment_layout_difference() -> None:
    evidence, _ = score_masks(_masks(30, 24), _masks(10, 8))

    assert evidence["pre_alignment"]["center_distance_normalized"] > 0.1
    assert evidence["alignment_policy"]["deformable_warp"] is False
