from __future__ import annotations

from collections.abc import Iterator

import torch
import torch.nn.functional as F
from torch import nn


class ConvNormAct(nn.Sequential):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        *,
        padding: int = 0,
        dilation: int = 1,
    ) -> None:
        super().__init__(
            nn.Conv2d(
                in_channels,
                out_channels,
                kernel_size,
                padding=padding,
                dilation=dilation,
                bias=False,
            ),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )


class ResNet50Encoder(nn.Module):
    """ImageNet ResNet-50 encoder with output stride 16."""

    def __init__(self, *, load_pretrained: bool) -> None:
        super().__init__()
        try:
            from torchvision.models import ResNet50_Weights, resnet50
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "DeepLabV3+ requires torchvision. Install: pip install -e '.[train]'"
            ) from exc

        weights = ResNet50_Weights.DEFAULT if load_pretrained else None
        backbone = resnet50(
            weights=weights,
            replace_stride_with_dilation=[False, False, True],
        )
        self.stem = nn.Sequential(
            backbone.conv1,
            backbone.bn1,
            backbone.relu,
            backbone.maxpool,
        )
        self.layer1 = backbone.layer1
        self.layer2 = backbone.layer2
        self.layer3 = backbone.layer3
        self.layer4 = backbone.layer4

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        x = self.stem(x)
        low_level = self.layer1(x)
        x = self.layer2(low_level)
        x = self.layer3(x)
        high_level = self.layer4(x)
        return low_level, high_level


class ASPPPooling(nn.Sequential):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(in_channels, out_channels, 1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        output = super().forward(x)
        return F.interpolate(
            output,
            size=x.shape[-2:],
            mode="bilinear",
            align_corners=False,
        )


class ASPP(nn.Module):
    def __init__(
        self,
        in_channels: int = 2048,
        out_channels: int = 256,
        rates: tuple[int, int, int] = (6, 12, 18),
    ) -> None:
        super().__init__()
        branches: list[nn.Module] = [ConvNormAct(in_channels, out_channels, 1)]
        branches.extend(
            ConvNormAct(
                in_channels,
                out_channels,
                3,
                padding=rate,
                dilation=rate,
            )
            for rate in rates
        )
        branches.append(ASPPPooling(in_channels, out_channels))
        self.branches = nn.ModuleList(branches)
        self.project = nn.Sequential(
            ConvNormAct(out_channels * len(branches), out_channels, 1),
            nn.Dropout(0.1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.project(torch.cat([branch(x) for branch in self.branches], dim=1))


class DeepLabV3PlusDecoder(nn.Module):
    def __init__(
        self,
        *,
        low_level_channels: int = 256,
        high_level_channels: int = 2048,
        decoder_channels: int = 256,
        low_level_projection_channels: int = 48,
        out_channels: int = 6,
    ) -> None:
        super().__init__()
        self.aspp = ASPP(high_level_channels, decoder_channels)
        self.low_level_projection = ConvNormAct(
            low_level_channels,
            low_level_projection_channels,
            1,
        )
        merged_channels = decoder_channels + low_level_projection_channels
        self.fuse = nn.Sequential(
            ConvNormAct(merged_channels, decoder_channels, 3, padding=1),
            ConvNormAct(decoder_channels, decoder_channels, 3, padding=1),
        )
        self.classifier = nn.Conv2d(decoder_channels, out_channels, 1)

    def forward(
        self,
        low_level: torch.Tensor,
        high_level: torch.Tensor,
    ) -> torch.Tensor:
        high_level = self.aspp(high_level)
        low_level = self.low_level_projection(low_level)
        high_level = F.interpolate(
            high_level,
            size=low_level.shape[-2:],
            mode="bilinear",
            align_corners=False,
        )
        return self.classifier(self.fuse(torch.cat([low_level, high_level], dim=1)))


class DeepLabV3PlusMultiLabel(nn.Module):
    """DeepLabV3+ with a six-channel independent-logit output head.

    The encoder is an ImageNet-pretrained ResNet-50. The decoder uses ASPP at
    output stride 16 and fuses stride-4 low-level features. No sigmoid or
    softmax is applied inside the model; the shared training/evaluation code
    handles independent sigmoid channels.
    """

    def __init__(
        self,
        *,
        out_channels: int = 6,
        backbone: str = "resnet50",
        load_pretrained: bool = True,
    ) -> None:
        super().__init__()
        if backbone.lower() != "resnet50":
            raise ValueError(
                "the frozen Task 1 DeepLabV3+ baseline supports backbone=resnet50 only"
            )
        self.encoder = ResNet50Encoder(load_pretrained=load_pretrained)
        self.decoder = DeepLabV3PlusDecoder(out_channels=out_channels)

    def encoder_parameters(self) -> Iterator[nn.Parameter]:
        return self.encoder.parameters()

    def decoder_parameters(self) -> Iterator[nn.Parameter]:
        return self.decoder.parameters()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_size = x.shape[-2:]
        low_level, high_level = self.encoder(x)
        logits = self.decoder(low_level, high_level)
        if logits.shape[-2:] != input_size:
            logits = F.interpolate(
                logits,
                size=input_size,
                mode="bilinear",
                align_corners=False,
            )
        return logits
