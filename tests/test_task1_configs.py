from __future__ import annotations

from pathlib import Path

import yaml

from onestroke_model.scripts.generate_task1_configs import (
    MODELS,
    QC_CONTRACT_SHA256,
    SEEDS,
    SPLITS,
    build_config,
    generate_configs,
)


def test_task1_config_matrix_contains_eighteen_unique_runs(tmp_path: Path) -> None:
    paths = generate_configs(tmp_path)
    assert len(paths) == 18
    assert len({path.name for path in paths}) == 18
    experiments = {
        yaml.safe_load(path.read_text(encoding="utf-8"))["experiment_name"]
        for path in paths
    }
    assert len(experiments) == 18


def test_task1_configs_share_frozen_protocol() -> None:
    for split_name, split in SPLITS.items():
        for model_key in MODELS:
            for seed in SEEDS:
                config = build_config(split_name, model_key, seed)
                data = config["data"]
                assert data["expected_splits_sha256"] == split["sha256"]
                assert data["expected_split_counts"] == split["counts"]
                assert data["expected_qc_exclusions_sha256"] == QC_CONTRACT_SHA256
                assert data["normalization"] == "imagenet"
                assert data["augmentation"]["enabled"] is True
                assert config["loss"]["boundary_weight"] == 0.2
                assert config["optim"]["epochs"] == 120
                assert config["optim"]["early_stop_patience"] == 15
                assert config["seed"] == seed
