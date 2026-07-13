"""Tune one independent sigmoid threshold per channel on the validation split."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from onestroke_model.config import load_yaml
from onestroke_model.constants import CHANNELS
from onestroke_model.utils.io import write_json


def _require_torch():
    try:
        import torch
    except ImportError as exc:
        raise SystemExit("PyTorch is required. Run: python -m pip install -e '.[train]'") from exc
    return torch


def _device(name: str, torch_module):
    if name != "auto":
        return torch_module.device(name)
    if torch_module.cuda.is_available():
        return torch_module.device("cuda")
    mps = getattr(torch_module.backends, "mps", None)
    if mps is not None and mps.is_available():
        return torch_module.device("mps")
    return torch_module.device("cpu")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate six independent thresholds using validation Dice.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-threshold", type=float, default=0.10)
    parser.add_argument("--max-threshold", type=float, default=0.90)
    parser.add_argument("--steps", type=int, default=17)
    args = parser.parse_args()
    if not 0 < args.min_threshold < args.max_threshold < 1 or args.steps < 2:
        raise ValueError("threshold range must satisfy 0 < min < max < 1 and steps >= 2")

    cfg = load_yaml(args.config)
    torch = _require_torch()
    from onestroke_model.data.dataset import make_torch_loader
    from onestroke_model.models import build_model

    device = _device(str(cfg.get("device", "auto")), torch)
    data_cfg = cfg["data"]
    loader = make_torch_loader(
        data_cfg["manifest"],
        data_cfg["splits"],
        "val",
        int(data_cfg.get("image_size", 512)),
        int(data_cfg.get("batch_size", 4)),
        int(data_cfg.get("num_workers", 0)),
        shuffle=False,
        normalization=str(data_cfg.get("normalization", "none")),
    )
    model = build_model(cfg["model"]).to(device)
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    grid = np.linspace(args.min_threshold, args.max_threshold, args.steps, dtype=np.float32)
    tp = np.zeros((len(CHANNELS), len(grid)), dtype=np.float64)
    fp = np.zeros_like(tp)
    fn = np.zeros_like(tp)
    with torch.no_grad():
        for batch in loader:
            images = batch["image"].to(device=device, dtype=torch.float32)
            targets = batch["mask"].numpy() > 0.5
            probabilities = torch.sigmoid(model(images)).cpu().numpy()
            for channel_index in range(len(CHANNELS)):
                target = targets[:, channel_index]
                for threshold_index, threshold in enumerate(grid):
                    prediction = probabilities[:, channel_index] >= threshold
                    tp[channel_index, threshold_index] += np.logical_and(prediction, target).sum()
                    fp[channel_index, threshold_index] += np.logical_and(prediction, ~target).sum()
                    fn[channel_index, threshold_index] += np.logical_and(~prediction, target).sum()

    dice = (2 * tp) / np.maximum(2 * tp + fp + fn, 1.0)
    best_indexes = dice.argmax(axis=1)
    best_thresholds = {channel: float(grid[best_indexes[i]]) for i, channel in enumerate(CHANNELS)}
    result = {
        "calibration_split": "val",
        "checkpoint": str(Path(args.checkpoint).resolve()),
        "threshold_grid": grid.tolist(),
        "best_thresholds": best_thresholds,
        "best_dice": {channel: float(dice[i, best_indexes[i]]) for i, channel in enumerate(CHANNELS)},
        "dice_by_channel": {channel: dice[i].tolist() for i, channel in enumerate(CHANNELS)},
    }
    write_json(args.output, result)
    print("best_thresholds=", best_thresholds)


if __name__ == "__main__":
    main()
