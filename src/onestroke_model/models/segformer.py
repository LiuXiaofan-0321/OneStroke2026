from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F


class SegFormerMultiLabel(nn.Module):
    """SegFormer backbone with a six-channel multi-label sigmoid-logit head.

    We use the Hugging Face SegFormer backbone and replace the final classifier.
    Training code must use BCE/Dice-style losses instead of softmax CE.
    """

    def __init__(self, backbone: str, out_channels: int = 6, load_pretrained: bool = True) -> None:
        super().__init__()
        try:
            from transformers import SegformerConfig, SegformerForSemanticSegmentation
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError("Install training extras first: pip install -e '.[train]'") from exc

        if load_pretrained:
            self.model = SegformerForSemanticSegmentation.from_pretrained(
                backbone,
                num_labels=out_channels,
                ignore_mismatched_sizes=True,
            )
        else:
            self.model = SegformerForSemanticSegmentation(
                _offline_segformer_config(SegformerConfig, backbone, out_channels)
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        logits = self.model(pixel_values=x).logits
        if logits.shape[-2:] != x.shape[-2:]:
            logits = F.interpolate(logits, size=x.shape[-2:], mode="bilinear", align_corners=False)
        return logits


def _offline_segformer_config(config_class, backbone: str, out_channels: int):
    """Recreate official MiT variants so deployed checkpoints need no Hub access."""
    name = backbone.lower()
    variants = {
        "b0": ([32, 64, 160, 256], [2, 2, 2, 2], 256),
        "b1": ([64, 128, 320, 512], [2, 2, 2, 2], 256),
        "b2": ([64, 128, 320, 512], [3, 4, 6, 3], 768),
        "b3": ([64, 128, 320, 512], [3, 4, 18, 3], 768),
        "b4": ([64, 128, 320, 512], [3, 8, 27, 3], 768),
        "b5": ([64, 128, 320, 512], [3, 6, 40, 3], 768),
    }
    variant = next((key for key in variants if f"segformer-{key}" in name), None)
    if variant is None:
        raise ValueError(f"Cannot infer offline SegFormer architecture from backbone: {backbone}")
    hidden_sizes, depths, decoder_hidden_size = variants[variant]
    return config_class(
        hidden_sizes=hidden_sizes,
        depths=depths,
        num_attention_heads=[1, 2, 5, 8],
        sr_ratios=[8, 4, 2, 1],
        patch_sizes=[7, 3, 3, 3],
        strides=[4, 2, 2, 2],
        mlp_ratios=[4, 4, 4, 4],
        decoder_hidden_size=decoder_hidden_size,
        num_labels=out_channels,
        id2label={index: str(index) for index in range(out_channels)},
        label2id={str(index): index for index in range(out_channels)},
    )
