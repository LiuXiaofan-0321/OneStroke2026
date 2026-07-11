from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from onestroke_model.constants import CHANNELS
from onestroke_model.utils.io import read_csv_rows


def _letterbox_image(image: Image.Image, size: int, resample: int) -> Image.Image:
    w, h = image.size
    scale = min(size / w, size / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    resized = image.resize((nw, nh), resample=resample)
    canvas = Image.new(image.mode, (size, size))
    canvas.paste(resized, ((size - nw) // 2, (size - nh) // 2))
    return canvas


def _letterbox_mask(mask: np.ndarray, size: int) -> np.ndarray:
    im = Image.fromarray(mask.astype(np.uint8) * 255)
    boxed = _letterbox_image(im, size, Image.Resampling.NEAREST)
    return (np.asarray(boxed) > 127).astype(np.float32)


class OneStrokeSegmentationDataset:
    """Torch-compatible dataset without importing torch at module import time."""

    def __init__(
        self,
        manifest_path: str | Path,
        splits_path: str | Path,
        split: str,
        image_size: int = 512,
    ) -> None:
        manifest = {r["sample_id"]: r for r in read_csv_rows(manifest_path)}
        split_ids = {r["sample_id"] for r in read_csv_rows(splits_path) if r["split"] == split}
        self.rows = [manifest[sid] for sid in sorted(split_ids) if sid in manifest]
        self.image_size = image_size

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        row = self.rows[idx]
        image = Image.open(row["image_path"]).convert("RGB")
        image = _letterbox_image(image, self.image_size, Image.Resampling.BILINEAR)
        image_arr = np.asarray(image).astype(np.float32) / 255.0
        image_arr = np.transpose(image_arr, (2, 0, 1))

        masks = []
        for channel in CHANNELS:
            mask = np.load(row[f"{channel}_path"])
            masks.append(_letterbox_mask(mask, self.image_size))
        mask_arr = np.stack(masks, axis=0).astype(np.float32)

        return {
            "image": image_arr,
            "mask": mask_arr,
            "sample_id": row["sample_id"],
            "original_size": (row.get("image_height", ""), row.get("image_width", "")),
        }


def make_torch_loader(
    manifest_path: str | Path,
    splits_path: str | Path,
    split: str,
    image_size: int,
    batch_size: int,
    num_workers: int = 0,
    shuffle: bool | None = None,
):
    try:
        from torch.utils.data import DataLoader
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError("Install training extras first: pip install -e '.[train]'") from exc

    dataset = OneStrokeSegmentationDataset(manifest_path, splits_path, split, image_size)
    if shuffle is None:
        shuffle = split == "train"
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=True,
    )


def estimate_direction_pos_weight(
    manifest_path: str | Path,
    splits_path: str | Path,
    max_samples: int = 200,
    max_weight: float = 100.0,
) -> dict[str, object]:
    """Estimate stable positive weights from evenly sampled training masks.

    We scan original-resolution masks because letterboxing preserves foreground
    occupancy ratios well enough while avoiding GPU/data-loader startup costs.
    """
    dataset = OneStrokeSegmentationDataset(manifest_path, splits_path, "train")
    if not dataset.rows:
        raise ValueError("cannot estimate class weights: training split is empty")
    if max_samples <= 0 or max_samples >= len(dataset.rows):
        selected = dataset.rows
    else:
        indices = np.linspace(0, len(dataset.rows) - 1, num=max_samples, dtype=int)
        selected = [dataset.rows[i] for i in indices]

    positives = np.zeros(5, dtype=np.float64)
    total_pixels = np.zeros(5, dtype=np.float64)
    for row in selected:
        for i, channel in enumerate(CHANNELS[:5]):
            mask = np.asarray(np.load(row[f"{channel}_path"])) > 0
            positives[i] += float(mask.sum())
            total_pixels[i] += float(mask.size)
    negatives = total_pixels - positives
    weights = np.divide(negatives, np.maximum(positives, 1.0))
    weights = np.clip(weights, 1.0, max_weight)
    return {
        "method": "negatives_over_positives",
        "num_samples": len(selected),
        "max_weight": float(max_weight),
        "positive_pixels": positives.tolist(),
        "positive_ratio": (positives / np.maximum(total_pixels, 1.0)).tolist(),
        "direction_pos_weight": weights.tolist(),
    }
