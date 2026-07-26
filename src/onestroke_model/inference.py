from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from onestroke_model.constants import CHANNELS, SCHEMA_VERSION
from onestroke_model.data.dataset import _letterbox_image
from onestroke_model.data.transforms import normalize_rgb


def prepare_image(
    path: str | Path,
    image_size: int,
    normalization: str = "none",
) -> tuple[np.ndarray, tuple[int, int]]:
    image = Image.open(path).convert("RGB")
    original_size = (image.height, image.width)
    boxed = _letterbox_image(image, image_size, Image.Resampling.BILINEAR)
    return normalize_rgb(boxed, normalization)[None, ...], original_size


def restore_letterbox_probabilities(probabilities: np.ndarray, original_size: tuple[int, int]) -> np.ndarray:
    """Map [S,S,C] letterboxed probabilities back to original [H,W,C]."""
    original_h, original_w = original_size
    size = probabilities.shape[0]
    scale = min(size / original_w, size / original_h)
    new_w, new_h = max(1, round(original_w * scale)), max(1, round(original_h * scale))
    left = (size - new_w) // 2
    top = (size - new_h) // 2
    cropped = probabilities[top : top + new_h, left : left + new_w]
    restored_channels = []
    for c in range(cropped.shape[-1]):
        im = Image.fromarray(cropped[..., c].astype(np.float32), mode="F")
        im = im.resize((original_w, original_h), resample=Image.Resampling.BILINEAR)
        restored_channels.append(np.asarray(im).astype(np.float32))
    return np.stack(restored_channels, axis=-1)


def package_prediction(
    probabilities: np.ndarray,
    thresholds: dict[str, float] | None = None,
    latency_ms: float | None = None,
) -> dict[str, Any]:
    if thresholds is None:
        thresholds = {c: 0.5 for c in CHANNELS}
    masks = np.stack(
        [(probabilities[..., i] >= thresholds[CHANNELS[i]]) for i in range(len(CHANNELS))],
        axis=-1,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "channels": list(CHANNELS),
        "probabilities": probabilities,
        "binary_masks": masks.astype(np.uint8),
        "thresholds": thresholds,
        "latency_ms": latency_ms,
    }


def now_ms() -> float:
    return time.perf_counter() * 1000


def extract_keypoints(
    keypoint_mask: np.ndarray,
    keypoint_probability: np.ndarray,
    min_area: int = 3,
) -> list[dict[str, float | int]]:
    """Convert the keypoint mask into 8-connected component centroids."""
    mask = keypoint_mask.astype(bool)
    if mask.ndim != 2 or keypoint_probability.shape != mask.shape:
        raise ValueError("keypoint mask and probability must share [H,W] shape")
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    points: list[dict[str, float | int]] = []
    for start_y, start_x in np.argwhere(mask):
        if visited[start_y, start_x]:
            continue
        queue = deque([(int(start_y), int(start_x))])
        visited[start_y, start_x] = True
        component: list[tuple[int, int]] = []
        while queue:
            y, x = queue.popleft()
            component.append((y, x))
            for next_y in range(max(0, y - 1), min(height, y + 2)):
                for next_x in range(max(0, x - 1), min(width, x + 2)):
                    if mask[next_y, next_x] and not visited[next_y, next_x]:
                        visited[next_y, next_x] = True
                        queue.append((next_y, next_x))
        if len(component) < min_area:
            continue
        ys = np.asarray([item[0] for item in component], dtype=np.int32)
        xs = np.asarray([item[1] for item in component], dtype=np.int32)
        probabilities = keypoint_probability[ys, xs]
        points.append(
            {
                "x": float(xs.mean()),
                "y": float(ys.mean()),
                "area": int(len(component)),
                "confidence": float(probabilities.max()),
            }
        )
    return sorted(points, key=lambda item: (float(item["y"]), float(item["x"])))


def save_prediction_assets(
    image_path: str | Path,
    packaged: dict[str, Any],
    output_dir: str | Path,
    model_version: str,
) -> dict[str, Any]:
    """Save model-service-ready masks, overlay, coordinates, archive and result JSON."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    probabilities = np.asarray(packaged["probabilities"], dtype=np.float32)
    masks = np.asarray(packaged["binary_masks"], dtype=np.uint8)
    channels = list(packaged["channels"])
    thresholds = {name: float(packaged["thresholds"][name]) for name in channels}

    archive_name = "prediction.npz"
    np.savez_compressed(
        output / archive_name,
        probabilities=probabilities,
        binary_masks=masks,
        channels=np.asarray(channels),
        thresholds=np.asarray([thresholds[name] for name in channels], dtype=np.float32),
        latency_ms=np.asarray([packaged.get("latency_ms")], dtype=np.float32),
    )

    mask_assets: dict[str, str] = {}
    for index, channel in enumerate(channels):
        filename = f"mask_{channel}.png"
        Image.fromarray(masks[..., index] * 255, mode="L").save(output / filename)
        mask_assets[channel] = filename

    original = Image.open(image_path).convert("RGB")
    base = np.asarray(original, dtype=np.float32)
    overlay = base.copy()
    colors = np.asarray(
        [
            [215, 48, 39],
            [252, 141, 89],
            [49, 130, 189],
            [116, 196, 118],
            [117, 107, 177],
            [0, 180, 180],
        ],
        dtype=np.float32,
    )
    for index in range(min(masks.shape[-1], len(colors))):
        active = masks[..., index].astype(bool)
        overlay[active] = 0.58 * overlay[active] + 0.42 * colors[index]
    overlay_image = Image.fromarray(np.clip(overlay, 0, 255).astype(np.uint8))

    keypoint_index = channels.index("keypoint")
    keypoints = extract_keypoints(
        masks[..., keypoint_index], probabilities[..., keypoint_index]
    )
    draw = ImageDraw.Draw(overlay_image)
    for point in keypoints:
        x, y = float(point["x"]), float(point["y"])
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), outline=(0, 255, 255), width=2)
    overlay_name = "overlay.png"
    overlay_image.save(output / overlay_name)

    result = {
        "schema_version": int(packaged["schema_version"]),
        "model_version": model_version,
        "capabilities": {
            "segmentation": True,
            "keypoint_localization": True,
            "style_conditioning": False,
            "style_scoring": False,
            "natural_language_feedback": False,
            "stroke_order_analysis": False,
        },
        "image_size": {"height": int(probabilities.shape[0]), "width": int(probabilities.shape[1])},
        "channels": channels,
        "thresholds": thresholds,
        "latency_ms": float(packaged["latency_ms"]) if packaged.get("latency_ms") is not None else None,
        "probability_archive": archive_name,
        "mask_assets": mask_assets,
        "overlay_asset": overlay_name,
        "keypoints": keypoints,
        "scores": None,
        "feedback": [],
    }
    (output / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
