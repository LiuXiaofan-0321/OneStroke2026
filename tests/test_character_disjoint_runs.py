from __future__ import annotations

import json
from pathlib import Path

import yaml

from onestroke_model.character_disjoint_runs import build_character_disjoint_run_plan
from onestroke_model.reproducibility import sha256_file


def test_run_plan_marks_missing_data_and_task1_without_executing(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "sample_id,char_id,has_all_masks,errors,image_path,vec1_path,vec2_path,"
        "vec3_path,vec4_path,vec5_path,keypoint_path\n"
        "a,1,true,,missing,missing,missing,missing,missing,missing,missing\n",
        encoding="utf-8",
    )
    split = tmp_path / "splits.csv"
    split.write_text("sample_id,char_id,split\na,1,train\n", encoding="utf-8")
    report = {
        "split_csv": str(split),
        "split_sha256": sha256_file(split),
        "assertions": {"train_test_character_overlap_zero": True},
        "actual_character_counts": {"train": 1, "val": 0, "test": 0},
        "actual_sample_counts": {"train": 1, "val": 0, "test": 0},
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    unet = {
        "experiment_name": "unet",
        "seed": 1,
        "data": {"manifest": "manifest.csv"},
        "model": {"name": "unet"},
        "output_dir": "runs/unet",
    }
    deeplab = {
        "research_status": "BLOCKED_BY_TASK1",
        "experiment_name": "deeplab",
        "seed": 1,
        "data": {"manifest": "manifest.csv"},
        "model": {"name": "deeplabv3plus"},
        "output_dir": "runs/deeplab",
    }
    (config_dir / "unet.yaml").write_text(yaml.safe_dump(unet), encoding="utf-8")
    (config_dir / "deeplab.yaml").write_text(yaml.safe_dump(deeplab), encoding="utf-8")
    plan = build_character_disjoint_run_plan(
        tmp_path,
        split_report_path="report.json",
        config_paths=("configs/unet.yaml", "configs/deeplab.yaml"),
        expected_split_sha256=sha256_file(split),
        expected_sample_counts={"train": 1, "val": 0, "test": 0},
        expected_character_counts={"train": 1, "val": 0, "test": 0},
    )
    statuses = {run["model_name"]: run["status"] for run in plan["runs"]}
    assert statuses["unet"] == "BLOCKED_DATA_PATHS"
    assert statuses["deeplabv3plus"] == "BLOCKED_BY_TASK1"
