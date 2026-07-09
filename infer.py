from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from onestroke_model.config import load_yaml
from onestroke_model.constants import CHANNELS
from onestroke_model.inference import now_ms, package_prediction, prepare_image, restore_letterbox_probabilities


def _require_torch():
    try:
        import torch
    except ImportError as exc:
        raise SystemExit("PyTorch is required for inference. Run: python -m pip install -e '.[train]'") from exc
    return torch


def _device(name: str, torch_module):
    if name == "auto":
        return torch_module.device("cuda" if torch_module.cuda.is_available() else "cpu")
    return torch_module.device(name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run single-image inference.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", default=None, help="Optional .npz output path.")
    args = parser.parse_args()
    cfg = load_yaml(args.config)
    torch = _require_torch()
    from onestroke_model.models import build_model

    device = _device(str(cfg.get("device", "auto")), torch)
    image_size = int(cfg.get("data", {}).get("image_size", 512))
    thresholds = cfg.get("thresholds", {c: 0.5 for c in CHANNELS})
    model = build_model(cfg["model"]).to(device)
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    arr, original_size = prepare_image(args.image, image_size)
    start = now_ms()
    with torch.no_grad():
        tensor = torch.from_numpy(arr).to(device=device, dtype=torch.float32)
        probs = torch.sigmoid(model(tensor)).cpu().numpy()[0]
    latency_ms = now_ms() - start
    probs_hwc = np.transpose(probs, (1, 2, 0))
    restored = restore_letterbox_probabilities(probs_hwc, original_size)
    packaged = package_prediction(restored, thresholds=thresholds, latency_ms=latency_ms)
    print(
        {
            "channels": packaged["channels"],
            "probability_shape": list(restored.shape),
            "latency_ms": round(latency_ms, 2),
            "thresholds": thresholds,
        }
    )
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            out,
            probabilities=packaged["probabilities"],
            binary_masks=packaged["binary_masks"],
            channels=np.array(packaged["channels"]),
            thresholds=np.array([thresholds[c] for c in CHANNELS], dtype=np.float32),
            latency_ms=np.array([latency_ms], dtype=np.float32),
        )


if __name__ == "__main__":
    main()
