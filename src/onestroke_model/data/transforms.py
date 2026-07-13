"""Normalization and label-safe augmentation for six-channel segmentation."""

from __future__ import annotations

import random
from collections.abc import Mapping

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


IMAGENET_MEAN = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)


def normalize_rgb(image: Image.Image, mode: str = "none") -> np.ndarray:
    """Convert an RGB PIL image to normalized CHW float32."""
    array = np.asarray(image, dtype=np.float32) / 255.0
    mode = mode.lower()
    if mode == "imagenet":
        array = (array - IMAGENET_MEAN) / IMAGENET_STD
    elif mode != "none":
        raise ValueError(f"unsupported normalization mode: {mode}")
    return np.transpose(array, (2, 0, 1)).astype(np.float32)


class LabelSafeAugmenter:
    """Apply the same small affine transform to image and all mask channels.

    Direction-channel labels make flips and large rotations unsafe.  This class
    intentionally supports only translation and isotropic scale as geometric
    transforms. Brightness, contrast and blur are image-only appearance changes.
    """

    def __init__(self, config: Mapping[str, object] | None = None, rng: random.Random | None = None) -> None:
        config = config or {}
        if float(config.get("rotation_deg", 0.0)) != 0.0 or float(config.get("hflip_probability", 0.0)) != 0.0:
            raise ValueError("rotation and horizontal flip are disabled for direction-channel label safety")
        self.enabled = bool(config.get("enabled", False))
        self.translate_px = float(config.get("translate_px", 0.0))
        self.scale_min = float(config.get("scale_min", 1.0))
        self.scale_max = float(config.get("scale_max", 1.0))
        self.brightness_min = float(config.get("brightness_min", 1.0))
        self.brightness_max = float(config.get("brightness_max", 1.0))
        self.contrast_min = float(config.get("contrast_min", 1.0))
        self.contrast_max = float(config.get("contrast_max", 1.0))
        self.blur_probability = float(config.get("blur_probability", 0.0))
        self.blur_radius_min = float(config.get("blur_radius_min", 0.1))
        self.blur_radius_max = float(config.get("blur_radius_max", 1.0))
        if self.scale_min <= 0 or self.scale_max < self.scale_min:
            raise ValueError("augmentation scale range must satisfy 0 < scale_min <= scale_max")
        self.rng = rng or random

    def __call__(self, image: Image.Image, masks: list[np.ndarray]) -> tuple[Image.Image, list[np.ndarray]]:
        if not self.enabled:
            return image, masks
        scale = self.rng.uniform(self.scale_min, self.scale_max)
        dx = self.rng.uniform(-self.translate_px, self.translate_px)
        dy = self.rng.uniform(-self.translate_px, self.translate_px)
        if scale != 1.0 or dx != 0.0 or dy != 0.0:
            image, masks = self._affine(image, masks, scale=scale, dx=dx, dy=dy)

        brightness = self.rng.uniform(self.brightness_min, self.brightness_max)
        contrast = self.rng.uniform(self.contrast_min, self.contrast_max)
        if brightness != 1.0:
            image = ImageEnhance.Brightness(image).enhance(brightness)
        if contrast != 1.0:
            image = ImageEnhance.Contrast(image).enhance(contrast)
        if self.blur_probability > 0 and self.rng.random() < self.blur_probability:
            image = image.filter(ImageFilter.GaussianBlur(self.rng.uniform(self.blur_radius_min, self.blur_radius_max)))
        return image, masks

    @staticmethod
    def _affine(
        image: Image.Image,
        masks: list[np.ndarray],
        scale: float,
        dx: float,
        dy: float,
    ) -> tuple[Image.Image, list[np.ndarray]]:
        width, height = image.size
        inverse_scale = 1.0 / scale
        # PIL's affine matrix maps output coordinates back to input coordinates.
        matrix = (
            inverse_scale,
            0.0,
            width * (1.0 - inverse_scale) / 2.0 - dx,
            0.0,
            inverse_scale,
            height * (1.0 - inverse_scale) / 2.0 - dy,
        )
        transformed_image = image.transform(
            image.size,
            Image.Transform.AFFINE,
            matrix,
            resample=Image.Resampling.BILINEAR,
            fillcolor=(255, 255, 255),
        )
        transformed_masks = []
        for mask in masks:
            mask_image = Image.fromarray((mask > 0).astype(np.uint8) * 255)
            mask_image = mask_image.transform(
                image.size,
                Image.Transform.AFFINE,
                matrix,
                resample=Image.Resampling.NEAREST,
                fillcolor=0,
            )
            transformed_masks.append((np.asarray(mask_image) > 127).astype(np.float32))
        return transformed_image, transformed_masks
