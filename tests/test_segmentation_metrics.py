from __future__ import annotations

import numpy as np

from onestroke_model.metrics.segmentation import SegmentationMeter, multilabel_confusion


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
