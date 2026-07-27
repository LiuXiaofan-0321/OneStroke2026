from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from onestroke_model.constants import CHANNELS
from onestroke_model.inference import prepare_image
from onestroke_model.scripts.cache_reference_masks import _load_model
from onestroke_model.style_scoring import save_score_assets, score_masks


def _load_reference(index_path: Path, style_id: str, target_char: str) -> tuple[dict[str, object], np.ndarray]:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if list(index.get("channels", [])) != list(CHANNELS):
        raise ValueError("reference cache channel schema does not match current model schema")
    matches = [
        item for item in index.get("references", [])
        if item["style_id"] == style_id and item["target_char"] == target_char
    ]
    if not matches:
        raise ValueError(f"no approved reference for style_id={style_id!r}, target_char={target_char!r}")
    if len(matches) > 1:
        raise ValueError("multiple references found; multi-reference aggregation is not implemented yet")
    reference = matches[0]
    cache_path = index_path.parent / str(reference["cache_path"])
    with np.load(cache_path) as cache:
        channels = [str(value) for value in cache["channels"].tolist()]
        if channels != list(CHANNELS):
            raise ValueError(f"cached channel schema mismatch: {channels}")
        masks = cache["binary_masks"].astype(bool)
    return reference, masks


def score_reference_style(
    image_path: str | Path,
    style_id: str,
    target_char: str,
    cache_index: str | Path,
    config_path: str | Path,
    checkpoint_path: str | Path,
    output_dir: str | Path,
) -> dict[str, object]:
    if len(target_char) != 1:
        raise ValueError("target_char must contain exactly one Unicode character")
    cache_index = Path(cache_index)
    reference, reference_masks = _load_reference(cache_index, style_id, target_char)
    torch, model, device, config, thresholds = _load_model(config_path, checkpoint_path)
    image_size = int(config.get("data", {}).get("image_size", 512))
    normalization = str(config.get("data", {}).get("normalization", "none"))
    array, _ = prepare_image(image_path, image_size, normalization=normalization)
    with torch.no_grad():
        tensor = torch.from_numpy(array).to(device=device, dtype=torch.float32)
        probabilities = torch.sigmoid(model(tensor)).cpu().numpy()[0]
    user_masks = np.transpose(probabilities, (1, 2, 0)) >= np.asarray(
        [thresholds[channel] for channel in CHANNELS], dtype=np.float32
    ).reshape(1, 1, -1)
    evidence, aligned_reference = score_masks(user_masks, reference_masks)
    evidence.update(
        {
            "model_version": "segformer-b2-v1",
            "style_id": style_id,
            "target_char": target_char,
            "reference_id": reference["reference_id"],
            "cache_index": str(cache_index.resolve()),
            "capabilities": {
                "style_conditioning": True,
                "style_scoring": "prototype_structure_evidence",
                "natural_language_feedback": False,
            },
        }
    )
    save_score_assets(output_dir, evidence, user_masks, aligned_reference)
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Score one user character against one cached same-character reference.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--style-id", required=True)
    parser.add_argument("--target-char", required=True)
    parser.add_argument("--cache-index", default="references/cache/segformer_b2_v1/index.json")
    parser.add_argument("--config", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    result = score_reference_style(
        image_path=args.image,
        style_id=args.style_id,
        target_char=args.target_char,
        cache_index=args.cache_index,
        config_path=args.config,
        checkpoint_path=args.checkpoint,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
