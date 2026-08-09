from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from onestroke_model.controlled_perturbations import DEFAULT_PERTURBATIONS
from onestroke_model.perturbation_benchmark import (
    load_reference_cache,
    run_benchmark,
    spearman_rho,
    bootstrap_mean_ci95,
    structural_target_channel_distribution,
    summarize_behavior,
    synthetic_references,
    write_benchmark_outputs,
)


def test_spearman_rho_handles_ties_and_direction() -> None:
    assert np.isclose(spearman_rho([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
    assert np.isclose(spearman_rho([1, 2, 3, 4], [1, 2, 2, 4]), 0.9486832980505138)
    assert spearman_rho([1, 2, 3], [5, 5, 5]) is None


def test_load_reference_cache_uses_stable_nonperformance_selection(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    references = []
    for index in range(5):
        masks = np.zeros((64, 64, 6), dtype=np.uint8)
        masks[20:40, 20 + index : 27 + index, :5] = 1
        masks[28:31, 23 + index : 26 + index, 5] = 1
        filename = f"ref_{index}.npz"
        np.savez_compressed(
            cache_dir / filename,
            binary_masks=masks,
            channels=np.asarray(("vec1", "vec2", "vec3", "vec4", "vec5", "keypoint")),
        )
        references.append(
            {
                "reference_id": f"ref-{index}",
                "style_id": "style-A" if index < 4 else "style-B",
                "target_char": chr(ord("A") + index),
                "cache_path": filename,
            }
        )
    index_path = cache_dir / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "channels": ["vec1", "vec2", "vec3", "vec4", "vec5", "keypoint"],
                "cache_format": "binary_masks_hwc_uint8",
                "references": references,
            }
        ),
        encoding="utf-8",
    )
    metadata_a, selected_a = load_reference_cache(index_path, limit_per_style=2)
    metadata_b, selected_b = load_reference_cache(index_path, limit_per_style=2)
    assert [row["reference_id"] for row in selected_a] == [
        row["reference_id"] for row in selected_b
    ]
    assert len(selected_a) == 3
    assert metadata_a["selection_policy"] == metadata_b["selection_policy"]


def test_smoke_benchmark_writes_reproducible_outputs(tmp_path: Path) -> None:
    metadata, references = synthetic_references(canvas_size=112)
    definitions = (
        next(item for item in DEFAULT_PERTURBATIONS if item.name == "global_translation"),
        next(item for item in DEFAULT_PERTURBATIONS if item.name == "direction_terminal_deletion"),
        next(item for item in DEFAULT_PERTURBATIONS if item.name == "keypoint_shift"),
    )
    # One synthetic reference keeps the unit test fast; the CLI smoke uses all four.
    results, baselines = run_benchmark(references[:1], definitions=definitions)
    report = write_benchmark_outputs(
        tmp_path,
        input_metadata={**metadata, "selected_references": 1},
        results=results,
        baselines=baselines,
        definitions=definitions,
    )
    assert report["benchmark_name"] == "onestroke_controlled_perturbation_v1"
    assert report["audit"]["baseline_identity"]["max_abs_deviation_from_100"] < 1e-9
    assert (tmp_path / "perturbation_results.csv").is_file()
    assert (tmp_path / "perturbation_summary.csv").is_file()
    assert (tmp_path / "behavior_summary.csv").is_file()
    assert (tmp_path / "benchmark_report.json").is_file()
    behaviors = summarize_behavior(results, definitions=definitions)
    deletion = next(
        row
        for row in behaviors
        if row["perturbation"] == "direction_terminal_deletion"
    )
    assert float(deletion["adjacent_nonincreasing_pair_rate"]) >= 0.66


def test_bootstrap_ci_is_deterministic() -> None:
    values = [1.0, 2.0, 3.0, 5.0, 8.0]
    first = bootstrap_mean_ci95(values, "stable-seed", iterations=500)
    second = bootstrap_mean_ci95(values, "stable-seed", iterations=500)
    assert first == second
    assert first[0] is not None and first[1] is not None
    assert first[0] <= float(np.mean(values)) <= first[1]


def test_target_channel_distribution_counts_each_reference_once_per_family() -> None:
    _, references = synthetic_references(canvas_size=112)
    definition = next(
        item
        for item in DEFAULT_PERTURBATIONS
        if item.name == "direction_terminal_deletion"
    )
    results, _ = run_benchmark(references[:1], definitions=(definition,))
    distribution = structural_target_channel_distribution(results)
    assert sum(distribution[definition.name].values()) == 1


def test_smoke_report_contains_code_provenance(tmp_path: Path) -> None:
    metadata, references = synthetic_references(canvas_size=112)
    definition = next(
        item
        for item in DEFAULT_PERTURBATIONS
        if item.name == "global_translation"
    )
    results, baselines = run_benchmark(references[:1], definitions=(definition,))
    report = write_benchmark_outputs(
        tmp_path,
        input_metadata={**metadata, "selected_references": 1},
        results=results,
        baselines=baselines,
        definitions=(definition,),
    )
    runtime = report["runtime"]
    assert runtime["benchmark_module_sha256"]
    assert runtime["perturbation_module_sha256"]
    assert runtime["python_version"]
