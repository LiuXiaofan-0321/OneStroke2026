from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F


class SegFormerMultiLabel(nn.Module):
    """SegFormer backbone with a six-channel multi-label sigmoid-logit head.

    We use the Hugging Face SegFormer backbone and replace the final classifier.
    Training code must use BCE/Dice-style losses instead of softmax CE.
    """

    def __init__(self, backbone: str, out_channels: int = 6) -> None:
        super().__init__()
        try:
            from transformers import SegformerForSemanticSegmentation
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError("Install training extras first: pip install -e '.[train]'") from exc

        self.model = SegformerForSemanticSegmentation.from_pretrained(
            backbone,
            num_labels=out_channels,
            ignore_mismatched_sizes=True,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        logits = self.model(pixel_values=x).logits
        if logits.shape[-2:] != x.shape[-2:]:
            logits = F.interpolate(logits, size=x.shape[-2:], mode="bilinear", align_corners=False)
        return logits

