from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

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
        im = Image.fromarray((cropped[..., c] * 255).astype(np.uint8))
        im = im.resize((original_w, original_h), resample=Image.Resampling.BILINEAR)
        restored_channels.append(np.asarray(im).astype(np.float32) / 255.0)
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
