from __future__ import annotations

import json

import numpy as np
from PIL import Image

from onestroke_model.inference import extract_keypoints, package_prediction, save_prediction_assets


def test_extract_keypoints_returns_component_centroids() -> None:
    mask = np.zeros((8, 8), dtype=np.uint8)
    mask[1:3, 2:4] = 1
    mask[6, 6] = 1
    probability = mask.astype(np.float32) * 0.9

    points = extract_keypoints(mask, probability, min_area=2)

    assert len(points) == 1
    assert points[0]["x"] == 2.5
    assert points[0]["y"] == 1.5
    assert points[0]["area"] == 4


def test_save_prediction_assets_declares_unavailable_future_capabilities(tmp_path) -> None:
    image_path = tmp_path / "input.png"
    Image.new("RGB", (8, 8), "white").save(image_path)
    probabilities = np.zeros((8, 8, 6), dtype=np.float32)
    probabilities[1:3, 2:4, 5] = 0.9
    packaged = package_prediction(
        probabilities,
        thresholds={
            "vec1": 0.5,
            "vec2": 0.5,
            "vec3": 0.5,
            "vec4": 0.5,
            "vec5": 0.5,
            "keypoint": 0.5,
        },
        latency_ms=12.5,
    )

    result = save_prediction_assets(image_path, packaged, tmp_path / "result", "test-model")
    saved = json.loads((tmp_path / "result" / "result.json").read_text(encoding="utf-8"))

    assert result["model_version"] == "test-model"
    assert saved["capabilities"]["segmentation"] is True
    assert saved["capabilities"]["style_scoring"] is False
    assert len(saved["keypoints"]) == 1
    assert (tmp_path / "result" / "overlay.png").exists()
    assert (tmp_path / "result" / "mask_keypoint.png").exists()
