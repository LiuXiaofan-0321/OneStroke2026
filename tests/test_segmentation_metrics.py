from __future__ import annotations

import numpy as np

from onestroke_model.metrics.segmentation import SegmentationMeter, binary_dilate, multilabel_confusion


def test_confusion_preserves_each_channel() -> None:
    pred = np.zeros((1, 6, 4, 4), dtype=bool)
    target = np.zeros_like(pred)
    pred[0, 0, 1:3, 1:3] = True
    target[0, 0, 1:3, 1:3] = True
    pred[0, 1, 0, 0] = True

    confusion = multilabel_confusion(pred, target)

    assert confusion["tp"].shape == (6,)
    assert confusion["tp"][0] == 4
    assert confusion["fp"][0] == 0
    assert confusion["fp"][1] == 1


def test_meter_reports_different_channel_scores() -> None:
    pred = np.zeros((1, 6, 4, 4), dtype=bool)
    target = np.zeros_like(pred)
    pred[0, 0, 1:3, 1:3] = True
    target[0, 0, 1:3, 1:3] = True
    pred[0, 1, 0, 0] = True

    meter = SegmentationMeter()
    meter.update(pred, target)
    metrics = meter.compute()

    assert metrics["dice"][0] == 1.0
    assert metrics["dice"][1] == 0.0
    assert len(metrics["boundary_f1_per_channel"]) == 6


def test_keypoint_tolerance_recovers_one_pixel_shift() -> None:
    pred = np.zeros((1, 6, 5, 5), dtype=bool)
    target = np.zeros_like(pred)
    pred[0, 5, 2, 3] = True
    target[0, 5, 2, 2] = True

    meter = SegmentationMeter(keypoint_tolerances=(0, 1))
    meter.update(pred, target)
    metrics = meter.compute()

    assert metrics["keypoint_f1"] == 0.0
    assert metrics["keypoint_tolerance"]["0"]["f1"] == 0.0
    assert metrics["keypoint_tolerance"]["1"]["f1"] == 1.0


def test_binary_dilate_rejects_invalid_radius() -> None:
    mask = np.zeros((1, 3, 3), dtype=bool)
    try:
        binary_dilate(mask, -1)
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("negative radius should fail")
