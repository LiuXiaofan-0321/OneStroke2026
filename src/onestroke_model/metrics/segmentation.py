from __future__ import annotations

import numpy as np


def _safe_div(num: float, den: float) -> float:
    return float(num / den) if den else 0.0


def multilabel_confusion(pred: np.ndarray, target: np.ndarray) -> dict[str, np.ndarray]:
    if pred.shape != target.shape or pred.ndim < 3:
        raise ValueError("pred and target must share [N, C, ...] shape")
    pred_bool = pred.astype(bool)
    target_bool = target.astype(bool)
    # Preserve the channel dimension. The previous reduction included it,
    # broadcasting one global count into all six channels.
    axes = (0, *range(2, pred.ndim))
    tp = np.logical_and(pred_bool, target_bool).sum(axis=axes)
    fp = np.logical_and(pred_bool, ~target_bool).sum(axis=axes)
    fn = np.logical_and(~pred_bool, target_bool).sum(axis=axes)
    tn = np.logical_and(~pred_bool, ~target_bool).sum(axis=axes)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def boundary_map(mask: np.ndarray) -> np.ndarray:
    """Morphological boundary for boolean [N, C, H, W] arrays."""
    if mask.ndim != 4:
        raise ValueError("boundary_map expects [N, C, H, W]")
    padded = np.pad(mask.astype(bool), ((0, 0), (0, 0), (1, 1), (1, 1)), constant_values=False)
    h, w = mask.shape[-2:]
    neighborhoods = [padded[:, :, dy : dy + h, dx : dx + w] for dy in range(3) for dx in range(3)]
    return np.logical_or.reduce(neighborhoods) ^ np.logical_and.reduce(neighborhoods)


def dice_iou_precision_recall(pred: np.ndarray, target: np.ndarray) -> dict[str, list[float] | float]:
    c = multilabel_confusion(pred, target)
    dice = []
    iou = []
    precision = []
    recall = []
    for tp, fp, fn in zip(c["tp"], c["fp"], c["fn"], strict=True):
        tp_f, fp_f, fn_f = float(tp), float(fp), float(fn)
        dice.append(_safe_div(2 * tp_f, 2 * tp_f + fp_f + fn_f))
        iou.append(_safe_div(tp_f, tp_f + fp_f + fn_f))
        precision.append(_safe_div(tp_f, tp_f + fp_f))
        recall.append(_safe_div(tp_f, tp_f + fn_f))
    return {
        "dice": dice,
        "iou": iou,
        "precision": precision,
        "recall": recall,
        "macro_dice": float(np.mean(dice[:5])) if len(dice) >= 5 else float(np.mean(dice)),
        "macro_iou": float(np.mean(iou[:5])) if len(iou) >= 5 else float(np.mean(iou)),
        "keypoint_f1": dice[5] if len(dice) > 5 else 0.0,
    }


class SegmentationMeter:
    def __init__(self, num_channels: int = 6) -> None:
        self.tp = np.zeros(num_channels, dtype=np.float64)
        self.fp = np.zeros(num_channels, dtype=np.float64)
        self.fn = np.zeros(num_channels, dtype=np.float64)
        self.boundary_tp = np.zeros(num_channels, dtype=np.float64)
        self.boundary_fp = np.zeros(num_channels, dtype=np.float64)
        self.boundary_fn = np.zeros(num_channels, dtype=np.float64)

    def update(self, pred: np.ndarray, target: np.ndarray) -> None:
        c = multilabel_confusion(pred, target)
        self.tp += c["tp"]
        self.fp += c["fp"]
        self.fn += c["fn"]
        boundary = multilabel_confusion(boundary_map(pred), boundary_map(target))
        self.boundary_tp += boundary["tp"]
        self.boundary_fp += boundary["fp"]
        self.boundary_fn += boundary["fn"]

    def compute(self) -> dict[str, list[float] | float]:
        dice = []
        iou = []
        precision = []
        recall = []
        for tp, fp, fn in zip(self.tp, self.fp, self.fn, strict=True):
            dice.append(_safe_div(2 * tp, 2 * tp + fp + fn))
            iou.append(_safe_div(tp, tp + fp + fn))
            precision.append(_safe_div(tp, tp + fp))
            recall.append(_safe_div(tp, tp + fn))
        boundary_f1 = [
            _safe_div(2 * tp, 2 * tp + fp + fn)
            for tp, fp, fn in zip(self.boundary_tp, self.boundary_fp, self.boundary_fn, strict=True)
        ]
        return {
            "dice": dice,
            "iou": iou,
            "precision": precision,
            "recall": recall,
            "macro_dice": float(np.mean(dice[:5])),
            "macro_iou": float(np.mean(iou[:5])),
            "keypoint_f1": dice[5] if len(dice) > 5 else 0.0,
            "boundary_f1_per_channel": boundary_f1,
            "boundary_f1": float(np.mean(boundary_f1[:5])),
        }
