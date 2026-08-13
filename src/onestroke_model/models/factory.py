from __future__ import annotations

from typing import Any


def build_model(config: dict[str, Any], load_pretrained: bool = True):
    name = config.get("name")
    if name == "unet":
        from .unet import UNet

        return UNet(
            in_channels=int(config.get("in_channels", 3)),
            out_channels=int(config.get("out_channels", 6)),
            base_channels=int(config.get("base_channels", 64)),
        )
    if name == "segformer":
        from .segformer import SegFormerMultiLabel

        return SegFormerMultiLabel(
            backbone=str(config.get("backbone", "nvidia/segformer-b2-finetuned-ade-512-512")),
            out_channels=int(config.get("out_channels", 6)),
            load_pretrained=load_pretrained,
        )
    if name == "deeplabv3plus":
        from .deeplabv3plus import DeepLabV3PlusMultiLabel

        return DeepLabV3PlusMultiLabel(
            backbone=str(config.get("backbone", "resnet50")),
            out_channels=int(config.get("out_channels", 6)),
            load_pretrained=load_pretrained,
        )
    raise ValueError(f"Unknown model name: {name}")
