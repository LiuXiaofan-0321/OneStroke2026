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
        raise SystemExit("PyTorch is required for evaluation. Run: python -m pip install -e '.[train]'") from exc
    return torch


def _device(name: str, torch_module):
    if name == "auto":
        if torch_module.cuda.is_available():
            return torch_module.device("cuda")
        mps = getattr(torch_module.backends, "mps", None)
        if mps is not None and mps.is_available():
            return torch_module.device("mps")
        return torch_module.device("cpu")
    return torch_module.device(name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a checkpoint with fixed segmentation metrics.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    cfg = load_yaml(args.config)
    torch = _require_torch()
    from onestroke_model.data.dataset import make_torch_loader
    from onestroke_model.metrics.segmentation import SegmentationMeter
    from onestroke_model.models import build_model

    device = _device(str(cfg.get("device", "auto")), torch)
    model = build_model(cfg["model"]).to(device)
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    data_cfg = cfg["data"]
    threshold_cfg = cfg.get("thresholds", {})
    threshold_array = np.asarray(
        [float(threshold_cfg.get(channel, 0.5)) for channel in CHANNELS], dtype=np.float32
    ).reshape(1, len(CHANNELS), 1, 1)
    loader = make_torch_loader(
        data_cfg["manifest"],
        data_cfg["splits"],
        args.split,
        int(data_cfg.get("image_size", 512)),
        int(data_cfg.get("batch_size", 4)),
        int(data_cfg.get("num_workers", 0)),
        shuffle=False,
    )
    meter = SegmentationMeter(num_channels=len(CHANNELS))
    with torch.no_grad():
        for batch in loader:
            images = batch["image"].to(device=device, dtype=torch.float32)
            masks = batch["mask"].to(device=device, dtype=torch.float32)
            logits = model(images)
            probs = torch.sigmoid(logits).cpu().numpy()
            targets = masks.cpu().numpy()
            meter.update(probs >= threshold_array, targets > 0.5)
    metrics = meter.compute()
    metrics["split"] = args.split
    metrics["thresholds"] = {channel: float(threshold_array[0, i, 0, 0]) for i, channel in enumerate(CHANNELS)}
    metrics["checkpoint"] = str(Path(args.checkpoint).resolve())
    print(metrics)
    if args.output:
        write_json(args.output, metrics)


if __name__ == "__main__":
    main()
