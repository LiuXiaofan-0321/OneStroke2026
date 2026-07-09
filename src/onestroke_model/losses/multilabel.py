from __future__ import annotations

import torch
import torch.nn.functional as F


def dice_loss_from_logits(logits: torch.Tensor, targets: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    dims = tuple(range(2, logits.ndim))
    intersection = (probs * targets).sum(dim=dims)
    denominator = probs.sum(dim=dims) + targets.sum(dim=dims)
    dice = (2 * intersection + eps) / (denominator + eps)
    return 1 - dice.mean()


def focal_loss_from_logits(
    logits: torch.Tensor,
    targets: torch.Tensor,
    gamma: float = 2.0,
    alpha: float = 0.25,
) -> torch.Tensor:
    bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    prob = torch.sigmoid(logits)
    p_t = prob * targets + (1 - prob) * (1 - targets)
    alpha_t = alpha * targets + (1 - alpha) * (1 - targets)
    return (alpha_t * (1 - p_t).pow(gamma) * bce).mean()


def multilabel_stroke_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    direction_logits = logits[:, :5]
    direction_targets = targets[:, :5]
    keypoint_logits = logits[:, 5:6]
    keypoint_targets = targets[:, 5:6]

    direction = F.binary_cross_entropy_with_logits(direction_logits, direction_targets)
    direction = direction + dice_loss_from_logits(direction_logits, direction_targets)

    keypoint = focal_loss_from_logits(keypoint_logits, keypoint_targets)
    keypoint = keypoint + dice_loss_from_logits(keypoint_logits, keypoint_targets)
    return direction + keypoint

