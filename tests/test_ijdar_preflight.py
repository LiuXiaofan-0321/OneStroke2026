from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from onestroke_model.constants import CHANNELS
from onestroke_model.ijdar_preflight import (
    audit_reference_cache,
    audit_reference_manifest,
    audit_standard_data,
    write_preflight_outputs,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_standard_split_detects_group_safety_and_character_overlap(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    splits = tmp_path / "splits.csv"
    _write_csv(
        manifest,
        [
            {
                "sample_id": "a/0",
                "char_id": "a",
                "has_all_masks": "true",
                "errors": "",
                "image_path": "missing",
                "vec1_path": "missing",
                "vec2_path": "missing",
                "vec3_path": "missing",
                "vec4_path": "missing",
                "vec5_path": "missing",
                "keypoint_path": "missing",
            },
            {
                "sample_id": "a/1",
                "char_id": "a",
                "has_all_masks": "true",
                "errors": "",
                "image_path": "missing",
                "vec1_path": "missing",
                "vec2_path": "missing",
                "vec3_path": "missing",
                "vec4_path": "missing",
                "vec5_path": "missing",
                "keypoint_path": "missing",
            },
        ],
    )
    _write_csv(
        splits,
        [
            {"sample_id": "a/0", "char_id": "a", "group_key": "0", "split": "train"},
            {"sample_id": "a/1", "char_id": "a", "group_key": "1", "split": "test"},
        ],
    )
    report = audit_standard_data(tmp_path, manifest, splits)
    assert report["status"] == "PASS"
    assert report["group_overlap"]["train_test"] == []
    assert report["character_overlap"]["train_test"] == ["a"]
    assert report["standard_split_is_character_disjoint"] is False
    assert report["local_training_data_available"] is False


def test_reference_pair_availability_does_not_invent_same_style_instances(tmp_path: Path) -> None:
    manifest = tmp_path / "references.csv"
    _write_csv(
        manifest,
        [
            {
                "reference_id": "a",
                "style_id": "style_a",
                "target_char": "永",
                "review_status": "approved",
            },
            {
                "reference_id": "b",
                "style_id": "style_b",
                "target_char": "永",
                "review_status": "approved",
            },
        ],
    )
    report = audit_reference_manifest(manifest)
    assert report["pair_support"]["same_character_same_style_different_instance"] is False
    assert report["pair_support"]["same_character_cross_style"] is True


def test_cache_preflight_validates_hwc_binary_schema(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("references/cache/\n", encoding="utf-8")
    cache_dir = tmp_path / "references" / "cache" / "segformer_b2_v1"
    cache_dir.mkdir(parents=True)
    artifact = cache_dir / "mask.npz"
    masks = np.zeros((32, 32, 6), dtype=np.uint8)
    masks[10:20, 10:20, 0] = 1
    np.savez_compressed(artifact, binary_masks=masks, channels=np.asarray(CHANNELS))
    reference_manifest = tmp_path / "references.csv"
    _write_csv(
        reference_manifest,
        [
            {
                "reference_id": "ref-a",
                "style_id": "style-a",
                "target_char": "永",
                "review_status": "approved",
            }
        ],
    )
    index = {
        "schema_version": 1,
        "cache_format": "binary_masks_hwc_uint8",
        "model_version": "segformer-b2-v1",
        "checkpoint_sha256": "abc",
        "channels": list(CHANNELS),
        "canvas_size": 32,
        "num_references": 1,
        "references": [
            {
                "reference_id": "ref-a",
                "style_id": "style-a",
                "target_char": "永",
                "cache_path": "mask.npz",
            }
        ],
    }
    index_path = cache_dir / "index.json"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    report = audit_reference_cache(tmp_path, index_path, reference_manifest)
    assert report["status"] == "PASS"
    assert report["mask_shapes"] == {"(32, 32, 6)": 1}
    assert report["cache_gitignored"] is True


def test_preflight_outputs_include_required_files(tmp_path: Path) -> None:
    report = {
        "git_commit": "abc",
        "task1": {"status": "READY", "components": {}},
        "workflows": {},
        "standard_data": {
            "manifest_rows": 0,
            "usable_rows": 0,
            "split_counts": {},
            "group_overlap": {},
            "character_overlap": {"train_test": []},
            "samples_with_all_local_paths_available": 0,
            "local_training_data_available": True,
        },
        "reference_manifest": {
            "approved_references": 0,
            "style_count": 0,
            "unique_character_count": 0,
            "pair_support": {},
            "same_character_cross_style_character_count": 0,
        },
        "reference_cache": {
            "status": "PASS",
            "preferred_index": "index.json",
            "cache_gitignored": True,
            "errors": [],
        },
    }
    outputs = write_preflight_outputs(tmp_path / "preflight", report)
    assert outputs["status"].is_file()
    assert outputs["missing_prerequisites"].is_file()
    assert outputs["cache_preflight"].is_file()
