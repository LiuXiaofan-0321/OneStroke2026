from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from onestroke_model.models import build_model


def test_deeplabv3plus_has_six_full_resolution_logits() -> None:
    model = build_model(
        {
            "name": "deeplabv3plus",
            "backbone": "resnet50",
            "out_channels": 6,
        },
        load_pretrained=False,
    )
    model.eval()
    inputs = torch.randn(1, 3, 64, 64)
    with torch.no_grad():
        logits = model(inputs)
    assert logits.shape == (1, 6, 64, 64)


def test_deeplabv3plus_parameter_groups_are_disjoint() -> None:
    model = build_model(
        {
            "name": "deeplabv3plus",
            "backbone": "resnet50",
            "out_channels": 6,
        },
        load_pretrained=False,
    )
    encoder = {id(parameter) for parameter in model.encoder_parameters()}
    decoder = {id(parameter) for parameter in model.decoder_parameters()}
    assert encoder
    assert decoder
    assert not encoder & decoder
    assert encoder | decoder == {id(parameter) for parameter in model.parameters()}
