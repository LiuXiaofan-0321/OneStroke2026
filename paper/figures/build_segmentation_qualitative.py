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

from figure_style import (
    GRID,
    INK,
    MUTED,
    configure_matplotlib,
    direction_composite,
)
from onestroke_model.config import load_yaml
from onestroke_model.constants import CHANNELS
from onestroke_model.data.dataset import _letterbox_image, _letterbox_mask
from onestroke_model.data.transforms import normalize_rgb
from onestroke_model.models import build_model

configure_matplotlib()

SEED = 20260811
IMAGE_SIZE = 512


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

SPLIT_LABELS = {
    "main_qc": "QC-standard",
    "character_disjoint": "character-disjoint",
}


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("figure4_segmentation_qualitative.pdf"),
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
    figure, axes = plt.subplots(len(CASES), len(columns), figsize=(11.5, 6.75))
    figure.suptitle(
        "Overlapping stroke parsing under crossings, sparse endpoints, and unseen characters",
        x=0.53,
        y=0.992,
        fontsize=12.2,
        fontweight="bold",
        color=INK,
    )
    for row_index, (case_name, sample_id, split_name) in enumerate(CASES):
        display, _, ground_truth = prepared[sample_id]
        panels = [
            display,
            direction_composite(ground_truth),
            direction_composite(predictions[(sample_id, "U-Net")]),
            direction_composite(predictions[(sample_id, "DeepLabV3+")]),
            direction_composite(predictions[(sample_id, "SegFormer-B2")]),
        ]
        for column_index, (title, panel) in enumerate(zip(columns, panels, strict=True)):
            axis = axes[row_index, column_index]
            axis.imshow(panel)
            axis.set_xticks([])
            axis.set_yticks([])
            if row_index == 0:
                axis.set_title(title, fontsize=9.2, fontweight="bold", pad=5)
            if column_index == 0:
                axis.set_ylabel(
                    f"{case_name}\n{SPLIT_LABELS[split_name]}\nsample {sample_id}",
                    fontsize=8.1,
                    color=INK,
                    labelpad=7,
                )
                axis.text(
                    -0.18,
                    1.02,
                    f"({chr(ord('a') + row_index)})",
                    transform=axis.transAxes,
                    ha="left",
                    va="bottom",
                    fontsize=9.2,
                    fontweight="bold",
                    color=INK,
                    clip_on=False,
                )
            for spine in axis.spines.values():
                spine.set_linewidth(0.55)
                spine.set_color(GRID)

    figure.text(
        0.5,
        0.013,
        "vec1 vertical (red) | vec2 rising diagonal (green) | "
        "vec3 horizontal (blue) | vec4 falling diagonal (orange) | "
        "vec5 compound/curved/other (purple)",
        ha="center",
        fontsize=7.2,
        color=MUTED,
    )
    figure.text(
        0.5,
        0.0015,
        "black = simultaneous direction labels | cyan outlines = stroke endpoints | "
        "all predictions use formal seed 20260811 checkpoints and validation-calibrated thresholds",
        ha="center",
        fontsize=6.8,
        color=MUTED,
    )
    figure.tight_layout(rect=(0.035, 0.045, 0.998, 0.963), pad=0.75)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        args.output,
        bbox_inches="tight",
        pad_inches=0.035,
        facecolor="white",
    )
    figure.savefig(
        args.output.with_suffix(".png"),
        dpi=360,
        bbox_inches="tight",
        pad_inches=0.035,
        facecolor="white",
    )
    plt.close(figure)

    provenance = {
        "schema_version": 1,
        "figure": "Figure 4",
        "selection_policy": (
            "Cases are fixed in source code by prespecified evidence type; "
            "they are not selected after viewing model predictions."
        ),
        "seed": SEED,
        "image_size": IMAGE_SIZE,
        "cases": [
            {
                "case": case_name,
                "sample_id": sample_id,
                "evaluation_protocol": split_name,
            }
            for case_name, sample_id, split_name in CASES
        ],
        "models": [
            {
                "evaluation_protocol": split_name,
                "model": spec.label,
                "config": spec.config,
                "checkpoint": spec.checkpoint,
                "checkpoint_sha256": spec.checkpoint_sha256,
                "thresholds": spec.thresholds,
                "thresholds_sha256": sha256_file(resolve(root, spec.thresholds)),
            }
            for split_name, specs in MODEL_SPECS.items()
            for spec in specs
        ],
        "outputs": {
            "pdf": str(args.output),
            "png": str(args.output.with_suffix(".png")),
        },
    }
    provenance_path = args.output.with_suffix(".provenance.json")
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    print(provenance_path)


if __name__ == "__main__":
    main()
