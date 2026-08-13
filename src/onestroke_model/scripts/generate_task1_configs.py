"""Generate the frozen 18-run Task 1 configuration matrix."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

import yaml

SEEDS = (20260811, 314159, 271828)
MANIFEST_SHA256 = "c55803a2381aa37e2a88c72b770be32036353e7b659986bf58f6591beba5edb4"
QC_CONTRACT_SHA256 = "bd2b0641d0e6f53f6f18f6604232c02ff99e9d989eb39125f6a9af41e8573a1a"

SPLITS = {
    "main_qc": {
        "splits": "artifacts/data_qc/standard_splits_qc_v1.csv",
        "sha256": "d79e48c264ac2b5431eb5543ddae798efc1542482e6ca76369eb78c155cc7b18",
        "counts": {"train": 530, "val": 119, "test": 120},
    },
    "character_disjoint": {
        "splits": "artifacts/data_qc/character_disjoint_splits_qc_v1.csv",
        "sha256": "e9303314d1b70d3f92efcdc5c0807f833148cbe64c2702379f0ac951ed2a1e2b",
        "counts": {"train": 539, "val": 114, "test": 116},
    },
}

MODELS = {
    "unet": {
        "batch_size": 8,
        "model": {
            "name": "unet",
            "in_channels": 3,
            "out_channels": 6,
            "base_channels": 32,
        },
        "optim": {"lr": 3e-4},
    },
    "deeplabv3plus": {
        "batch_size": 4,
        "model": {
            "name": "deeplabv3plus",
            "backbone": "resnet50",
            "out_channels": 6,
        },
        "optim": {
            "encoder_lr": 1e-4,
            "decoder_lr": 1e-3,
        },
    },
    "segformer_b2": {
        "batch_size": 4,
        "model": {
            "name": "segformer",
            "backbone": "nvidia/segformer-b2-finetuned-ade-512-512",
            "out_channels": 6,
            "freeze_encoder": False,
            "decoder_lr_scale": 10.0,
        },
        "optim": {
            "encoder_lr": 3e-5,
            "decoder_lr": 3e-4,
        },
    },
}


def _common_loss() -> dict[str, object]:
    return {
        "direction": {
            "bce_weight": 1.0,
            "dice_weight": 1.0,
            "pos_weight": "auto",
            "pos_weight_max_samples": 200,
            "pos_weight_max": 100.0,
        },
        "keypoint": {
            "loss_type": "focal",
            "focal_weight": 1.0,
            "dice_weight": 1.0,
            "focal_gamma": 2.0,
            "focal_alpha": 0.75,
        },
        "boundary_weight": 0.2,
    }


def _common_augmentation() -> dict[str, object]:
    return {
        "enabled": True,
        "translate_px": 12,
        "scale_min": 0.9,
        "scale_max": 1.1,
        "brightness_min": 0.85,
        "brightness_max": 1.15,
        "contrast_min": 0.9,
        "contrast_max": 1.1,
        "blur_probability": 0.15,
        "blur_radius_min": 0.1,
        "blur_radius_max": 0.8,
    }


def build_config(split_name: str, model_key: str, seed: int) -> dict[str, object]:
    split = SPLITS[split_name]
    model = MODELS[model_key]
    experiment_name = f"{split_name}_{model_key}_seed_{seed}"
    optim = {
        "name": "adamw",
        **copy.deepcopy(model["optim"]),
        "weight_decay": 0.01,
        "epochs": 120,
        "early_stop_patience": 15,
        "amp": True,
        "scheduler": "cosine",
        "min_lr": 1e-6,
        "warmup_epochs": 3,
        "warmup_start_factor": 0.1,
        "grad_clip_norm": 1.0,
    }
    return {
        "experiment_name": experiment_name,
        "seed": seed,
        "device": "auto",
        "data": {
            "manifest": "artifacts/data_qc/manifest_qc_v1.csv",
            "splits": split["splits"],
            "image_size": 512,
            "batch_size": model["batch_size"],
            "num_workers": 4,
            "normalization": "imagenet",
            "augmentation": _common_augmentation(),
            "qc_exclusions": (
                "artifacts/data_qc/dataset_qc_exclusion_contract_v1.csv"
            ),
            "expected_manifest_sha256": MANIFEST_SHA256,
            "expected_splits_sha256": split["sha256"],
            "expected_qc_exclusions_sha256": QC_CONTRACT_SHA256,
            "expected_split_counts": copy.deepcopy(split["counts"]),
        },
        "model": copy.deepcopy(model["model"]),
        "loss": _common_loss(),
        "optim": optim,
        "thresholds": {
            "vec1": 0.5,
            "vec2": 0.5,
            "vec3": 0.5,
            "vec4": 0.5,
            "vec5": 0.5,
            "keypoint": 0.45,
        },
        "output_dir": (
            f"artifacts/paper_ijdar/{split_name}/runs/"
            f"{model_key}_seed_{seed}"
        ),
    }


def generate_configs(output_dir: str | Path) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for split_name in SPLITS:
        for model_key in MODELS:
            for seed in SEEDS:
                path = output / f"{split_name}_{model_key}_seed_{seed}.yaml"
                payload = yaml.safe_dump(
                    build_config(split_name, model_key, seed),
                    sort_keys=False,
                    allow_unicode=True,
                )
                path.write_text(payload, encoding="utf-8")
                generated.append(path)
    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("configs/paper_ijdar"),
    )
    args = parser.parse_args()
    for path in generate_configs(args.output_dir):
        print(path.as_posix())


if __name__ == "__main__":
    main()
