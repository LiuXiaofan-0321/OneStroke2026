"""Interpretable spatial-distribution evidence for aligned calligraphy masks.

The frozen production score is retained unchanged.  This module defines a
development-stage scalar intended for independent confirmatory validation.
It compares the union ink of the five direction channels after the existing
constrained alignment and deliberately does not consume character identity or
human ratings at inference time.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

import numpy as np

from onestroke_model.constants import CHANNELS

SPATIAL_SCORE_VERSION = "spatial-structure-v1-development"
SPATIAL_SCORE_WEIGHTS = {
    "polar_js_similarity": 0.70,
    "grid_js_similarity": 0.15,
    "projection_js_similarity": 0.15,
}


@dataclass(frozen=True)
class SpatialStructureComponents:
    polar_js_similarity: float
    grid_js_similarity: float
    projection_js_similarity: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def _as_masks(value: np.ndarray) -> np.ndarray:
    masks = np.asarray(value, dtype=bool)
    if masks.ndim != 3 or masks.shape[-1] != len(CHANNELS):
        raise ValueError(f"expected [H,W,{len(CHANNELS)}] masks, got {masks.shape}")
    return masks


def _ink(masks: np.ndarray) -> np.ndarray:
    return np.any(_as_masks(masks)[..., :5], axis=-1)


def _normalize_distribution(values: np.ndarray) -> np.ndarray:
    distribution = np.asarray(values, dtype=np.float64).reshape(-1)
    if np.any(distribution < 0):
        raise ValueError("distributions cannot contain negative values")
    total = float(distribution.sum())
    if total <= 0:
        return np.full(distribution.shape, 1.0 / max(1, distribution.size))
    return distribution / total


def jensen_shannon_similarity(first: np.ndarray, second: np.ndarray) -> float:
    """Return ``1 - Jensen-Shannon distance`` in the closed interval [0, 1]."""

    p = _normalize_distribution(first)
    q = _normalize_distribution(second)
    if p.shape != q.shape:
        raise ValueError("Jensen-Shannon inputs must have the same shape")
    midpoint = 0.5 * (p + q)

    def kl_divergence(source: np.ndarray) -> float:
        active = source > 0
        return float(
            np.sum(source[active] * np.log2(source[active] / midpoint[active]))
        )

    divergence = 0.5 * kl_divergence(p) + 0.5 * kl_divergence(q)
    distance = float(np.sqrt(max(0.0, min(1.0, divergence))))
    return float(np.clip(1.0 - distance, 0.0, 1.0))


def polar_occupancy_signature(
    mask: np.ndarray,
    *,
    radial_bins: int = 4,
    angular_bins: int = 8,
    radius_quantile: float = 0.95,
) -> np.ndarray:
    """Describe relative ink placement in a centroid-normalized polar grid."""

    foreground = np.asarray(mask, dtype=bool)
    if foreground.ndim != 2:
        raise ValueError(f"expected a two-dimensional mask, got {foreground.shape}")
    if radial_bins <= 0 or angular_bins <= 0:
        raise ValueError("polar bin counts must be positive")
    if not 0 < radius_quantile <= 1:
        raise ValueError("radius_quantile must be in (0, 1]")

    ys, xs = np.nonzero(foreground)
    if len(xs) == 0:
        return np.full(radial_bins * angular_bins, 1.0 / (radial_bins * angular_bins))

    center_x = float(xs.mean())
    center_y = float(ys.mean())
    delta_x = xs.astype(np.float64) - center_x
    delta_y = ys.astype(np.float64) - center_y
    radii = np.hypot(delta_x, delta_y)
    radius_scale = max(float(np.quantile(radii, radius_quantile)), 1.0)
    normalized_radius = np.clip(radii / radius_scale, 0.0, 1.0 - 1e-12)
    normalized_angle = (np.arctan2(delta_y, delta_x) + np.pi) / (2.0 * np.pi)

    radial_index = np.minimum(
        radial_bins - 1,
        np.floor(normalized_radius * radial_bins).astype(np.int64),
    )
    angular_index = np.minimum(
        angular_bins - 1,
        np.floor(normalized_angle * angular_bins).astype(np.int64),
    )
    signature = np.zeros((radial_bins, angular_bins), dtype=np.float64)
    np.add.at(signature, (radial_index, angular_index), 1.0)
    return _normalize_distribution(signature)


def grid_occupancy_signature(mask: np.ndarray, *, grid_size: int = 3) -> np.ndarray:
    foreground = np.asarray(mask, dtype=bool)
    if foreground.ndim != 2:
        raise ValueError(f"expected a two-dimensional mask, got {foreground.shape}")
    if grid_size <= 0:
        raise ValueError("grid_size must be positive")

    height, width = foreground.shape
    values: list[float] = []
    for row in range(grid_size):
        y0 = round(row * height / grid_size)
        y1 = round((row + 1) * height / grid_size)
        for column in range(grid_size):
            x0 = round(column * width / grid_size)
            x1 = round((column + 1) * width / grid_size)
            values.append(float(foreground[y0:y1, x0:x1].sum()))
    return _normalize_distribution(np.asarray(values))


def projection_similarity(first: np.ndarray, second: np.ndarray) -> float:
    first_mask = np.asarray(first, dtype=bool)
    second_mask = np.asarray(second, dtype=bool)
    if first_mask.shape != second_mask.shape or first_mask.ndim != 2:
        raise ValueError("projection masks must be equally sized two-dimensional arrays")
    horizontal = jensen_shannon_similarity(
        first_mask.sum(axis=1),
        second_mask.sum(axis=1),
    )
    vertical = jensen_shannon_similarity(
        first_mask.sum(axis=0),
        second_mask.sum(axis=0),
    )
    return float(0.5 * (horizontal + vertical))


def compute_spatial_structure_components(
    user_masks: np.ndarray,
    aligned_reference_masks: np.ndarray,
) -> SpatialStructureComponents:
    user = _as_masks(user_masks)
    reference = _as_masks(aligned_reference_masks)
    if user.shape != reference.shape:
        raise ValueError("user and aligned reference masks must share a canvas")

    user_ink = _ink(user)
    reference_ink = _ink(reference)
    if not np.any(user_ink) or not np.any(reference_ink):
        raise ValueError("spatial structure score requires non-empty ink masks")

    polar = jensen_shannon_similarity(
        polar_occupancy_signature(user_ink),
        polar_occupancy_signature(reference_ink),
    )
    grid = jensen_shannon_similarity(
        grid_occupancy_signature(user_ink),
        grid_occupancy_signature(reference_ink),
    )
    projection = projection_similarity(user_ink, reference_ink)
    return SpatialStructureComponents(
        polar_js_similarity=polar,
        grid_js_similarity=grid,
        projection_js_similarity=projection,
    )


def spatial_structure_score(
    components: SpatialStructureComponents | Mapping[str, float],
    *,
    weights: Mapping[str, float] = SPATIAL_SCORE_WEIGHTS,
) -> float:
    values = (
        components.as_dict()
        if isinstance(components, SpatialStructureComponents)
        else dict(components)
    )
    missing = sorted(set(SPATIAL_SCORE_WEIGHTS) - set(values))
    if missing:
        raise ValueError(f"missing spatial score components: {missing}")
    weight_total = float(sum(float(weights[name]) for name in SPATIAL_SCORE_WEIGHTS))
    if not np.isclose(weight_total, 1.0, rtol=0.0, atol=1e-12):
        raise ValueError(f"spatial score weights must sum to 1, got {weight_total}")
    if any(float(weights[name]) < 0 for name in SPATIAL_SCORE_WEIGHTS):
        raise ValueError("spatial score weights must be non-negative")

    score = 100.0 * sum(
        float(weights[name]) * float(values[name]) for name in SPATIAL_SCORE_WEIGHTS
    )
    return float(np.clip(score, 0.0, 100.0))
