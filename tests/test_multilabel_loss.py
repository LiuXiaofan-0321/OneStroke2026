from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from onestroke_model.losses.multilabel import MultiLabelStrokeLoss


def test_multilabel_loss_supports_backward_with_boundary_supervision() -> None:
    logits = torch.zeros((2, 6, 16, 16), requires_grad=True)
    targets = torch.zeros_like(logits)
    targets[:, 0, 3:12, 7:9] = 1
    targets[:, 1, 7:9, 3:12] = 1
    targets[:, 5, 3:5, 3:5] = 1
    loss_fn = MultiLabelStrokeLoss(direction_pos_weight=[50, 60, 70, 80, 90], boundary_weight=0.2)

    loss = loss_fn(logits, targets)
    loss.backward()

    assert torch.isfinite(loss)
    assert logits.grad is not None
    assert torch.isfinite(logits.grad).all()
