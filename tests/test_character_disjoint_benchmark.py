from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from onestroke_model.character_disjoint_benchmark import (
    run_character_disjoint_benchmark,
    summarize_character_disjoint_runs,
)
from onestroke_model.reproducibility import sha256_file


def _fixture_project(tmp_path: Path) -> tuple[Path, Path, tuple[str, ...]]:
    sample_ids = ("a", "b", "c")
    manifest_rows = [
        (
            f"{sample_id},true,,{tmp_path / f'{sample_id}.jpg'},"
            + ",".join(str(tmp_path / f"{sample_id}_{index}.npy") for index in range(6))
        )
        for sample_id in sample_ids
    ]
    for sample_id in sample_ids:
        (tmp_path / f"{sample_id}.jpg").write_bytes(b"x")
        for index in range(6):
            (tmp_path / f"{sample_id}_{index}.npy").write_bytes(b"x")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "sample_id,has_all_masks,errors,image_path,vec1_path,vec2_path,"
        "vec3_path,vec4_path,vec5_path,keypoint_path\n"
        + "\n".join(manifest_rows)
        + "\n",
        encoding="utf-8",
    )
    split = tmp_path / "splits.csv"
    split.write_text(
        "sample_id,char_id,split\n"
        "a,1,train\n"
        "b,2,val\n"
        "c,3,test\n",
        encoding="utf-8",
    )
    report = {
        "split_csv": str(split),
        "split_sha256": sha256_file(split),
        "assertions": {
            "train_val_character_overlap_zero": True,
            "train_test_character_overlap_zero": True,
            "val_test_character_overlap_zero": True,
            "all_usable_samples_assigned_once": True,
        },
        "actual_character_counts": {"train": 1, "val": 1, "test": 1},
        "actual_sample_counts": {"train": 1, "val": 1, "test": 1},
    }
    report_path = tmp_path / "split_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    config = {
        "experiment_name": "unet_seed_1",
        "seed": 1,
        "data": {"manifest": str(manifest), "splits": str(split)},
        "model": {"name": "unet"},
        "output_dir": "runs/unet_seed_1",
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return report_path, config_path, sample_ids


def test_benchmark_defaults_to_dry_run_and_never_calls_training(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_path, config_path, _ = _fixture_project(tmp_path)
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("training command must not run in dry-run")

    monkeypatch.setattr(
        "onestroke_model.character_disjoint_benchmark._run_command",
        fail_if_called,
    )
    split_hash = json.loads(report_path.read_text())["split_sha256"]
    plan = run_character_disjoint_benchmark(
        tmp_path,
        split_report_path=report_path,
        config_paths=(config_path,),
        expected_split_sha256=split_hash,
        expected_sample_counts={"train": 1, "val": 1, "test": 1},
        expected_character_counts={"train": 1, "val": 1, "test": 1},
    )
    assert plan["training_executed"] is False
    assert plan["requested_execute"] is False
    assert called is False


def test_summary_requires_validation_calibration(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs/unet"
    (run_dir / "checkpoints").mkdir(parents=True)
    (run_dir / "test_metrics.json").write_text(
        json.dumps({"split": "test", "macro_dice": 0.5}),
        encoding="utf-8",
    )
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump({"output_dir": str(run_dir)}),
        encoding="utf-8",
    )
    plan = {
        "project_root": str(tmp_path),
        "runs": [
            {
                "status": "READY",
                "experiment_name": "unet",
                "model_name": "unet",
                "seed": 1,
                "config": str(config),
                "config_sha256": sha256_file(config),
            }
        ],
    }
    with pytest.raises(ValueError, match="validation thresholds"):
        summarize_character_disjoint_runs(plan, tmp_path / "summary")
