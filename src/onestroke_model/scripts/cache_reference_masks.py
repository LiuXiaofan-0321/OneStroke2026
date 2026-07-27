from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from onestroke_model.config import load_yaml
from onestroke_model.constants import CHANNELS, SCHEMA_VERSION
from onestroke_model.inference import prepare_image
from onestroke_model.utils.io import ensure_dir, read_csv_rows, write_json


def _require_torch():
    try:
        import torch
    except ImportError as exc:
        raise SystemExit("PyTorch is required. Run: python -m pip install -e '.[train]'") from exc
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_model(config_path: str | Path, checkpoint_path: str | Path):
    torch = _require_torch()
    from onestroke_model.models import build_model

    config = load_yaml(config_path)
    device = _device(str(config.get("device", "auto")), torch)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model_cfg = checkpoint.get("config", {}).get("model", config["model"])
    model = build_model(model_cfg, load_pretrained=False).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    thresholds = {channel: float(config.get("thresholds", {}).get(channel, 0.5)) for channel in CHANNELS}
    return torch, model, device, config, thresholds


def cache_reference_masks(
    manifest_path: str | Path,
    config_path: str | Path,
    checkpoint_path: str | Path,
    cache_dir: str | Path,
    output_index: str | Path,
    batch_size: int = 4,
    limit: int = 0,
    model_version: str = "segformer-b2-v1",
) -> dict[str, object]:
    manifest_path = Path(manifest_path)
    checkpoint_path = Path(checkpoint_path)
    cache_dir = ensure_dir(cache_dir)
    output_index = Path(output_index)
    rows = [row for row in read_csv_rows(manifest_path) if row.get("review_status", "").lower() == "approved"]
    if limit > 0:
        rows = rows[:limit]
    if not rows:
        raise ValueError("manifest contains no approved reference rows")
    torch, model, device, config, thresholds = _load_model(config_path, checkpoint_path)
    image_size = int(config.get("data", {}).get("image_size", 512))
    normalization = str(config.get("data", {}).get("normalization", "none"))
    threshold_array = np.asarray([thresholds[channel] for channel in CHANNELS], dtype=np.float32).reshape(1, 1, 1, -1)
    entries: list[dict[str, object]] = []

    for start in range(0, len(rows), batch_size):
        batch_rows = rows[start : start + batch_size]
        arrays = []
        for row in batch_rows:
            image_path = manifest_path.parent / row["image_path"]
            array, _ = prepare_image(image_path, image_size, normalization=normalization)
            arrays.append(array)
        inputs = np.concatenate(arrays, axis=0)
        with torch.no_grad():
            tensor = torch.from_numpy(inputs).to(device=device, dtype=torch.float32)
            probabilities = torch.sigmoid(model(tensor)).cpu().numpy()
        masks = np.transpose(probabilities, (0, 2, 3, 1)) >= threshold_array
        for row, mask in zip(batch_rows, masks, strict=True):
            reference_id = row["reference_id"]
            filename = hashlib.sha256(reference_id.encode("utf-8")).hexdigest()[:20] + ".npz"
            output_dir = ensure_dir(cache_dir / row["style_id"])
            output_path = output_dir / filename
            np.savez_compressed(
                output_path,
                binary_masks=mask.astype(np.uint8),
                channels=np.asarray(CHANNELS),
                thresholds=np.asarray([thresholds[channel] for channel in CHANNELS], dtype=np.float32),
            )
            entries.append(
                {
                    "reference_id": reference_id,
                    "style_id": row["style_id"],
                    "target_char": row["target_char"],
                    "cache_path": os.path.relpath(output_path, output_index.parent).replace("\\", "/"),
                    "source_image_path": row["image_path"],
                }
            )
        print(f"cached={min(start + len(batch_rows), len(rows))}/{len(rows)}")

    report = {
        "schema_version": SCHEMA_VERSION,
        "cache_format": "binary_masks_hwc_uint8",
        "model_version": model_version,
        "checkpoint": str(checkpoint_path.resolve()),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "config": str(Path(config_path).resolve()),
        "channels": list(CHANNELS),
        "thresholds": thresholds,
        "canvas_size": image_size,
        "normalization": normalization,
        "num_references": len(entries),
        "references": entries,
    }
    write_json(output_index, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache B2 binary masks for approved reference characters.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--cache-dir", default="references/cache/segformer_b2_v1")
    parser.add_argument("--output-index", default="references/cache/segformer_b2_v1/index.json")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="Optional smoke-test limit.")
    parser.add_argument("--model-version", default="segformer-b2-v1")
    args = parser.parse_args()
    report = cache_reference_masks(
        manifest_path=args.manifest,
        config_path=args.config,
        checkpoint_path=args.checkpoint,
        cache_dir=args.cache_dir,
        output_index=args.output_index,
        batch_size=args.batch_size,
        limit=args.limit,
        model_version=args.model_version,
    )
    print(json.dumps({key: report[key] for key in ("num_references", "canvas_size", "checkpoint_sha256")}, indent=2))


if __name__ == "__main__":
    main()
