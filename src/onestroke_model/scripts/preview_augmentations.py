"""Render original and augmented image/mask overlays before expensive training."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from onestroke_model.config import load_yaml
from onestroke_model.data.dataset import OneStrokeSegmentationDataset
from onestroke_model.utils.io import ensure_dir


def _overlay(image_chw: np.ndarray, mask_chw: np.ndarray) -> Image.Image:
    image = Image.fromarray(np.clip(np.transpose(image_chw, (1, 2, 0)) * 255, 0, 255).astype(np.uint8)).convert("RGBA")
    union = mask_chw.any(axis=0)
    overlay = Image.new("RGBA", image.size, (255, 0, 0, 0))
    overlay_array = np.asarray(overlay).copy()
    overlay_array[union] = np.asarray([255, 80, 60, 100], dtype=np.uint8)
    return Image.alpha_composite(image, Image.fromarray(overlay_array, mode="RGBA")).convert("RGB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview segmentation augmentation alignment.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", default="artifacts/augmentation_preview.png")
    parser.add_argument("--num-samples", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260713)
    args = parser.parse_args()
    random.seed(args.seed)
    cfg = load_yaml(args.config)
    data_cfg = cfg["data"]
    base = OneStrokeSegmentationDataset(
        data_cfg["manifest"], data_cfg["splits"], "train", int(data_cfg.get("image_size", 512)), normalization="none"
    )
    augmented = OneStrokeSegmentationDataset(
        data_cfg["manifest"],
        data_cfg["splits"],
        "train",
        int(data_cfg.get("image_size", 512)),
        normalization="none",
        augmentation=data_cfg.get("augmentation"),
    )
    count = min(args.num_samples, len(base))
    cell_size = int(data_cfg.get("image_size", 512))
    title_height = 28
    canvas = Image.new("RGB", (cell_size * 2, (cell_size + title_height) * count), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index in range(count):
        original = base[index]
        transformed = augmented[index]
        y = index * (cell_size + title_height)
        canvas.paste(_overlay(original["image"], original["mask"]), (0, y + title_height))
        canvas.paste(_overlay(transformed["image"], transformed["mask"]), (cell_size, y + title_height))
        draw.text((4, y + 6), f"original: {original['sample_id']}", fill="black", font=font)
        draw.text((cell_size + 4, y + 6), f"augmented: {transformed['sample_id']}", fill="black", font=font)
    output = Path(args.output)
    ensure_dir(output.parent)
    canvas.save(output)
    print(f"wrote {count} original/augmented pairs to {output}")


if __name__ == "__main__":
    main()
