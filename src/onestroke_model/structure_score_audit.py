"""Auditing utilities and candidate aggregations for OneStroke structure scores.

This module is intentionally *not* the production scorer.  It decomposes the
existing score after the production-equivalent alignment step, quantifies
coverage/redundancy risks, and exposes preregistered candidate aggregations for
controlled comparison.

The current production score remains the reference baseline::

    100 * (0.55 * direction_macro_dice + 0.25 * ink_iou + 0.20 * keypoint_f1_r3)

Two candidates are provided for audit only:

``v1_coverage_corrected``
    Keep the original three evidence families and original weights, but test an
    active-evidence normalization in which direction channels that are empty on
    both sides are excluded from the direction macro and a both-empty keypoint
    channel is treated as unavailable. This is an audit candidate, not an
    assumption that semantic absence is always uninformative: if the annotation
    ontology defines absence itself as meaningful negative evidence, v1's
    empty-empty credit can be defensible.

``v2_nonredundant_candidate``
    In addition to the coverage correction, keep ink IoU as an alignment and
    diagnostic quantity rather than counting it again in the final scalar.
    The original direction:keypoint weight ratio (0.55:0.20) is preserved and
    renormalized over available evidence.  This is a research candidate, not a
    calibrated grade and not a production replacement.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from onestroke_model.constants import CHANNELS
from onestroke_model.style_scoring import _as_masks, _dice, _ink, _iou, _tolerant_f1

CURRENT_WEIGHTS: dict[str, float] = {
    "direction": 0.55,
    "ink": 0.25,
    "keypoint": 0.20,
}

SCORE_VARIANTS: tuple[str, ...] = (
    "v1_current",
    "v1_coverage_corrected",
    "v2_nonredundant_candidate",
)


@dataclass(frozen=True)
class ScoreComponents:
    """Atomic post-alignment evidence used by the score audit."""

    direction_dice: tuple[float, float, float, float, float]
    direction_dice_coverage: tuple[float, float, float, float, float]
    direction_active: tuple[bool, bool, bool, bool, bool]
    reference_direction_present: tuple[bool, bool, bool, bool, bool]
    aligned_reference_direction_present: tuple[bool, bool, bool, bool, bool]
    direction_macro_all: float
    direction_macro_active: float
    direction_min_active: float
    active_direction_count: int
    alignment_lost_direction_count: int
    ink_iou: float
    keypoint_f1_radius_0: float
    keypoint_f1_radius_1: float
    keypoint_f1_radius_3: float
    keypoint_f1_radius_5: float
    keypoint_component_center_f1_radius_3: float
    keypoint_component_center_f1_radius_5: float
    user_keypoint_component_count: int
    reference_keypoint_component_count: int
    keypoint_f1_radius_3_coverage: float
    keypoint_available: bool
    user_keypoint_pixels: int
    reference_keypoint_pixels: int
    source_reference_keypoint_pixels: int
    alignment_lost_keypoint_evidence: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["direction_dice"] = {
            CHANNELS[index]: float(value)
            for index, value in enumerate(self.direction_dice)
        }
        payload["direction_dice_coverage"] = {
            CHANNELS[index]: float(value)
            for index, value in enumerate(self.direction_dice_coverage)
        }
        payload["direction_active"] = {
            CHANNELS[index]: bool(value)
            for index, value in enumerate(self.direction_active)
        }
        payload["reference_direction_present"] = {
            CHANNELS[index]: bool(value)
            for index, value in enumerate(self.reference_direction_present)
        }
        payload["aligned_reference_direction_present"] = {
            CHANNELS[index]: bool(value)
            for index, value in enumerate(self.aligned_reference_direction_present)
        }
        return payload


def _connected_component_centers(mask: np.ndarray) -> tuple[tuple[float, float], ...]:
    """Return 8-connected component centroids as ``(x, y)`` points.

    Keypoints are delivered as small binary regions rather than one-hot pixels.
    This dependency-free helper lets the audit compare the current tolerant
    pixel-F1 against the component-center interpretation already used by
    downstream coordinate export.
    """

    value = np.asarray(mask, dtype=bool)
    if value.ndim != 2:
        raise ValueError(f"expected a 2D keypoint mask, got {value.shape}")
    seeds = np.argwhere(value)
    if len(seeds) == 0:
        return ()

    visited = np.zeros_like(value, dtype=bool)
    height, width = value.shape
    centers: list[tuple[float, float]] = []
    for seed_y, seed_x in seeds:
        y0, x0 = int(seed_y), int(seed_x)
        if visited[y0, x0]:
            continue
        stack = [(y0, x0)]
        visited[y0, x0] = True
        sum_x = 0.0
        sum_y = 0.0
        count = 0
        while stack:
            y, x = stack.pop()
            sum_x += x
            sum_y += y
            count += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if (
                        0 <= ny < height
                        and 0 <= nx < width
                        and value[ny, nx]
                        and not visited[ny, nx]
                    ):
                        visited[ny, nx] = True
                        stack.append((ny, nx))
        centers.append((sum_x / count, sum_y / count))
    return tuple(centers)


def _component_center_f1(
    prediction: np.ndarray,
    reference: np.ndarray,
    radius: float,
) -> tuple[float, int, int]:
    """Maximum-cardinality center matching within the production Chebyshev radius.

    Production tolerant pixel F1 dilates with a square `(2r+1)x(2r+1)` window,
    which corresponds to Chebyshev distance. Using the same geometry isolates
    the effect of comparing component centers rather than pixel regions.
    """

    if radius < 0:
        raise ValueError("component-center radius must be non-negative")
    predicted_centers = _connected_component_centers(prediction)
    reference_centers = _connected_component_centers(reference)
    n_pred = len(predicted_centers)
    n_ref = len(reference_centers)
    if n_pred == 0 and n_ref == 0:
        return 1.0, 0, 0
    if n_pred == 0 or n_ref == 0:
        return 0.0, n_pred, n_ref

    adjacency: list[list[int]] = []
    for pred_x, pred_y in predicted_centers:
        candidates = [
            index
            for index, (ref_x, ref_y) in enumerate(reference_centers)
            if max(abs(pred_x - ref_x), abs(pred_y - ref_y))
            <= float(radius) + 1e-12
        ]
        adjacency.append(candidates)

    # Standard augmenting-path bipartite matching. The number of calligraphy
    # keypoint components is small, so a dependency-free exact matching is
    # preferable to a greedy nearest-neighbor rule.
    matched_prediction_for_reference = [-1] * n_ref

    def augment(prediction_index: int, seen_reference: list[bool]) -> bool:
        for reference_index in adjacency[prediction_index]:
            if seen_reference[reference_index]:
                continue
            seen_reference[reference_index] = True
            previous = matched_prediction_for_reference[reference_index]
            if previous < 0 or augment(previous, seen_reference):
                matched_prediction_for_reference[reference_index] = prediction_index
                return True
        return False

    matched = 0
    for prediction_index in range(n_pred):
        if augment(prediction_index, [False] * n_ref):
            matched += 1

    precision = matched / n_pred
    recall = matched / n_ref
    f1 = 2.0 * precision * recall / max(1e-12, precision + recall)
    return float(f1), n_pred, n_ref


def compute_score_components(
    user_masks: np.ndarray,
    aligned_reference_masks: np.ndarray,
    source_reference_masks: np.ndarray | None = None,
) -> ScoreComponents:
    """Compute score evidence *after* the production alignment has been fixed.

    ``source_reference_masks`` should be the pre-alignment reference when it is
    available.  Coverage-aware candidates use source-reference presence so an
    alignment transform cannot accidentally turn a clipped-away reference
    channel into "both empty = perfect" evidence.  If omitted, the aligned
    reference is used as the source-presence proxy for backward-compatible unit
    use.
    """

    user = _as_masks(user_masks)
    reference = _as_masks(aligned_reference_masks)
    source_reference = (
        reference
        if source_reference_masks is None
        else _as_masks(source_reference_masks)
    )
    if user.shape != reference.shape or source_reference.shape != reference.shape:
        raise ValueError(
            "user, aligned reference, and source reference masks must share a canonical canvas"
        )

    direction_dice = tuple(
        float(_dice(user[..., index], reference[..., index])) for index in range(5)
    )
    source_present = tuple(bool(np.any(source_reference[..., index])) for index in range(5))
    aligned_present = tuple(bool(np.any(reference[..., index])) for index in range(5))
    user_present = tuple(bool(np.any(user[..., index])) for index in range(5))
    active = tuple(
        bool(source_present[index] or user_present[index]) for index in range(5)
    )
    coverage_dice_values: list[float] = []
    for index in range(5):
        value = direction_dice[index]
        if (
            source_present[index]
            and not aligned_present[index]
            and not user_present[index]
        ):
            # The source contained this semantic direction but the selected
            # alignment removed it from the canvas.  Do not convert that loss of
            # evidence into the production helper's empty-empty Dice=1.
            value = 0.0
        coverage_dice_values.append(float(value))
    direction_dice_coverage = tuple(coverage_dice_values)
    active_values = [
        direction_dice_coverage[index]
        for index, is_active in enumerate(active)
        if is_active
    ]
    if not active_values:
        raise ValueError("cannot audit structure score without any direction evidence")

    user_keypoint_pixels = int(user[..., 5].sum())
    reference_keypoint_pixels = int(reference[..., 5].sum())
    source_reference_keypoint_pixels = int(source_reference[..., 5].sum())
    keypoint_available = bool(user_keypoint_pixels or source_reference_keypoint_pixels)
    alignment_lost_keypoint = bool(
        source_reference_keypoint_pixels > 0
        and reference_keypoint_pixels == 0
        and user_keypoint_pixels == 0
    )
    keypoint_f1_r0 = float(_tolerant_f1(user[..., 5], reference[..., 5], radius=0))
    keypoint_f1_r1 = float(_tolerant_f1(user[..., 5], reference[..., 5], radius=1))
    keypoint_f1_r3 = float(_tolerant_f1(user[..., 5], reference[..., 5], radius=3))
    keypoint_f1_r5 = float(_tolerant_f1(user[..., 5], reference[..., 5], radius=5))
    keypoint_center_f1_r3, user_kp_components, reference_kp_components = (
        _component_center_f1(user[..., 5], reference[..., 5], radius=3.0)
    )
    keypoint_center_f1_r5, user_kp_components_r5, reference_kp_components_r5 = (
        _component_center_f1(user[..., 5], reference[..., 5], radius=5.0)
    )
    if (
        user_kp_components != user_kp_components_r5
        or reference_kp_components != reference_kp_components_r5
    ):
        raise RuntimeError("keypoint component counts changed across matching radii")
    keypoint_f1_r3_coverage = 0.0 if alignment_lost_keypoint else keypoint_f1_r3

    return ScoreComponents(
        direction_dice=direction_dice,  # type: ignore[arg-type]
        direction_dice_coverage=direction_dice_coverage,  # type: ignore[arg-type]
        direction_active=active,  # type: ignore[arg-type]
        reference_direction_present=source_present,  # type: ignore[arg-type]
        aligned_reference_direction_present=aligned_present,  # type: ignore[arg-type]
        direction_macro_all=float(np.mean(direction_dice)),
        direction_macro_active=float(np.mean(active_values)),
        direction_min_active=float(np.min(active_values)),
        active_direction_count=len(active_values),
        alignment_lost_direction_count=sum(
            1
            for index in range(5)
            if source_present[index] and not aligned_present[index]
        ),
        ink_iou=float(_iou(_ink(user), _ink(reference))),
        keypoint_f1_radius_0=keypoint_f1_r0,
        keypoint_f1_radius_1=keypoint_f1_r1,
        keypoint_f1_radius_3=keypoint_f1_r3,
        keypoint_f1_radius_5=keypoint_f1_r5,
        keypoint_component_center_f1_radius_3=float(keypoint_center_f1_r3),
        keypoint_component_center_f1_radius_5=float(keypoint_center_f1_r5),
        user_keypoint_component_count=int(user_kp_components),
        reference_keypoint_component_count=int(reference_kp_components),
        keypoint_f1_radius_3_coverage=float(keypoint_f1_r3_coverage),
        keypoint_available=keypoint_available,
        user_keypoint_pixels=user_keypoint_pixels,
        reference_keypoint_pixels=reference_keypoint_pixels,
        source_reference_keypoint_pixels=source_reference_keypoint_pixels,
        alignment_lost_keypoint_evidence=alignment_lost_keypoint,
    )


def _weighted_available_score(
    components: Mapping[str, tuple[float, float, bool]],
) -> float:
    numerator = 0.0
    denominator = 0.0
    for value, weight, available in components.values():
        if not available:
            continue
        numerator += float(value) * float(weight)
        denominator += float(weight)
    if denominator <= 0:
        raise ValueError("score has no available evidence")
    return float(100.0 * numerator / denominator)


def score_v1_current(components: ScoreComponents) -> float:
    """Recompute the exact current production scalar from atomic evidence."""

    return float(
        100.0
        * (
            CURRENT_WEIGHTS["direction"] * components.direction_macro_all
            + CURRENT_WEIGHTS["ink"] * components.ink_iou
            + CURRENT_WEIGHTS["keypoint"] * components.keypoint_f1_radius_3
        )
    )


def score_v1_coverage_corrected(components: ScoreComponents) -> float:
    """Active-evidence alternative using the original evidence families/weights.

    This candidate removes the dilution created by both-empty semantic channels,
    but it is not automatically "more correct": true absence can itself be
    meaningful agreement when the annotation ontology is exhaustive.
    """

    return _weighted_available_score(
        {
            "direction": (
                components.direction_macro_active,
                CURRENT_WEIGHTS["direction"],
                True,
            ),
            "ink": (components.ink_iou, CURRENT_WEIGHTS["ink"], True),
            "keypoint": (
                components.keypoint_f1_radius_3_coverage,
                CURRENT_WEIGHTS["keypoint"],
                components.keypoint_available,
            ),
        }
    )


def score_v2_nonredundant_candidate(components: ScoreComponents) -> float:
    """Coverage-aware candidate that does not count alignment ink IoU twice.

    The direction:keypoint prior ratio is inherited from v1 (0.55:0.20), not
    retuned on perturbation data.  Ink IoU remains an exported diagnostic and
    the alignment objective; it is simply omitted from this candidate scalar.
    """

    return _weighted_available_score(
        {
            "direction": (
                components.direction_macro_active,
                CURRENT_WEIGHTS["direction"],
                True,
            ),
            "keypoint": (
                components.keypoint_f1_radius_3_coverage,
                CURRENT_WEIGHTS["keypoint"],
                components.keypoint_available,
            ),
        }
    )


def score_variants(components: ScoreComponents) -> dict[str, float]:
    return {
        "v1_current": score_v1_current(components),
        "v1_coverage_corrected": score_v1_coverage_corrected(components),
        "v2_nonredundant_candidate": score_v2_nonredundant_candidate(components),
    }


def v1_weighted_contributions(components: ScoreComponents) -> dict[str, float]:
    """Return the current score's point contributions on the 0-100 scale."""

    return {
        "direction_points": float(100.0 * CURRENT_WEIGHTS["direction"] * components.direction_macro_all),
        "ink_points": float(100.0 * CURRENT_WEIGHTS["ink"] * components.ink_iou),
        "keypoint_points": float(100.0 * CURRENT_WEIGHTS["keypoint"] * components.keypoint_f1_radius_3),
    }


def empty_direction_credit(components: ScoreComponents) -> float:
    """Macro uplift caused by both-empty channels being counted as Dice=1."""

    return float(components.direction_macro_all - components.direction_macro_active)


def keypoint_empty_credit_exposed(components: ScoreComponents) -> bool:
    """Whether v1 treats a both-empty keypoint channel as perfect evidence."""

    return bool(
        not components.keypoint_available
        and abs(components.keypoint_f1_radius_3 - 1.0) <= 1e-12
    )


def component_vector(components: ScoreComponents) -> dict[str, float]:
    """Compact numeric vector used by correlation/sensitivity audits."""

    return {
        "direction_macro_all": components.direction_macro_all,
        "direction_macro_active": components.direction_macro_active,
        "direction_min_active": components.direction_min_active,
        "ink_iou": components.ink_iou,
        "keypoint_f1_r3": components.keypoint_f1_radius_3,
        "keypoint_center_f1_r3": components.keypoint_component_center_f1_radius_3,
    }


def validate_variant_name(name: str) -> str:
    if name not in SCORE_VARIANTS:
        raise ValueError(f"unknown score variant {name!r}; expected one of {SCORE_VARIANTS}")
    return name


def score_from_variant(name: str, components: ScoreComponents) -> float:
    validate_variant_name(name)
    return score_variants(components)[name]


def direction_channel_rows(components: ScoreComponents) -> Sequence[dict[str, Any]]:
    return [
        {
            "channel": CHANNELS[index],
            "dice": float(components.direction_dice[index]),
            "active": bool(components.direction_active[index]),
        }
        for index in range(5)
    ]
