"""Build the frozen three-model qualitative segmentation figure.

The script deliberately refuses missing or hash-mismatched formal checkpoints.
It must never substitute smoke, legacy-release, or randomly initialized model
outputs for the Task 1 models reported in the paper.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from onestroke_model.config import load_yaml
from onestroke_model.constants import CHANNELS
from onestroke_model.data.dataset import _letterbox_image, _letterbox_mask
from onestroke_model.data.transforms import normalize_rgb
from onestroke_model.models import build_model

SEED = 20260811
IMAGE_SIZE = 512
COLORS = np.asarray(
    [
        [214, 39, 40],
        [0, 158, 115],
        [0, 114, 178],
        [230, 159, 0],
        [135, 72, 177],
    ],
    dtype=np.float32,
) / 255.0


@dataclass(frozen=True)
class ModelSpec:
    label: str
    config: str
    checkpoint: str
    thresholds: str
    checkpoint_sha256: str


MODEL_SPECS = {
    "main_qc": (
        ModelSpec(
            "U-Net",
            f"configs/paper_ijdar/main_qc_unet_seed_{SEED}.yaml",
            f"artifacts/paper_ijdar/main_qc/runs/unet_seed_{SEED}/checkpoints/best.pt",
            f"artifacts/paper_ijdar/task1/formal_runs/main_qc_unet_seed_{SEED}/thresholds_val.json",
            "39868d61ac7e02be1e16b6c01b6a832a2dc5cf224d0efa80cc76abbeb0f8b303",
        ),
        ModelSpec(
            "DeepLabV3+",
            f"configs/paper_ijdar/main_qc_deeplabv3plus_seed_{SEED}.yaml",
            f"artifacts/paper_ijdar/main_qc/runs/deeplabv3plus_seed_{SEED}/checkpoints/best.pt",
            f"artifacts/paper_ijdar/task1/formal_runs/main_qc_deeplabv3plus_seed_{SEED}/thresholds_val.json",
            "e3bc8dc37b441a9a85baf11345bd45529b5107cfb1e2dc95c9443933bf80bf62",
        ),
        ModelSpec(
            "SegFormer-B2",
            f"configs/paper_ijdar/main_qc_segformer_b2_seed_{SEED}.yaml",
            f"artifacts/paper_ijdar/main_qc/runs/segformer_b2_seed_{SEED}/checkpoints/best.pt",
            f"artifacts/paper_ijdar/task1/formal_runs/main_qc_segformer_b2_seed_{SEED}/thresholds_val.json",
            "c58c409279372af0c5846e00d74d660d05c0055a4c2d387d9e58bbc03b82dd54",
        ),
    ),
    "character_disjoint": (
        ModelSpec(
            "U-Net",
            f"configs/paper_ijdar/character_disjoint_unet_seed_{SEED}.yaml",
            f"artifacts/paper_ijdar/character_disjoint/runs/unet_seed_{SEED}/checkpoints/best.pt",
            f"artifacts/paper_ijdar/task1/formal_runs/character_disjoint_unet_seed_{SEED}/thresholds_val.json",
            "d89e1b29bdc7a932e66d6e95975c6347e776846ebde75212b5581b46427a1679",
        ),
        ModelSpec(
            "DeepLabV3+",
            f"configs/paper_ijdar/character_disjoint_deeplabv3plus_seed_{SEED}.yaml",
            f"artifacts/paper_ijdar/character_disjoint/runs/deeplabv3plus_seed_{SEED}/checkpoints/best.pt",
            f"artifacts/paper_ijdar/task1/formal_runs/character_disjoint_deeplabv3plus_seed_{SEED}/thresholds_val.json",
            "9f25a4abf3067ee74c023059842dff47a509126ae8872a199ee51beeac63ce05",
        ),
        ModelSpec(
            "SegFormer-B2",
            f"configs/paper_ijdar/character_disjoint_segformer_b2_seed_{SEED}.yaml",
            f"artifacts/paper_ijdar/character_disjoint/runs/segformer_b2_seed_{SEED}/checkpoints/best.pt",
            f"artifacts/paper_ijdar/task1/formal_runs/character_disjoint_segformer_b2_seed_{SEED}/thresholds_val.json",
            "922f415a38c30b1972d852404886156eb51b633e91a45218befae4636dd1fb56",
        ),
    ),
}

CASES = (
    ("Crossing", "33/18", "main_qc"),
    ("Endpoint-rich", "35/20", "main_qc"),
    ("Unseen character", "6/18", "character_disjoint"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_manifest(root: Path) -> dict[str, dict[str, str]]:
    path = root / "artifacts/data_qc/manifest_qc_v1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return {row["sample_id"]: row for row in csv.DictReader(stream)}


def load_case(root: Path, row: dict[str, str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    image = Image.open(resolve(root, row["image_path"])).convert("RGB")
    boxed = _letterbox_image(image, IMAGE_SIZE, Image.Resampling.BILINEAR)
    display = np.asarray(boxed, dtype=np.uint8)
    tensor = normalize_rgb(boxed, "imagenet")
    masks = np.stack(
        [
            _letterbox_mask(np.load(resolve(root, row[f"{channel}_path"])), IMAGE_SIZE)
            for channel in CHANNELS
        ],
        axis=0,
    ).astype(bool)
    return display, tensor, masks


def load_thresholds(path: Path) -> np.ndarray:
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload["best_thresholds"]
    return np.asarray([values[channel] for channel in CHANNELS], dtype=np.float32)


def predict(
    root: Path,
    spec: ModelSpec,
    tensors: list[np.ndarray],
    device: str,
) -> list[np.ndarray]:
    checkpoint_path = resolve(root, spec.checkpoint)
    thresholds_path = resolve(root, spec.thresholds)
    for required in (checkpoint_path, thresholds_path):
        if not required.is_file():
            raise FileNotFoundError(
                f"Missing formal artifact: {required}. Recover the frozen Task 1 file; "
                "do not substitute another checkpoint."
            )
    actual_hash = sha256_file(checkpoint_path)
    if actual_hash != spec.checkpoint_sha256:
        raise ValueError(
            f"Checkpoint hash mismatch for {checkpoint_path}: "
            f"expected {spec.checkpoint_sha256}, got {actual_hash}"
        )

    import torch

    config = load_yaml(resolve(root, spec.config))
    model = build_model(config["model"], load_pretrained=False)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state"])
    model.to(device).eval()
    thresholds = load_thresholds(thresholds_path).reshape(1, 6, 1, 1)

    batch = torch.from_numpy(np.stack(tensors)).to(device)
    with torch.no_grad():
        probabilities = torch.sigmoid(model(batch)).cpu().numpy()
    del model, checkpoint, batch
    if device.startswith("cuda"):
        torch.cuda.empty_cache()
    return [mask.astype(bool) for mask in probabilities >= thresholds]


def prediction_cache_path(
    cache_dir: Path,
    split_name: str,
    spec: ModelSpec,
) -> Path:
    model_name = spec.label.lower().replace("+", "plus").replace("-", "_")
    return cache_dir / f"{split_name}_{model_name}_seed_{SEED}.npz"


def load_or_predict(
    root: Path,
    split_name: str,
    spec: ModelSpec,
    sample_ids: list[str],
    tensors: list[np.ndarray],
    device: str,
    cache_dir: Path,
) -> list[np.ndarray]:
    checkpoint_path = resolve(root, spec.checkpoint)
    actual_hash = sha256_file(checkpoint_path)
    if actual_hash != spec.checkpoint_sha256:
        raise ValueError(
            f"Checkpoint hash mismatch for {checkpoint_path}: "
            f"expected {spec.checkpoint_sha256}, got {actual_hash}"
        )

    cache_path = prediction_cache_path(cache_dir, split_name, spec)
    if cache_path.is_file():
        cached = np.load(cache_path, allow_pickle=False)
        cached_ids = cached["sample_ids"].astype(str).tolist()
        cached_hash = str(cached["checkpoint_sha256"].item())
        if cached_ids == sample_ids and cached_hash == actual_hash:
            print(f"prediction_cache_hit={cache_path}", flush=True)
            return [mask.astype(bool) for mask in cached["masks"]]

    print(
        f"predicting split={split_name} model={spec.label} "
        f"samples={len(sample_ids)} device={device}",
        flush=True,
    )
    masks = predict(root, spec, tensors, device)
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_path,
        sample_ids=np.asarray(sample_ids),
        checkpoint_sha256=np.asarray(actual_hash),
        masks=np.stack(masks).astype(np.uint8),
    )
    print(f"prediction_cache_written={cache_path}", flush=True)
    return masks


def composite(masks: np.ndarray) -> np.ndarray:
    direction = masks[:5].astype(bool)
    count = direction.sum(axis=0)
    canvas = np.ones((IMAGE_SIZE, IMAGE_SIZE, 3), dtype=np.float32)
    for channel, color in enumerate(COLORS):
        canvas[direction[channel]] = color
    canvas[count > 1] = 0.05
    keypoint = masks[5].astype(bool)
    if keypoint.any():
        padded = np.pad(keypoint, 2)
        dilated = np.zeros_like(keypoint)
        for dy in range(5):
            for dx in range(5):
                dilated |= padded[dy : dy + IMAGE_SIZE, dx : dx + IMAGE_SIZE]
        canvas[dilated] = np.asarray([0.0, 0.75, 0.2])
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("segmentation_qualitative.pdf"),
    )
    parser.add_argument(
        "--prediction-cache",
        type=Path,
        default=Path("artifacts/paper_ijdar/segmentation_qualitative/cache"),
    )
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = read_manifest(root)

    prepared: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for _, sample_id, _ in CASES:
        prepared[sample_id] = load_case(root, manifest[sample_id])

    predictions: dict[tuple[str, str], np.ndarray] = {}
    for split_name, specs in MODEL_SPECS.items():
        split_cases = [case for case in CASES if case[2] == split_name]
        sample_ids = [sample_id for _, sample_id, _ in split_cases]
        tensors = [prepared[sample_id][1] for _, sample_id, _ in split_cases]
        for spec in specs:
            masks = load_or_predict(
                root,
                split_name,
                spec,
                sample_ids,
                tensors,
                args.device,
                resolve(root, args.prediction_cache),
            )
            for (_, sample_id, _), mask in zip(split_cases, masks, strict=True):
                predictions[(sample_id, spec.label)] = mask

    columns = ("Input", "Ground truth", "U-Net", "DeepLabV3+", "SegFormer-B2")
    figure, axes = plt.subplots(len(CASES), len(columns), figsize=(12.0, 7.15))
    for row_index, (case_name, sample_id, split_name) in enumerate(CASES):
        display, _, ground_truth = prepared[sample_id]
        panels = [
            display,
            composite(ground_truth),
            composite(predictions[(sample_id, "U-Net")]),
            composite(predictions[(sample_id, "DeepLabV3+")]),
            composite(predictions[(sample_id, "SegFormer-B2")]),
        ]
        for column_index, (title, panel) in enumerate(zip(columns, panels, strict=True)):
            axis = axes[row_index, column_index]
            axis.imshow(panel)
            axis.set_xticks([])
            axis.set_yticks([])
            if row_index == 0:
                axis.set_title(title, fontsize=10, fontweight="bold")
            if column_index == 0:
                axis.set_ylabel(
                    f"{case_name}\n{sample_id}\n{split_name.replace('_', '-')}",
                    fontsize=9,
                )
            for spine in axis.spines.values():
                spine.set_linewidth(0.5)
                spine.set_color("#777777")

    figure.text(
        0.5,
        0.012,
        "Red=vec1, green=vec2, blue=vec3, orange=vec4, purple=vec5, "
        "black=multi-channel overlap, bright green=endpoints. Seed 20260811.",
        ha="center",
        fontsize=8,
    )
    figure.tight_layout(rect=(0.02, 0.035, 1.0, 1.0), pad=0.7)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, bbox_inches="tight")
    figure.savefig(args.output.with_suffix(".png"), dpi=220, bbox_inches="tight")
    plt.close(figure)
    print(args.output)


if __name__ == "__main__":
    main()
