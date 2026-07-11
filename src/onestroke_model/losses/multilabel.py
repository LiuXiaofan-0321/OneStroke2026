from __future__ import annotations

from collections.abc import Sequence

import torch
import torch.nn.functional as F
from torch import nn


def dice_loss_from_probs(probs: torch.Tensor, targets: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """Soft Dice loss for independent multi-label channels."""
    dims = tuple(range(2, probs.ndim))
    intersection = (probs * targets).sum(dim=dims)
    denominator = probs.sum(dim=dims) + targets.sum(dim=dims)
    dice = (2 * intersection + eps) / (denominator + eps)
    return 1 - dice.mean()


def dice_loss_from_logits(logits: torch.Tensor, targets: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    return dice_loss_from_probs(torch.sigmoid(logits), targets, eps=eps)


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


def _morphological_boundary(masks: torch.Tensor) -> torch.Tensor:
    """Return a one-pixel-ish boundary map without a scipy dependency."""
    dilated = F.max_pool2d(masks, kernel_size=3, stride=1, padding=1)
    eroded = 1.0 - F.max_pool2d(1.0 - masks, kernel_size=3, stride=1, padding=1)
    return (dilated - eroded).clamp(0.0, 1.0)


def boundary_loss_from_logits(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    """Supervise predicted contour strength using boundaries derived from masks."""
    probabilities = torch.sigmoid(logits)
    predicted_boundary = _morphological_boundary(probabilities)
    target_boundary = _morphological_boundary(targets)
    bce = F.binary_cross_entropy(predicted_boundary.clamp(1e-5, 1 - 1e-5), target_boundary)
    return bce + dice_loss_from_probs(predicted_boundary, target_boundary)


class MultiLabelStrokeLoss(nn.Module):
    """Configured loss for five direction masks and one sparse keypoint mask."""

    def __init__(
        self,
        direction_pos_weight: Sequence[float] | None = None,
        direction_bce_weight: float = 1.0,
        direction_dice_weight: float = 1.0,
        keypoint_focal_weight: float = 1.0,
        keypoint_dice_weight: float = 1.0,
        focal_gamma: float = 2.0,
        focal_alpha: float = 0.25,
        boundary_weight: float = 0.2,
    ) -> None:
        super().__init__()
        if direction_pos_weight is None:
            direction_pos_weight = [1.0] * 5
        if len(direction_pos_weight) != 5:
            raise ValueError("direction_pos_weight must contain one value for vec1 through vec5")
        self.register_buffer(
            "direction_pos_weight", torch.tensor(direction_pos_weight, dtype=torch.float32).view(1, 5, 1, 1)
        )
        self.direction_bce_weight = float(direction_bce_weight)
        self.direction_dice_weight = float(direction_dice_weight)
        self.keypoint_focal_weight = float(keypoint_focal_weight)
        self.keypoint_dice_weight = float(keypoint_dice_weight)
        self.focal_gamma = float(focal_gamma)
        self.focal_alpha = float(focal_alpha)
        self.boundary_weight = float(boundary_weight)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        if logits.shape != targets.shape or logits.shape[1] != 6:
            raise ValueError("expected logits and targets with matching [B, 6, H, W] shape")
        direction_logits = logits[:, :5]
        direction_targets = targets[:, :5]
        keypoint_logits = logits[:, 5:6]
        keypoint_targets = targets[:, 5:6]

        direction_bce = F.binary_cross_entropy_with_logits(
            direction_logits,
            direction_targets,
            pos_weight=self.direction_pos_weight,
        )
        direction_dice = dice_loss_from_logits(direction_logits, direction_targets)
        keypoint_focal = focal_loss_from_logits(
            keypoint_logits,
            keypoint_targets,
            gamma=self.focal_gamma,
            alpha=self.focal_alpha,
        )
        keypoint_dice = dice_loss_from_logits(keypoint_logits, keypoint_targets)
        boundary = boundary_loss_from_logits(logits, targets)
        return (
            self.direction_bce_weight * direction_bce
            + self.direction_dice_weight * direction_dice
            + self.keypoint_focal_weight * keypoint_focal
            + self.keypoint_dice_weight * keypoint_dice
            + self.boundary_weight * boundary
        )


def multilabel_stroke_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    """Backward-compatible default loss; training uses ``MultiLabelStrokeLoss``."""
    return MultiLabelStrokeLoss()(logits, targets)
