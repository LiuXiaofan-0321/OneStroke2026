"""Controlled perturbations for auditing reference-conditioned structural scoring.

The benchmark operates in the canonical six-channel mask space.  This is
intentional: it isolates the deterministic scoring/alignment contract from the
segmentation model, so score behavior can be tested without perception noise.

All perturbations are deterministic.  Local structural perturbations select a
reference-specific direction channel using a stable hash rather than model
errors or manual cherry-picking.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

import numpy as np
from PIL import Image, ImageFilter

from onestroke_model.constants import CHANNELS, SCHEMA_VERSION
from onestroke_model.style_scoring import (
    _as_masks,
    _centroid,
    _dice,
    _ink,
    _iou,
    _scale_rotate,
    _tolerant_f1,
    _translate,
)

PerturbationFamily = Literal["baseline", "nuisance", "structural"]
ExpectedBehavior = Literal["identity", "invariant", "decreasing"]


@dataclass(frozen=True)
class PerturbationDefinition:
    """One deterministic perturbation family and its ordered severity levels."""

    name: str
    family: PerturbationFamily
    severities: tuple[float, ...]
    unit: str
    expected_behavior: ExpectedBehavior
    description: str


@dataclass(frozen=True)
class PerturbationOutcome:
    """Result of one synthetic perturbation before structural scoring."""

    masks: np.ndarray
    valid: bool
    metadata: dict[str, Any] = field(default_factory=dict)
    invalid_reason: str | None = None


@dataclass(frozen=True)
class _AlignmentCandidate:
    scale: float
    rotation_degrees: float
    center_x: float
    center_y: float
    ys: np.ndarray
    xs: np.ndarray


DEFAULT_PERTURBATIONS: tuple[PerturbationDefinition, ...] = (
    PerturbationDefinition(
        name="global_translation",
        family="nuisance",
        severities=(4.0, 8.0, 12.0, 16.0),
        unit="pixels",
        expected_behavior="invariant",
        description="Translate all six channels along a reference-specific safe axis.",
    ),
    PerturbationDefinition(
        name="global_rotation",
        family="nuisance",
        severities=(0.5, 1.5, 2.5),
        unit="degrees",
        expected_behavior="invariant",
        description=(
            "Rotate all six channels at off-grid angles within the scorer's permitted "
            "±3 degree range."
        ),
    ),
    PerturbationDefinition(
        name="global_scale_up",
        family="nuisance",
        severities=(0.025, 0.075, 0.125, 0.175),
        unit="fraction",
        expected_behavior="invariant",
        description=(
            "Isotropically enlarge all channels at off-grid values within the permitted "
            "0.80–1.20 range."
        ),
    ),
    PerturbationDefinition(
        name="global_scale_down",
        family="nuisance",
        severities=(0.025, 0.075, 0.125, 0.175),
        unit="fraction",
        expected_behavior="invariant",
        description=(
            "Isotropically shrink all channels at off-grid values within the permitted "
            "0.80–1.20 range."
        ),
    ),
    PerturbationDefinition(
        name="compound_allowed_transform",
        family="nuisance",
        severities=(1.0, 2.0, 3.0),
        unit="level",
        expected_behavior="invariant",
        description="Combine allowed scale, rotation and translation at increasing levels.",
    ),
    PerturbationDefinition(
        name="direction_terminal_deletion",
        family="structural",
        severities=(0.05, 0.10, 0.20, 0.30),
        unit="target_channel_fraction",
        expected_behavior="decreasing",
        description="Delete a nested terminal fraction from one deterministic direction channel.",
    ),
    PerturbationDefinition(
        name="extra_direction_fragment",
        family="structural",
        severities=(0.05, 0.10, 0.20, 0.30),
        unit="target_channel_fraction",
        expected_behavior="decreasing",
        description="Add an offset duplicate of a terminal direction fragment.",
    ),
    PerturbationDefinition(
        name="local_fragment_shift",
        family="structural",
        severities=(4.0, 8.0, 12.0, 16.0),
        unit="pixels",
        expected_behavior="decreasing",
        description="Move a fixed terminal fragment perpendicular to its dominant axis.",
    ),
    PerturbationDefinition(
        name="direction_width_dilate",
        family="structural",
        severities=(1.0, 2.0, 4.0, 6.0),
        unit="pixels_radius",
        expected_behavior="decreasing",
        description="Progressively thicken one deterministic direction channel.",
    ),
    PerturbationDefinition(
        name="direction_width_erode",
        family="structural",
        severities=(1.0, 2.0, 3.0, 4.0),
        unit="pixels_radius",
        expected_behavior="decreasing",
        description="Progressively thin one deterministic direction channel.",
    ),
    PerturbationDefinition(
        name="keypoint_shift",
        family="structural",
        severities=(2.0, 4.0, 8.0, 12.0),
        unit="pixels",
        expected_behavior="decreasing",
        description=(
            "Translate only the keypoint channel; the 3 px tolerance should create "
            "a small-error plateau."
        ),
    ),
)


def perturbation_definitions() -> dict[str, PerturbationDefinition]:
    return {item.name: item for item in DEFAULT_PERTURBATIONS}


def _stable_int(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def _foreground_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _stack_transform(
    masks: np.ndarray, scale: float = 1.0, rotation_degrees: float = 0.0
) -> np.ndarray:
    masks = _as_masks(masks)
    return np.stack(
        [
            _scale_rotate(masks[..., channel], float(scale), float(rotation_degrees))
            for channel in range(len(CHANNELS))
        ],
        axis=-1,
    )


def _stack_translate(masks: np.ndarray, dx: int, dy: int) -> np.ndarray:
    masks = _as_masks(masks)
    return np.stack(
        [_translate(masks[..., channel], int(dx), int(dy)) for channel in range(len(CHANNELS))],
        axis=-1,
    )


def _safe_axis_shift(mask: np.ndarray, amount: int, key: str) -> tuple[int, int]:
    """Choose a stable axis/sign with enough foreground margin when possible."""
    bbox = _foreground_bbox(mask)
    if bbox is None:
        return 0, 0
    x0, y0, x1, y1 = bbox
    height, width = mask.shape
    options = [
        (width - 1 - x1, amount, 0, "right"),
        (x0, -amount, 0, "left"),
        (height - 1 - y1, 0, amount, "down"),
        (y0, 0, -amount, "up"),
    ]
    # First maximize available margin.  Stable hash only resolves exact ties.
    best_margin = max(item[0] for item in options)
    tied = [item for item in options if item[0] == best_margin]
    chosen = tied[_stable_int(key) % len(tied)]
    return int(chosen[1]), int(chosen[2])


def _translate_without_loss(masks: np.ndarray, dx: int, dy: int) -> tuple[np.ndarray, bool, int]:
    before = int(np.any(masks, axis=-1).sum())
    translated = _stack_translate(masks, dx, dy)
    after = int(np.any(translated, axis=-1).sum())
    return translated, after == before, before - after


def _global_transform_bbox_clipping_risk(
    masks: np.ndarray,
    scale: float = 1.0,
    rotation_degrees: float = 0.0,
) -> tuple[bool, dict[str, float]]:
    """Conservatively flag global transforms whose foreground bbox may leave canvas.

    Nearest-neighbor rotation/scaling can change foreground pixel counts even without
    clipping, so count preservation is not a reliable clipping test.  Instead we
    transform the half-pixel-expanded foreground bounding box in continuous canvas
    coordinates.  The check is intentionally conservative: ambiguous edge cases are
    retained as invalid rows rather than contaminating a nuisance-invariance estimate
    with crop loss.
    """
    masks = _as_masks(masks)
    foreground = np.any(masks, axis=-1)
    bbox = _foreground_bbox(foreground)
    if bbox is None:
        return True, {"reason_code": "empty_foreground"}
    x0, y0, x1, y1 = bbox
    height, width = foreground.shape
    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    # Expand by half a pixel so the transformed support, not only pixel centers,
    # must remain inside the canonical canvas.
    corners = np.asarray(
        [
            [x0 - 0.5, y0 - 0.5],
            [x0 - 0.5, y1 + 0.5],
            [x1 + 0.5, y0 - 0.5],
            [x1 + 0.5, y1 + 0.5],
        ],
        dtype=np.float64,
    )
    centered = corners - np.asarray([center_x, center_y], dtype=np.float64)
    theta = math.radians(float(rotation_degrees))
    cosine, sine = math.cos(theta), math.sin(theta)
    rotation = np.asarray([[cosine, -sine], [sine, cosine]], dtype=np.float64)
    transformed = (centered * float(scale)) @ rotation.T
    transformed += np.asarray([center_x, center_y], dtype=np.float64)
    min_x, min_y = transformed.min(axis=0)
    max_x, max_y = transformed.max(axis=0)
    risk = bool(min_x < -0.5 or min_y < -0.5 or max_x > width - 0.5 or max_y > height - 0.5)
    return risk, {
        "bbox_transformed_min_x": float(min_x),
        "bbox_transformed_min_y": float(min_y),
        "bbox_transformed_max_x": float(max_x),
        "bbox_transformed_max_y": float(max_y),
        "canvas_width": float(width),
        "canvas_height": float(height),
    }


def _binary_filter(mask: np.ndarray, radius: int, mode: Literal["dilate", "erode"]) -> np.ndarray:
    if radius <= 0:
        return np.asarray(mask, dtype=bool).copy()
    size = 2 * int(radius) + 1
    image = Image.fromarray(np.asarray(mask, dtype=np.uint8) * 255, mode="L")
    if mode == "dilate":
        filtered = image.filter(ImageFilter.MaxFilter(size=size))
    else:
        filtered = image.filter(ImageFilter.MinFilter(size=size))
    return np.asarray(filtered, dtype=np.uint8) > 0


def _eligible_direction_channels(masks: np.ndarray, min_pixels: int = 64) -> list[int]:
    counts = [int(masks[..., index].sum()) for index in range(5)]
    eligible = [index for index, count in enumerate(counts) if count >= min_pixels]
    if eligible:
        return eligible
    nonempty = [index for index, count in enumerate(counts) if count > 0]
    return nonempty


def select_target_direction_channel(
    masks: np.ndarray, reference_id: str, min_pixels: int = 64
) -> int | None:
    """Choose an eligible direction channel without consulting score/model errors."""
    masks = _as_masks(masks)
    eligible = _eligible_direction_channels(masks, min_pixels=min_pixels)
    if not eligible:
        return None
    return eligible[_stable_int(f"{reference_id}:direction-channel") % len(eligible)]


def _terminal_order(
    mask: np.ndarray, reference_id: str, channel_index: int
) -> tuple[np.ndarray, np.ndarray, str, str]:
    """Order foreground pixels from one deterministic geometric terminal inward."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return ys, xs, "x", "high"
    var_x = float(np.var(xs))
    var_y = float(np.var(ys))
    axis = "x" if var_x >= var_y else "y"
    side = "high" if (_stable_int(f"{reference_id}:{channel_index}:terminal-side") % 2) else "low"
    primary = xs if axis == "x" else ys
    secondary = ys if axis == "x" else xs
    order = np.lexsort((secondary, primary))
    if side == "high":
        order = order[::-1]
    return ys[order], xs[order], axis, side


def _terminal_fragment(
    mask: np.ndarray,
    fraction: float,
    reference_id: str,
    channel_index: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    ys, xs, axis, side = _terminal_order(mask, reference_id, channel_index)
    count = len(xs)
    if count == 0:
        return np.zeros_like(mask, dtype=bool), {"axis": axis, "side": side, "pixels": 0}
    take = max(1, min(count, int(math.ceil(count * float(fraction)))))
    fragment = np.zeros_like(mask, dtype=bool)
    fragment[ys[:take], xs[:take]] = True
    return fragment, {"axis": axis, "side": side, "pixels": int(take)}


def _remove_nearby_keypoints(
    masks: np.ndarray, affected: np.ndarray, radius: int = 3
) -> tuple[np.ndarray, int]:
    output = masks.copy()
    zone = _binary_filter(affected, radius=radius, mode="dilate")
    removed = np.logical_and(output[..., 5], zone)
    output[..., 5][removed] = False
    return output, int(removed.sum())


def _shift_fragment_axis(
    fragment: np.ndarray,
    reference_id: str,
    channel_index: int,
    dominant_axis: str,
    amount: int,
    remaining: np.ndarray | None = None,
) -> tuple[int, int, dict[str, Any]]:
    """Pick one fixed perpendicular direction that minimizes clipping/overlap."""
    amount = abs(int(amount))
    if amount == 0:
        return 0, 0, {"shift_axis": "none", "shift_sign": 0}
    if dominant_axis == "x":
        candidates = [(0, amount), (0, -amount)]
        shift_axis = "y"
    else:
        candidates = [(amount, 0), (-amount, 0)]
        shift_axis = "x"
    scored: list[tuple[int, int, int, int]] = []
    for dx, dy in candidates:
        shifted = _translate(fragment, dx, dy)
        kept = int(shifted.sum())
        overlap = int(np.logical_and(shifted, remaining).sum()) if remaining is not None else 0
        # maximize kept pixels, then minimize overlap. Stable hash resolves a remaining tie.
        scored.append((kept, -overlap, dx, dy))
    best_primary = max((item[0], item[1]) for item in scored)
    tied = [item for item in scored if (item[0], item[1]) == best_primary]
    chosen = tied[_stable_int(f"{reference_id}:{channel_index}:fragment-shift") % len(tied)]
    _, negative_overlap, dx, dy = chosen
    return int(dx), int(dy), {
        "shift_axis": shift_axis,
        "shift_sign": 1 if (dx > 0 or dy > 0) else -1,
        "predicted_overlap_pixels": int(-negative_overlap),
    }


def _apply_global_translation(
    masks: np.ndarray, reference_id: str, severity: float
) -> PerturbationOutcome:
    amount = int(round(severity))
    all_foreground = np.any(masks, axis=-1)
    dx, dy = _safe_axis_shift(all_foreground, amount, f"{reference_id}:global-translation")
    transformed, lossless, lost = _translate_without_loss(masks, dx, dy)
    return PerturbationOutcome(
        masks=transformed,
        valid=lossless,
        metadata={"translation_x": dx, "translation_y": dy, "lost_foreground_pixels": lost},
        invalid_reason=(
            None
            if lossless
            else "global translation clipped foreground at canvas boundary"
        ),
    )


def _apply_global_rotation(
    masks: np.ndarray, reference_id: str, severity: float
) -> PerturbationOutcome:
    sign = 1.0 if (_stable_int(f"{reference_id}:rotation-sign") % 2) else -1.0
    angle = sign * float(severity)
    clipping_risk, clipping_meta = _global_transform_bbox_clipping_risk(
        masks, rotation_degrees=angle
    )
    if clipping_risk:
        return PerturbationOutcome(
            masks=masks.copy(),
            valid=False,
            metadata={
                "rotation_degrees": angle,
                "clipping_precheck": clipping_meta,
            },
            invalid_reason="rotation clipping risk from conservative foreground-bbox precheck",
        )
    transformed = _stack_transform(masks, rotation_degrees=angle)
    valid = bool(np.any(transformed[..., :5]))
    return PerturbationOutcome(
        masks=transformed,
        valid=valid,
        metadata={
            "rotation_degrees": angle,
            "clipping_precheck": clipping_meta,
        },
        invalid_reason=None if valid else "rotation removed all direction ink",
    )


def _apply_global_scale(
    masks: np.ndarray, severity: float, direction: Literal["up", "down"]
) -> PerturbationOutcome:
    scale = 1.0 + float(severity) if direction == "up" else 1.0 - float(severity)
    clipping_risk, clipping_meta = _global_transform_bbox_clipping_risk(masks, scale=scale)
    if clipping_risk:
        return PerturbationOutcome(
            masks=masks.copy(),
            valid=False,
            metadata={
                "scale": float(scale),
                "clipping_precheck": clipping_meta,
            },
            invalid_reason="scale clipping risk from conservative foreground-bbox precheck",
        )
    transformed = _stack_transform(masks, scale=scale)
    valid = bool(np.any(transformed[..., :5]))
    return PerturbationOutcome(
        masks=transformed,
        valid=valid,
        metadata={
            "scale": float(scale),
            "clipping_precheck": clipping_meta,
        },
        invalid_reason=None if valid else "scale transform removed all direction ink",
    )


def _apply_compound_allowed(
    masks: np.ndarray, reference_id: str, severity: float
) -> PerturbationOutcome:
    level = int(round(severity))
    scale = 1.0 + (0.0375 + 0.05 * (level - 1))
    sign = 1.0 if (_stable_int(f"{reference_id}:compound-rotation-sign") % 2) else -1.0
    angle = sign * (0.75 + float(level - 1))
    clipping_risk, clipping_meta = _global_transform_bbox_clipping_risk(
        masks, scale=scale, rotation_degrees=angle
    )
    if clipping_risk:
        return PerturbationOutcome(
            masks=masks.copy(),
            valid=False,
            metadata={
                "scale": float(scale),
                "rotation_degrees": float(angle),
                "clipping_precheck": clipping_meta,
            },
            invalid_reason=(
                "compound transform clipping risk from conservative foreground-bbox precheck"
            ),
        )
    transformed = _stack_transform(masks, scale=scale, rotation_degrees=angle)
    amount = 5 * level
    dx, dy = _safe_axis_shift(
        np.any(transformed, axis=-1), amount, f"{reference_id}:compound-translation"
    )
    translated, lossless, lost = _translate_without_loss(transformed, dx, dy)
    valid = lossless and bool(np.any(translated[..., :5]))
    return PerturbationOutcome(
        masks=translated,
        valid=valid,
        metadata={
            "scale": float(scale),
            "rotation_degrees": float(angle),
            "translation_x": int(dx),
            "translation_y": int(dy),
            "lost_foreground_pixels": int(lost),
            "clipping_precheck": clipping_meta,
        },
        invalid_reason=(
            None
            if valid
            else "compound allowed transform clipped or removed direction ink"
        ),
    )


def _require_target_channel(masks: np.ndarray, reference_id: str) -> tuple[int | None, str | None]:
    target = select_target_direction_channel(masks, reference_id)
    if target is None:
        return None, "reference has no non-empty direction channel"
    return target, None


def _apply_terminal_deletion(
    masks: np.ndarray, reference_id: str, severity: float
) -> PerturbationOutcome:
    target, reason = _require_target_channel(masks, reference_id)
    if target is None:
        return PerturbationOutcome(masks=masks.copy(), valid=False, invalid_reason=reason)
    fragment, fragment_meta = _terminal_fragment(masks[..., target], severity, reference_id, target)
    output = masks.copy()
    output[..., target][fragment] = False
    output, removed_keypoints = _remove_nearby_keypoints(output, fragment)
    valid = bool(output[..., target].any())
    metadata = {
        "target_channel": CHANNELS[target],
        "requested_fraction": float(severity),
        "removed_direction_pixels": int(fragment.sum()),
        "removed_keypoint_pixels": removed_keypoints,
        **fragment_meta,
    }
    return PerturbationOutcome(
        masks=output,
        valid=valid,
        metadata=metadata,
        invalid_reason=(
            None
            if valid
            else "terminal deletion emptied the selected direction channel"
        ),
    )


def _apply_extra_fragment(
    masks: np.ndarray, reference_id: str, severity: float
) -> PerturbationOutcome:
    target, reason = _require_target_channel(masks, reference_id)
    if target is None:
        return PerturbationOutcome(masks=masks.copy(), valid=False, invalid_reason=reason)
    fragment, fragment_meta = _terminal_fragment(masks[..., target], severity, reference_id, target)
    remaining = masks[..., target]
    # Use one fixed offset direction for the whole nested severity curve.  It is
    # chosen from the maximum fragment so larger severities are true supersets.
    max_fraction = max(
        item.severities[-1]
        for item in DEFAULT_PERTURBATIONS
        if item.name == "extra_direction_fragment"
    )
    max_fragment, max_fragment_meta = _terminal_fragment(
        masks[..., target], max_fraction, reference_id, target
    )
    max_offset = max(8, int(round(min(masks.shape[:2]) * 0.03)))
    max_dx, max_dy, shift_meta = _shift_fragment_axis(
        max_fragment,
        reference_id,
        target,
        str(max_fragment_meta["axis"]),
        max_offset,
        remaining=remaining,
    )
    dx = max_offset if max_dx > 0 else (-max_offset if max_dx < 0 else 0)
    dy = max_offset if max_dy > 0 else (-max_offset if max_dy < 0 else 0)
    shifted = _translate(fragment, dx, dy)
    if int(shifted.sum()) != int(fragment.sum()):
        return PerturbationOutcome(
            masks=masks.copy(),
            valid=False,
            metadata={"target_channel": CHANNELS[target], **fragment_meta, **shift_meta},
            invalid_reason="extra fragment would be clipped at canvas boundary",
        )
    output = masks.copy()
    before = int(output[..., target].sum())
    output[..., target] |= shifted
    added = int(output[..., target].sum()) - before
    valid = added > 0
    metadata = {
        "target_channel": CHANNELS[target],
        "requested_fraction": float(severity),
        "source_fragment_pixels": int(fragment.sum()),
        "added_direction_pixels": added,
        "translation_x": int(dx),
        "translation_y": int(dy),
        **fragment_meta,
        **shift_meta,
    }
    return PerturbationOutcome(
        masks=output,
        valid=valid,
        metadata=metadata,
        invalid_reason=(
            None
            if valid
            else "shifted extra fragment fully overlapped existing structure"
        ),
    )


def _apply_local_fragment_shift(
    masks: np.ndarray, reference_id: str, severity: float
) -> PerturbationOutcome:
    target, reason = _require_target_channel(masks, reference_id)
    if target is None:
        return PerturbationOutcome(masks=masks.copy(), valid=False, invalid_reason=reason)
    fragment_fraction = 0.20
    fragment, fragment_meta = _terminal_fragment(
        masks[..., target], fragment_fraction, reference_id, target
    )
    remaining = np.logical_and(masks[..., target], ~fragment)
    # Choose the direction using the largest suite displacement so all severities move consistently.
    max_amount = int(
        max(
            item.severities[-1]
            for item in DEFAULT_PERTURBATIONS
            if item.name == "local_fragment_shift"
        )
    )
    max_dx, max_dy, shift_meta = _shift_fragment_axis(
        fragment,
        reference_id,
        target,
        str(fragment_meta["axis"]),
        max_amount,
        remaining=remaining,
    )
    amount = int(round(severity))
    if max_dx:
        dx, dy = (amount if max_dx > 0 else -amount), 0
    else:
        dx, dy = 0, (amount if max_dy > 0 else -amount)
    shifted = _translate(fragment, dx, dy)
    if int(shifted.sum()) != int(fragment.sum()):
        return PerturbationOutcome(
            masks=masks.copy(),
            valid=False,
            metadata={"target_channel": CHANNELS[target], **fragment_meta, **shift_meta},
            invalid_reason="local fragment shift would be clipped at canvas boundary",
        )
    output = masks.copy()
    output[..., target][fragment] = False
    output[..., target] |= shifted

    # Move keypoints spatially associated with the fragment as part of the local structural change.
    association_zone = _binary_filter(fragment, radius=3, mode="dilate")
    associated_keypoints = np.logical_and(output[..., 5], association_zone)
    output[..., 5][associated_keypoints] = False
    shifted_keypoints = _translate(associated_keypoints, dx, dy)
    output[..., 5] |= shifted_keypoints

    metadata = {
        "target_channel": CHANNELS[target],
        "fragment_fraction": fragment_fraction,
        "fragment_pixels": int(fragment.sum()),
        "associated_keypoint_pixels": int(associated_keypoints.sum()),
        "translation_x": int(dx),
        "translation_y": int(dy),
        **fragment_meta,
        **shift_meta,
    }
    return PerturbationOutcome(masks=output, valid=True, metadata=metadata)


def _apply_width_change(
    masks: np.ndarray,
    reference_id: str,
    severity: float,
    mode: Literal["dilate", "erode"],
) -> PerturbationOutcome:
    target, reason = _require_target_channel(masks, reference_id)
    if target is None:
        return PerturbationOutcome(masks=masks.copy(), valid=False, invalid_reason=reason)
    radius = int(round(severity))
    output = masks.copy()
    before = int(output[..., target].sum())
    changed = _binary_filter(output[..., target], radius=radius, mode=mode)
    after = int(changed.sum())
    output[..., target] = changed
    valid = after != before and bool(np.any(output[..., :5]))
    return PerturbationOutcome(
        masks=output,
        valid=valid,
        metadata={
            "target_channel": CHANNELS[target],
            "radius": radius,
            "mode": mode,
            "direction_pixels_before": before,
            "direction_pixels_after": after,
        },
        invalid_reason=(
            None
            if valid
            else f"{mode} did not produce a valid direction-structure change"
        ),
    )


def _apply_keypoint_shift(
    masks: np.ndarray, reference_id: str, severity: float
) -> PerturbationOutcome:
    keypoints = masks[..., 5]
    if not np.any(keypoints):
        return PerturbationOutcome(
            masks=masks.copy(),
            valid=False,
            invalid_reason="reference has an empty keypoint channel",
        )
    amount = int(round(severity))
    dx, dy = _safe_axis_shift(keypoints, amount, f"{reference_id}:keypoint-shift")
    shifted = _translate(keypoints, dx, dy)
    if int(shifted.sum()) != int(keypoints.sum()):
        return PerturbationOutcome(
            masks=masks.copy(),
            valid=False,
            metadata={"translation_x": dx, "translation_y": dy},
            invalid_reason="keypoint shift would be clipped at canvas boundary",
        )
    output = masks.copy()
    output[..., 5] = shifted
    return PerturbationOutcome(
        masks=output,
        valid=True,
        metadata={
            "translation_x": dx,
            "translation_y": dy,
            "keypoint_pixels": int(keypoints.sum()),
        },
    )


def apply_perturbation(
    masks: np.ndarray,
    reference_id: str,
    perturbation_name: str,
    severity: float,
) -> PerturbationOutcome:
    """Apply one named deterministic perturbation to canonical six-channel masks."""
    masks = _as_masks(masks)
    if perturbation_name == "global_translation":
        return _apply_global_translation(masks, reference_id, severity)
    if perturbation_name == "global_rotation":
        return _apply_global_rotation(masks, reference_id, severity)
    if perturbation_name == "global_scale_up":
        return _apply_global_scale(masks, severity, "up")
    if perturbation_name == "global_scale_down":
        return _apply_global_scale(masks, severity, "down")
    if perturbation_name == "compound_allowed_transform":
        return _apply_compound_allowed(masks, reference_id, severity)
    if perturbation_name == "direction_terminal_deletion":
        return _apply_terminal_deletion(masks, reference_id, severity)
    if perturbation_name == "extra_direction_fragment":
        return _apply_extra_fragment(masks, reference_id, severity)
    if perturbation_name == "local_fragment_shift":
        return _apply_local_fragment_shift(masks, reference_id, severity)
    if perturbation_name == "direction_width_dilate":
        return _apply_width_change(masks, reference_id, severity, "dilate")
    if perturbation_name == "direction_width_erode":
        return _apply_width_change(masks, reference_id, severity, "erode")
    if perturbation_name == "keypoint_shift":
        return _apply_keypoint_shift(masks, reference_id, severity)
    raise ValueError(f"unknown perturbation: {perturbation_name!r}")


class PreparedReferenceScorer:
    """Fast scorer with production-equivalent alignment search for one reference.

    Production ``score_masks`` recomputes 63 scale/rotation candidates on every
    call.  A perturbation benchmark scores many users against the same reference,
    so this class precomputes only the transformed *direction ink* candidates.
    The same scale/rotation grid, centroid translation, IoU objective and
    first-win tie behavior are preserved.  Unit tests compare this path directly
    with production ``score_masks`` to guard semantic drift.
    """

    def __init__(
        self,
        reference_masks: np.ndarray,
        min_scale: float = 0.80,
        max_scale: float = 1.20,
        max_rotation_degrees: float = 3.0,
    ) -> None:
        self.reference_masks = _as_masks(reference_masks).copy()
        if not np.any(_ink(self.reference_masks)):
            raise ValueError("cannot prepare an empty reference ink mask")
        self.min_scale = float(min_scale)
        self.max_scale = float(max_scale)
        self.max_rotation_degrees = float(max_rotation_degrees)
        self._candidates: list[_AlignmentCandidate] = []
        self._full_transform_cache: dict[int, np.ndarray] = {}
        reference_ink = _ink(self.reference_masks)
        for scale in np.linspace(self.min_scale, self.max_scale, 9):
            for rotation in np.linspace(-self.max_rotation_degrees, self.max_rotation_degrees, 7):
                transformed_ink = _scale_rotate(reference_ink, float(scale), float(rotation))
                ys, xs = np.nonzero(transformed_ink)
                if len(xs) == 0:
                    # This should not happen for realistic masks and the allowed scale range.
                    continue
                self._candidates.append(
                    _AlignmentCandidate(
                        scale=float(scale),
                        rotation_degrees=float(rotation),
                        center_x=float(xs.mean()),
                        center_y=float(ys.mean()),
                        ys=ys.astype(np.int32, copy=False),
                        xs=xs.astype(np.int32, copy=False),
                    )
                )
        if not self._candidates:
            raise ValueError("no valid alignment candidates could be prepared")

    @staticmethod
    def _candidate_iou(
        user_ink: np.ndarray,
        user_sum: int,
        candidate: _AlignmentCandidate,
        dx: int,
        dy: int,
    ) -> float:
        height, width = user_ink.shape
        xs = candidate.xs + int(dx)
        ys = candidate.ys + int(dy)
        valid = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
        if not np.any(valid):
            return 0.0
        valid_xs = xs[valid]
        valid_ys = ys[valid]
        shifted_sum = int(valid_xs.size)
        intersection = int(np.count_nonzero(user_ink[valid_ys, valid_xs]))
        union = user_sum + shifted_sum - intersection
        return 1.0 if union == 0 else float(intersection / union)

    def _full_transformed(self, candidate_index: int) -> np.ndarray:
        if candidate_index not in self._full_transform_cache:
            candidate = self._candidates[candidate_index]
            self._full_transform_cache[candidate_index] = _stack_transform(
                self.reference_masks,
                scale=candidate.scale,
                rotation_degrees=candidate.rotation_degrees,
            )
        return self._full_transform_cache[candidate_index]

    def align(self, user_masks: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
        user_masks = _as_masks(user_masks)
        if user_masks.shape != self.reference_masks.shape:
            raise ValueError("user and reference masks must share a canonical canvas")
        user_ink = _ink(user_masks)
        user_center = _centroid(user_ink)
        user_sum = int(user_ink.sum())
        best_iou = -1.0
        best_index = -1
        best_dx = 0
        best_dy = 0
        for index, candidate in enumerate(self._candidates):
            dx = int(round(user_center[0] - candidate.center_x))
            dy = int(round(user_center[1] - candidate.center_y))
            candidate_iou = self._candidate_iou(user_ink, user_sum, candidate, dx, dy)
            if candidate_iou > best_iou:
                best_iou = candidate_iou
                best_index = index
                best_dx = dx
                best_dy = dy
        if best_index < 0:
            raise RuntimeError("alignment search did not select a candidate")
        candidate = self._candidates[best_index]
        transformed = self._full_transformed(best_index)
        aligned = _stack_translate(transformed, best_dx, best_dy)
        return aligned, {
            "scale": float(candidate.scale),
            "rotation_degrees": float(candidate.rotation_degrees),
            "translation_x": float(best_dx),
            "translation_y": float(best_dy),
            "alignment_ink_iou": float(best_iou),
        }

    def score(self, user_masks: np.ndarray) -> tuple[dict[str, Any], np.ndarray]:
        user_masks = _as_masks(user_masks)
        if user_masks.shape != self.reference_masks.shape:
            raise ValueError("user and reference masks must share a canonical canvas")
        user_ink = _ink(user_masks)
        reference_ink = _ink(self.reference_masks)
        user_center, reference_center = _centroid(user_ink), _centroid(reference_ink)
        height, width = user_ink.shape
        diagonal = float(np.hypot(height, width))
        raw_center_distance = float(
            np.hypot(user_center[0] - reference_center[0], user_center[1] - reference_center[1])
        )
        center_offset_x = float(user_center[0] - reference_center[0])
        center_offset_y = float(user_center[1] - reference_center[1])
        raw_area_ratio = float(reference_ink.sum() / max(1, user_ink.sum()))
        aligned_reference, transform = self.align(user_masks)
        direction_dice = [
            _dice(user_masks[..., index], aligned_reference[..., index]) for index in range(5)
        ]
        aligned_ink = _ink(aligned_reference)
        keypoint_f1 = _tolerant_f1(user_masks[..., 5], aligned_reference[..., 5], radius=3)
        ink_iou = _iou(user_ink, aligned_ink)
        direction_mean = float(np.mean(direction_dice))
        prototype_score = 100.0 * (
            0.55 * direction_mean + 0.25 * ink_iou + 0.20 * keypoint_f1
        )
        evidence = {
            "schema_version": SCHEMA_VERSION,
            "score_type": "prototype_structure_score",
            "score_interpretation": (
                "B2 mask-structure agreement, not a calibrated calligraphy grade."
            ),
            "prototype_structure_score": float(prototype_score),
            "direction_dice": {
                CHANNELS[index]: float(value) for index, value in enumerate(direction_dice)
            },
            "direction_macro_dice": direction_mean,
            "ink_iou": ink_iou,
            "keypoint_tolerant_f1_radius_3": keypoint_f1,
            "pre_alignment": {
                "center_distance_pixels": raw_center_distance,
                "center_distance_normalized": raw_center_distance / diagonal,
                "center_offset_pixels": {"x": center_offset_x, "y": center_offset_y},
                "center_offset_normalized": {
                    "x": center_offset_x / diagonal,
                    "y": center_offset_y / diagonal,
                },
                "reference_to_user_ink_area_ratio": raw_area_ratio,
            },
            "alignment_policy": {
                "translation": True,
                "isotropic_scale_range": [0.80, 1.20],
                "max_rotation_degrees": 3.0,
                "nonuniform_scale": False,
                "deformable_warp": False,
            },
            "selected_transform": transform,
        }
        return evidence, aligned_reference


def iter_suite(
    definitions: Iterable[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> Iterable[tuple[PerturbationDefinition, float]]:
    for definition in definitions:
        for severity in definition.severities:
            yield definition, float(severity)
