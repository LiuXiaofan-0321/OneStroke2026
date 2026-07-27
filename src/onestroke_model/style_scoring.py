"""Deterministic evidence extraction for reference-based calligraphy scoring.

This module deliberately scores B2 segmentation evidence, not artistic quality.
It only accepts same-character reference masks and uses restricted global alignment.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from onestroke_model.constants import CHANNELS, SCHEMA_VERSION


def _as_masks(masks: np.ndarray) -> np.ndarray:
    value = np.asarray(masks, dtype=bool)
    if value.ndim != 3 or value.shape[-1] != len(CHANNELS):
        raise ValueError(f"expected [H,W,{len(CHANNELS)}] masks, got {value.shape}")
    return value


def _ink(mask: np.ndarray) -> np.ndarray:
    return np.any(mask[..., :5], axis=-1)


def _dice(first: np.ndarray, second: np.ndarray) -> float:
    first_sum, second_sum = int(first.sum()), int(second.sum())
    if first_sum == 0 and second_sum == 0:
        return 1.0
    return float(2 * np.logical_and(first, second).sum() / max(1, first_sum + second_sum))


def _iou(first: np.ndarray, second: np.ndarray) -> float:
    union = int(np.logical_or(first, second).sum())
    return 1.0 if union == 0 else float(np.logical_and(first, second).sum() / union)


def _centroid(mask: np.ndarray) -> tuple[float, float]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        raise ValueError("cannot align an empty ink mask")
    return float(xs.mean()), float(ys.mean())


def _translate(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    output = np.zeros_like(mask, dtype=bool)
    height, width = mask.shape
    source_x0, source_x1 = max(0, -dx), min(width, width - dx)
    source_y0, source_y1 = max(0, -dy), min(height, height - dy)
    if source_x0 >= source_x1 or source_y0 >= source_y1:
        return output
    output[source_y0 + dy : source_y1 + dy, source_x0 + dx : source_x1 + dx] = mask[
        source_y0:source_y1, source_x0:source_x1
    ]
    return output


def _scale_rotate(mask: np.ndarray, scale: float, rotation_degrees: float) -> np.ndarray:
    """Apply the allowed global transform around canvas center with nearest masks."""
    height, width = mask.shape
    image = Image.fromarray(mask.astype(np.uint8) * 255, mode="L")
    scaled_w, scaled_h = max(1, round(width * scale)), max(1, round(height * scale))
    scaled = image.resize((scaled_w, scaled_h), resample=Image.Resampling.NEAREST)
    canvas = Image.new("L", (width, height), color=0)
    canvas.paste(scaled, ((width - scaled_w) // 2, (height - scaled_h) // 2))
    rotated = canvas.rotate(rotation_degrees, resample=Image.Resampling.NEAREST, fillcolor=0)
    return np.asarray(rotated, dtype=np.uint8) > 0


def _dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return mask
    padded = np.pad(mask, radius, mode="constant")
    output = np.zeros_like(mask, dtype=bool)
    height, width = mask.shape
    for dy in range(2 * radius + 1):
        for dx in range(2 * radius + 1):
            output |= padded[dy : dy + height, dx : dx + width]
    return output


def _tolerant_f1(prediction: np.ndarray, reference: np.ndarray, radius: int = 3) -> float:
    prediction_sum, reference_sum = int(prediction.sum()), int(reference.sum())
    if prediction_sum == 0 and reference_sum == 0:
        return 1.0
    if prediction_sum == 0 or reference_sum == 0:
        return 0.0
    precision = np.logical_and(prediction, _dilate(reference, radius)).sum() / prediction_sum
    recall = np.logical_and(reference, _dilate(prediction, radius)).sum() / reference_sum
    return float(2 * precision * recall / max(1e-8, precision + recall))


def align_reference_masks(
    user_masks: np.ndarray,
    reference_masks: np.ndarray,
    min_scale: float = 0.80,
    max_scale: float = 1.20,
    max_rotation_degrees: float = 3.0,
) -> tuple[np.ndarray, dict[str, float]]:
    """Find the best permitted global alignment using direction-ink IoU.

    Translation is derived from centroids after each candidate scale/rotation. This
    intentionally cannot reshape individual strokes or compensate local mistakes.
    """
    user_masks = _as_masks(user_masks)
    reference_masks = _as_masks(reference_masks)
    if user_masks.shape != reference_masks.shape:
        raise ValueError("user and reference masks must share a canonical canvas")
    user_ink = _ink(user_masks)
    user_center = _centroid(user_ink)
    scales = np.linspace(min_scale, max_scale, 9)
    rotations = np.linspace(-max_rotation_degrees, max_rotation_degrees, 7)
    best_masks: np.ndarray | None = None
    best_transform: dict[str, float] | None = None
    best_iou = -1.0

    for scale in scales:
        for rotation in rotations:
            transformed = np.stack(
                [_scale_rotate(reference_masks[..., channel], float(scale), float(rotation)) for channel in range(len(CHANNELS))],
                axis=-1,
            )
            reference_center = _centroid(_ink(transformed))
            dx = int(round(user_center[0] - reference_center[0]))
            dy = int(round(user_center[1] - reference_center[1]))
            translated = np.stack(
                [_translate(transformed[..., channel], dx, dy) for channel in range(len(CHANNELS))],
                axis=-1,
            )
            candidate_iou = _iou(user_ink, _ink(translated))
            if candidate_iou > best_iou:
                best_iou = candidate_iou
                best_masks = translated
                best_transform = {
                    "scale": float(scale),
                    "rotation_degrees": float(rotation),
                    "translation_x": float(dx),
                    "translation_y": float(dy),
                    "alignment_ink_iou": float(candidate_iou),
                }
    assert best_masks is not None and best_transform is not None
    return best_masks, best_transform


def score_masks(user_masks: np.ndarray, reference_masks: np.ndarray) -> tuple[dict[str, Any], np.ndarray]:
    """Return calibration-free structural evidence and aligned reference masks."""
    user_masks = _as_masks(user_masks)
    reference_masks = _as_masks(reference_masks)
    if user_masks.shape != reference_masks.shape:
        raise ValueError("user and reference masks must share a canonical canvas")
    user_ink, reference_ink = _ink(user_masks), _ink(reference_masks)
    user_center, reference_center = _centroid(user_ink), _centroid(reference_ink)
    height, width = user_ink.shape
    diagonal = float(np.hypot(height, width))
    raw_center_distance = float(np.hypot(user_center[0] - reference_center[0], user_center[1] - reference_center[1]))
    center_offset_x = float(user_center[0] - reference_center[0])
    center_offset_y = float(user_center[1] - reference_center[1])
    raw_area_ratio = float(reference_ink.sum() / max(1, user_ink.sum()))
    aligned_reference, transform = align_reference_masks(user_masks, reference_masks)

    direction_dice = [
        _dice(user_masks[..., index], aligned_reference[..., index]) for index in range(5)
    ]
    aligned_ink = _ink(aligned_reference)
    keypoint_f1 = _tolerant_f1(user_masks[..., 5], aligned_reference[..., 5], radius=3)
    ink_iou = _iou(user_ink, aligned_ink)
    direction_mean = float(np.mean(direction_dice))
    # This is an evidence aggregation, deliberately not an artistic-grade claim.
    prototype_score = 100.0 * (0.55 * direction_mean + 0.25 * ink_iou + 0.20 * keypoint_f1)
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "score_type": "prototype_structure_score",
        "score_interpretation": "B2 mask-structure agreement, not a calibrated calligraphy grade.",
        "prototype_structure_score": float(prototype_score),
        "direction_dice": {CHANNELS[index]: float(value) for index, value in enumerate(direction_dice)},
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


def save_score_assets(
    output_dir: str | Path,
    evidence: dict[str, Any],
    user_masks: np.ndarray,
    aligned_reference_masks: np.ndarray,
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    user_ink, reference_ink = _ink(_as_masks(user_masks)), _ink(_as_masks(aligned_reference_masks))
    overlay = np.full((*user_ink.shape, 3), 255, dtype=np.uint8)
    overlay[reference_ink] = [230, 82, 70]
    overlay[user_ink] = [52, 117, 194]
    overlay[np.logical_and(user_ink, reference_ink)] = [96, 166, 88]
    Image.fromarray(overlay, mode="RGB").save(output_dir / "alignment_overlay.png")
