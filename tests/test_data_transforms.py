from __future__ import annotations

import numpy as np
from PIL import Image

from onestroke_model.data.transforms import LabelSafeAugmenter, normalize_rgb


class _FixedRng:
    def uniform(self, lower: float, upper: float) -> float:
        return upper

    def random(self) -> float:
        return 1.0


def test_imagenet_normalization_matches_known_white_pixel() -> None:
    image = Image.new("RGB", (2, 2), "white")
    normalized = normalize_rgb(image, "imagenet")
    expected = (1.0 - 0.485) / 0.229
    assert normalized.shape == (3, 2, 2)
    assert np.isclose(normalized[0, 0, 0], expected)


def test_affine_augmentation_preserves_image_mask_alignment() -> None:
    image_array = np.full((16, 16, 3), 255, dtype=np.uint8)
    image_array[4:8, 4:8] = 0
    image = Image.fromarray(image_array)
    mask = np.zeros((16, 16), dtype=np.float32)
    mask[4:8, 4:8] = 1.0
    augmenter = LabelSafeAugmenter(
        {
            "enabled": True,
            "translate_px": 2,
            "scale_min": 1.0,
            "scale_max": 1.0,
            "brightness_min": 1.0,
            "brightness_max": 1.0,
            "contrast_min": 1.0,
            "contrast_max": 1.0,
            "blur_probability": 0.0,
        },
        rng=_FixedRng(),
    )

    transformed_image, transformed_masks = augmenter(image, [mask])
    foreground_from_image = np.asarray(transformed_image)[..., 0] < 128

    assert np.array_equal(foreground_from_image, transformed_masks[0].astype(bool))
