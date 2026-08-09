"""Benchmark runner and statistics for controlled structural perturbations."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from PIL import __version__ as pillow_version

from onestroke_model.constants import CHANNELS, SCHEMA_VERSION
from onestroke_model.controlled_perturbations import (
    DEFAULT_PERTURBATIONS,
    PerturbationDefinition,
    PreparedReferenceScorer,
    apply_perturbation,
    iter_suite,
)

RESULT_FIELDS = (
    "reference_id",
    "style_id",
    "target_char",
    "perturbation",
    "family",
    "expected_behavior",
    "severity",
    "severity_unit",
    "status",
    "invalid_reason",
    "prototype_structure_score",
    "score_drop_from_identity",
    "direction_macro_dice",
    "ink_iou",
    "keypoint_tolerant_f1_radius_3",
    "selected_scale",
    "selected_rotation_degrees",
    "selected_translation_x",
    "selected_translation_y",
    "alignment_ink_iou",
    "target_channel",
    "perturbation_metadata_json",
)


class BenchmarkInputError(ValueError):
    """Raised when a local reference cache cannot support the benchmark contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


BENCHMARK_NAME = "onestroke_controlled_perturbation_v1"
BENCHMARK_SCHEMA_VERSION = 1


def collect_runtime_metadata(project_root: str | Path | None = None) -> dict[str, Any]:
    """Capture lightweight provenance without requiring optional packages."""
    root = Path(project_root or Path.cwd()).resolve()
    git_commit: str | None = None
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        value = completed.stdout.strip()
        git_commit = value or None
    except (OSError, subprocess.SubprocessError):
        git_commit = None
    module_path = Path(__file__).resolve()
    perturbation_module = module_path.with_name("controlled_perturbations.py")
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "pillow_version": pillow_version,
        "git_commit": git_commit,
        "benchmark_module_sha256": _sha256(module_path),
        "perturbation_module_sha256": (
            _sha256(perturbation_module) if perturbation_module.is_file() else None
        ),
    }


def _stable_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_reference_cache(
    index_path: str | Path,
    style_ids: set[str] | None = None,
    target_chars: set[str] | None = None,
    limit_per_style: int = 0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load and deterministically select locally cached approved reference masks.

    The checked-in repository intentionally does not redistribute the licensed
    reference images/cache.  This function consumes the local cache created by
    ``cache_reference_masks.py`` and validates the fixed six-channel schema.
    """
    index_path = Path(index_path)
    if not index_path.is_file():
        raise BenchmarkInputError(f"reference cache index not found: {index_path}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if list(index.get("channels", [])) != list(CHANNELS):
        raise BenchmarkInputError(
            f"reference cache channel schema mismatch: {index.get('channels')!r}"
        )
    references = list(index.get("references", []))
    if not references:
        raise BenchmarkInputError("reference cache index contains no references")
    selected: list[dict[str, Any]] = []
    for item in references:
        if style_ids and str(item.get("style_id")) not in style_ids:
            continue
        if target_chars and str(item.get("target_char")) not in target_chars:
            continue
        selected.append(dict(item))
    if not selected:
        raise BenchmarkInputError("no references remain after style/character filtering")
    filtered_references = len(selected)

    # Hash ordering gives a stable, non-performance-based subset if a runtime cap is requested.
    selected.sort(key=lambda item: _stable_key(str(item.get("reference_id", ""))))
    if limit_per_style > 0:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in selected:
            grouped[str(item.get("style_id", ""))].append(item)
        selected = []
        for style_id in sorted(grouped):
            selected.extend(grouped[style_id][:limit_per_style])
        selected.sort(
            key=lambda item: (
                str(item.get("style_id", "")),
                _stable_key(str(item.get("reference_id", ""))),
            )
        )

    loaded: list[dict[str, Any]] = []
    for item in selected:
        cache_path = index_path.parent / str(item.get("cache_path", ""))
        if not cache_path.is_file():
            raise BenchmarkInputError(
                f"cached mask missing for reference {item.get('reference_id')!r}: {cache_path}"
            )
        with np.load(cache_path) as cache:
            channels = [str(value) for value in cache["channels"].tolist()]
            if channels != list(CHANNELS):
                raise BenchmarkInputError(
                    f"cached channel schema mismatch for {item.get('reference_id')!r}: {channels}"
                )
            masks = np.asarray(cache["binary_masks"], dtype=np.uint8).astype(bool)
        if masks.ndim != 3 or masks.shape[-1] != len(CHANNELS):
            raise BenchmarkInputError(
                f"invalid cached mask shape for {item.get('reference_id')!r}: {masks.shape}"
            )
        if not np.any(masks[..., :5]):
            raise BenchmarkInputError(f"empty direction ink for {item.get('reference_id')!r}")
        loaded.append({**item, "masks": masks, "cache_path_resolved": str(cache_path.resolve())})

    metadata = {
        "index_path": str(index_path.resolve()),
        "index_sha256": _sha256(index_path),
        "cache_format": index.get("cache_format"),
        "model_version": index.get("model_version"),
        "checkpoint_sha256": index.get("checkpoint_sha256"),
        "canvas_size": index.get("canvas_size"),
        "normalization": index.get("normalization"),
        "channels": list(CHANNELS),
        "available_references": len(references),
        "filtered_references_before_limit": filtered_references,
        "selected_references": len(loaded),
        "selection_policy": (
            "all filtered references"
            if limit_per_style <= 0
            else f"stable SHA-256 order, first {limit_per_style} references per style"
        ),
    }
    return metadata, loaded


def synthetic_references(canvas_size: int = 160) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Create deterministic multi-channel fixtures for smoke tests only."""
    if canvas_size < 96:
        raise ValueError("synthetic canvas_size must be at least 96")

    def make_variant(variant: int) -> np.ndarray:
        m = np.zeros((canvas_size, canvas_size, 6), dtype=bool)
        c = canvas_size // 2
        offset = variant * 3
        # Five deliberately different direction regions with overlaps/crossings.
        m[c - 4 : c + 5, 32 + offset : canvas_size - 30, 0] = True
        m[28 : canvas_size - 28, c - 4 - offset : c + 5 - offset, 1] = True
        for t in range(-3, 4):
            rr = np.arange(38, canvas_size - 38)
            cc = rr + t - 9 + offset
            valid = (cc >= 0) & (cc < canvas_size)
            m[rr[valid], cc[valid], 2] = True
            cc2 = canvas_size - 1 - rr + t + 7 - offset
            valid2 = (cc2 >= 0) & (cc2 < canvas_size)
            m[rr[valid2], cc2[valid2], 3] = True
        # Short hook-like fifth region.
        m[c + 25 : c + 32, c - 8 : c + 32, 4] = True
        m[c + 18 : c + 32, c + 25 : c + 32, 4] = True
        # Compact keypoints near several structural junctions/endpoints.
        keypoint_centers = (
            (c, c - offset),
            (c + 29, c + 28),
            (38, 29 + offset),
            (canvas_size - 39, canvas_size - 48 + offset),
        )
        for y, x in keypoint_centers:
            y0, y1 = max(0, y - 2), min(canvas_size, y + 3)
            x0, x1 = max(0, x - 2), min(canvas_size, x + 3)
            m[y0:y1, x0:x1, 5] = True
        return m

    refs = [
        {
            "reference_id": f"synthetic:style_{index % 2}:char_{index}",
            "style_id": f"synthetic_style_{index % 2}",
            "target_char": chr(ord("A") + index),
            "masks": make_variant(index),
            "cache_path_resolved": "synthetic",
        }
        for index in range(4)
    ]
    return (
        {
            "index_path": "synthetic",
            "index_sha256": None,
            "cache_format": "synthetic_binary_masks_hwc_bool",
            "model_version": "synthetic-smoke-only",
            "checkpoint_sha256": None,
            "canvas_size": canvas_size,
            "normalization": None,
            "channels": list(CHANNELS),
            "available_references": len(refs),
            "selected_references": len(refs),
            "selection_policy": "four deterministic synthetic fixtures",
        },
        refs,
    )


def _valid_result_row(
    reference: dict[str, Any],
    definition: PerturbationDefinition,
    severity: float,
    evidence: dict[str, Any],
    baseline_score: float,
    perturbation_metadata: dict[str, Any],
) -> dict[str, Any]:
    transform = dict(evidence["selected_transform"])
    return {
        "reference_id": reference["reference_id"],
        "style_id": reference.get("style_id", ""),
        "target_char": reference.get("target_char", ""),
        "perturbation": definition.name,
        "family": definition.family,
        "expected_behavior": definition.expected_behavior,
        "severity": float(severity),
        "severity_unit": definition.unit,
        "status": "valid",
        "invalid_reason": "",
        "prototype_structure_score": float(evidence["prototype_structure_score"]),
        "score_drop_from_identity": float(
            baseline_score - float(evidence["prototype_structure_score"])
        ),
        "direction_macro_dice": float(evidence["direction_macro_dice"]),
        "ink_iou": float(evidence["ink_iou"]),
        "keypoint_tolerant_f1_radius_3": float(evidence["keypoint_tolerant_f1_radius_3"]),
        "selected_scale": float(transform["scale"]),
        "selected_rotation_degrees": float(transform["rotation_degrees"]),
        "selected_translation_x": float(transform["translation_x"]),
        "selected_translation_y": float(transform["translation_y"]),
        "alignment_ink_iou": float(transform["alignment_ink_iou"]),
        "target_channel": str(perturbation_metadata.get("target_channel", "")),
        "perturbation_metadata_json": json.dumps(
            perturbation_metadata, ensure_ascii=False, sort_keys=True
        ),
    }


def _invalid_result_row(
    reference: dict[str, Any],
    definition: PerturbationDefinition,
    severity: float,
    reason: str,
    perturbation_metadata: dict[str, Any],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "reference_id": reference["reference_id"],
        "style_id": reference.get("style_id", ""),
        "target_char": reference.get("target_char", ""),
        "perturbation": definition.name,
        "family": definition.family,
        "expected_behavior": definition.expected_behavior,
        "severity": float(severity),
        "severity_unit": definition.unit,
        "status": "invalid",
        "invalid_reason": reason,
        "target_channel": str(perturbation_metadata.get("target_channel", "")),
        "perturbation_metadata_json": json.dumps(
            perturbation_metadata, ensure_ascii=False, sort_keys=True
        ),
    }
    for field in RESULT_FIELDS:
        row.setdefault(field, "")
    return row


def run_benchmark(
    references: Sequence[dict[str, Any]],
    definitions: Sequence[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
    progress: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Score identity and the full perturbation suite for each reference."""
    results: list[dict[str, Any]] = []
    baselines: list[dict[str, Any]] = []
    total = len(references)
    for reference_index, reference in enumerate(references, start=1):
        reference_masks = np.asarray(reference["masks"], dtype=bool)
        scorer = PreparedReferenceScorer(reference_masks)
        baseline_evidence, _ = scorer.score(reference_masks)
        baseline_score = float(baseline_evidence["prototype_structure_score"])
        baseline_transform = dict(baseline_evidence["selected_transform"])
        baselines.append(
            {
                "reference_id": reference["reference_id"],
                "style_id": reference.get("style_id", ""),
                "target_char": reference.get("target_char", ""),
                "prototype_structure_score": baseline_score,
                "direction_macro_dice": float(baseline_evidence["direction_macro_dice"]),
                "ink_iou": float(baseline_evidence["ink_iou"]),
                "keypoint_tolerant_f1_radius_3": float(
                    baseline_evidence["keypoint_tolerant_f1_radius_3"]
                ),
                "selected_transform": baseline_transform,
            }
        )
        for definition, severity in iter_suite(definitions):
            outcome = apply_perturbation(
                reference_masks,
                reference_id=str(reference["reference_id"]),
                perturbation_name=definition.name,
                severity=severity,
            )
            if not outcome.valid:
                results.append(
                    _invalid_result_row(
                        reference,
                        definition,
                        severity,
                        outcome.invalid_reason or "unspecified invalid perturbation",
                        outcome.metadata,
                    )
                )
                continue
            evidence, _ = scorer.score(outcome.masks)
            results.append(
                _valid_result_row(
                    reference,
                    definition,
                    severity,
                    evidence,
                    baseline_score,
                    outcome.metadata,
                )
            )
        if progress:
            print(f"controlled-perturbation reference={reference_index}/{total}")
    return results, baselines


def _rankdata_average(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        ranks[order[start:end]] = average_rank
        start = end
    return ranks


def spearman_rho(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    x_arr = np.asarray(x, dtype=np.float64)
    y_arr = np.asarray(y, dtype=np.float64)
    x_rank = _rankdata_average(x_arr)
    y_rank = _rankdata_average(y_arr)
    x_centered = x_rank - x_rank.mean()
    y_centered = y_rank - y_rank.mean()
    denominator = float(np.sqrt(np.sum(x_centered**2) * np.sum(y_centered**2)))
    if denominator <= 0:
        return None
    return float(np.sum(x_centered * y_centered) / denominator)


def _safe_float(row: dict[str, Any], field: str) -> float | None:
    value = row.get(field)
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def bootstrap_mean_ci95(
    values: Sequence[float],
    seed_key: str,
    iterations: int = 2000,
) -> tuple[float | None, float | None]:
    """Deterministic nonparametric 95% CI for the sample mean."""
    if not values:
        return None, None
    array = np.asarray(values, dtype=np.float64)
    if len(array) == 1 or iterations <= 0:
        mean = float(array.mean())
        return mean, mean
    seed = int.from_bytes(hashlib.sha256(seed_key.encode("utf-8")).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(array), size=(int(iterations), len(array)))
    means = array[indices].mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def _definition_map(
    definitions: Sequence[PerturbationDefinition],
) -> dict[str, PerturbationDefinition]:
    return {item.name: item for item in definitions}


def summarize_by_severity(
    results: Sequence[dict[str, Any]],
    definitions: Sequence[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
    bootstrap_iterations: int = 2000,
) -> list[dict[str, Any]]:
    definition_map = _definition_map(definitions)
    groups: dict[tuple[str, str, str, float, str], list[dict[str, Any]]] = defaultdict(list)
    invalid_counts: dict[tuple[str, str, str, float, str], int] = defaultdict(int)
    for row in results:
        key = (
            str(row["perturbation"]),
            str(row["family"]),
            str(row["expected_behavior"]),
            float(row["severity"]),
            str(row["severity_unit"]),
        )
        if row.get("status") == "valid":
            groups[key].append(row)
        else:
            invalid_counts[key] += 1
    summaries: list[dict[str, Any]] = []
    all_keys = sorted(set(groups) | set(invalid_counts), key=lambda key: (key[0], key[3]))
    metrics = (
        "prototype_structure_score",
        "score_drop_from_identity",
        "direction_macro_dice",
        "ink_iou",
        "keypoint_tolerant_f1_radius_3",
        "alignment_ink_iou",
    )
    for key in all_keys:
        perturbation, family, expected, severity, unit = key
        valid_rows = groups.get(key, [])
        definition = definition_map.get(perturbation)
        severity_index = ""
        severity_normalized = ""
        if definition is not None and severity in definition.severities:
            severity_index = definition.severities.index(severity) + 1
            maximum = max(definition.severities)
            severity_normalized = float(severity / maximum) if maximum else 0.0
        summary: dict[str, Any] = {
            "perturbation": perturbation,
            "family": family,
            "expected_behavior": expected,
            "severity": severity,
            "severity_unit": unit,
            "severity_index": severity_index,
            "severity_normalized": severity_normalized,
            "n_valid": len(valid_rows),
            "n_invalid": invalid_counts.get(key, 0),
        }
        for metric in metrics:
            values = [
                value
                for row in valid_rows
                if (value := _safe_float(row, metric)) is not None
            ]
            if not values:
                summary[f"{metric}_mean"] = ""
                summary[f"{metric}_std"] = ""
                summary[f"{metric}_median"] = ""
                summary[f"{metric}_p05"] = ""
                summary[f"{metric}_p95"] = ""
                continue
            array = np.asarray(values, dtype=np.float64)
            summary[f"{metric}_mean"] = float(array.mean())
            summary[f"{metric}_std"] = float(array.std(ddof=1)) if len(array) > 1 else 0.0
            summary[f"{metric}_median"] = float(np.median(array))
            summary[f"{metric}_p05"] = float(np.quantile(array, 0.05))
            summary[f"{metric}_p95"] = float(np.quantile(array, 0.95))
        for metric in ("prototype_structure_score", "score_drop_from_identity"):
            values = [
                value
                for row in valid_rows
                if (value := _safe_float(row, metric)) is not None
            ]
            low, high = bootstrap_mean_ci95(
                values,
                seed_key=f"severity-summary:{perturbation}:{severity}:{metric}",
                iterations=bootstrap_iterations,
            )
            summary[f"{metric}_mean_ci95_low"] = "" if low is None else low
            summary[f"{metric}_mean_ci95_high"] = "" if high is None else high
        summaries.append(summary)
    return summaries


def summarize_by_style(
    results: Sequence[dict[str, Any]],
    bootstrap_iterations: int = 2000,
) -> list[dict[str, Any]]:
    """Style-stratified score/drop curves for detecting reference-pack-specific behavior."""
    groups: dict[tuple[str, str, str, float, str], list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        if row.get("status") != "valid":
            continue
        key = (
            str(row.get("style_id", "")),
            str(row["perturbation"]),
            str(row["family"]),
            float(row["severity"]),
            str(row["severity_unit"]),
        )
        groups[key].append(row)
    output: list[dict[str, Any]] = []
    for key in sorted(groups, key=lambda item: (item[0], item[1], item[3])):
        style_id, perturbation, family, severity, unit = key
        rows = groups[key]
        scores = [float(row["prototype_structure_score"]) for row in rows]
        drops = [float(row["score_drop_from_identity"]) for row in rows]
        score_low, score_high = bootstrap_mean_ci95(
            scores,
            seed_key=f"style:{style_id}:{perturbation}:{severity}:score",
            iterations=bootstrap_iterations,
        )
        drop_low, drop_high = bootstrap_mean_ci95(
            drops,
            seed_key=f"style:{style_id}:{perturbation}:{severity}:drop",
            iterations=bootstrap_iterations,
        )
        output.append(
            {
                "style_id": style_id,
                "perturbation": perturbation,
                "family": family,
                "severity": severity,
                "severity_unit": unit,
                "n_valid": len(rows),
                "prototype_structure_score_mean": float(np.mean(scores)),
                "prototype_structure_score_std": (
                    float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0
                ),
                "prototype_structure_score_mean_ci95_low": score_low,
                "prototype_structure_score_mean_ci95_high": score_high,
                "score_drop_from_identity_mean": float(np.mean(drops)),
                "score_drop_from_identity_std": (
                    float(np.std(drops, ddof=1)) if len(drops) > 1 else 0.0
                ),
                "score_drop_from_identity_mean_ci95_low": drop_low,
                "score_drop_from_identity_mean_ci95_high": drop_high,
            }
        )
    return output


def summarize_behavior(
    results: Sequence[dict[str, Any]],
    definitions: Sequence[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> list[dict[str, Any]]:
    by_perturbation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        by_perturbation[str(row["perturbation"])].append(row)

    output: list[dict[str, Any]] = []
    for definition in definitions:
        all_rows = by_perturbation.get(definition.name, [])
        rows = [row for row in all_rows if row.get("status") == "valid"]
        invalid_count = len(all_rows) - len(rows)
        common = {
            "perturbation": definition.name,
            "family": definition.family,
            "expected_behavior": definition.expected_behavior,
            "n_valid_observations": len(rows),
            "n_invalid_observations": invalid_count,
            "valid_fraction": (float(len(rows) / len(all_rows)) if all_rows else ""),
        }

        if definition.family == "nuisance":
            drops = [
                value
                for row in rows
                if (value := _safe_float(row, "score_drop_from_identity")) is not None
            ]
            scores = [
                value
                for row in rows
                if (value := _safe_float(row, "prototype_structure_score")) is not None
            ]
            array = np.asarray(drops, dtype=np.float64)
            score_array = np.asarray(scores, dtype=np.float64)
            output.append(
                {
                    **common,
                    "n_references_with_valid_curve": len(
                        {str(row["reference_id"]) for row in rows}
                    ),
                    "n_complete_curves": "",
                    "mean_abs_score_drop": (
                        float(np.mean(np.abs(array))) if len(array) else ""
                    ),
                    "median_abs_score_drop": (
                        float(np.median(np.abs(array))) if len(array) else ""
                    ),
                    "p95_abs_score_drop": (
                        float(np.quantile(np.abs(array), 0.95)) if len(array) else ""
                    ),
                    "max_abs_score_drop": (
                        float(np.max(np.abs(array))) if len(array) else ""
                    ),
                    "fraction_score_ge_99": (
                        float(np.mean(score_array >= 99.0)) if len(score_array) else ""
                    ),
                    "fraction_score_ge_95": (
                        float(np.mean(score_array >= 95.0)) if len(score_array) else ""
                    ),
                    "mean_sample_spearman_rho": "",
                    "median_sample_spearman_rho": "",
                    "adjacent_nonincreasing_pair_rate": "",
                    "adjacent_strict_decrease_pair_rate": "",
                    "mean_max_score_drop": "",
                    "median_max_score_drop": "",
                    "mean_normalized_drop_auc": "",
                    "median_normalized_drop_auc": "",
                }
            )
            continue

        by_reference: dict[str, dict[float, dict[str, Any]]] = defaultdict(dict)
        for row in rows:
            by_reference[str(row["reference_id"])][float(row["severity"])] = row
        configured = tuple(float(value) for value in definition.severities)
        rhos: list[float] = []
        nonincreasing = 0
        strict_decrease = 0
        pair_count = 0
        max_drops: list[float] = []
        normalized_drop_aucs: list[float] = []
        valid_curves = 0
        complete_curves = 0

        for severity_map in by_reference.values():
            available = [severity for severity in configured if severity in severity_map]
            if len(available) >= 2:
                valid_curves += 1
            # Only compare truly adjacent configured severity levels. Missing invalid
            # levels are not silently bridged into a synthetic adjacent pair.
            for first_severity, second_severity in zip(
                configured[:-1], configured[1:], strict=True
            ):
                if first_severity not in severity_map or second_severity not in severity_map:
                    continue
                first_score = float(
                    severity_map[first_severity]["prototype_structure_score"]
                )
                second_score = float(
                    severity_map[second_severity]["prototype_structure_score"]
                )
                pair_count += 1
                if second_score <= first_score + 1e-9:
                    nonincreasing += 1
                if second_score < first_score - 1e-6:
                    strict_decrease += 1

            if len(available) != len(configured):
                continue
            complete_curves += 1
            scores = [
                float(severity_map[severity]["prototype_structure_score"])
                for severity in configured
            ]
            drops = [
                float(severity_map[severity]["score_drop_from_identity"])
                for severity in configured
            ]
            rho = spearman_rho(configured, scores)
            if rho is not None:
                rhos.append(rho)
            max_drops.append(drops[-1])
            max_severity = configured[-1]
            if max_severity > 0:
                x = [0.0] + [value / max_severity for value in configured]
                y = [0.0] + drops
                auc = 0.0
                for x0, x1, y0, y1 in zip(
                    x[:-1], x[1:], y[:-1], y[1:], strict=True
                ):
                    auc += (x1 - x0) * (y0 + y1) / 2.0
                normalized_drop_aucs.append(float(auc))

        output.append(
            {
                **common,
                "n_references_with_valid_curve": valid_curves,
                "n_complete_curves": complete_curves,
                "mean_abs_score_drop": "",
                "median_abs_score_drop": "",
                "p95_abs_score_drop": "",
                "max_abs_score_drop": "",
                "fraction_score_ge_99": "",
                "fraction_score_ge_95": "",
                "mean_sample_spearman_rho": (
                    float(np.mean(rhos)) if rhos else ""
                ),
                "median_sample_spearman_rho": (
                    float(np.median(rhos)) if rhos else ""
                ),
                "adjacent_nonincreasing_pair_rate": (
                    float(nonincreasing / pair_count) if pair_count else ""
                ),
                "adjacent_strict_decrease_pair_rate": (
                    float(strict_decrease / pair_count) if pair_count else ""
                ),
                "mean_max_score_drop": (
                    float(np.mean(max_drops)) if max_drops else ""
                ),
                "median_max_score_drop": (
                    float(np.median(max_drops)) if max_drops else ""
                ),
                "mean_normalized_drop_auc": (
                    float(np.mean(normalized_drop_aucs))
                    if normalized_drop_aucs
                    else ""
                ),
                "median_normalized_drop_auc": (
                    float(np.median(normalized_drop_aucs))
                    if normalized_drop_aucs
                    else ""
                ),
            }
        )
    return output


def _max_severity_rows(
    results: Sequence[dict[str, Any]],
    definitions: Sequence[PerturbationDefinition],
) -> list[dict[str, Any]]:
    maximum = {item.name: max(item.severities) for item in definitions if item.severities}
    return [
        row
        for row in results
        if row.get("status") == "valid"
        and str(row["perturbation"]) in maximum
        and float(row["severity"]) == float(maximum[str(row["perturbation"])])
    ]


def structural_target_channel_distribution(
    results: Sequence[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Count reference-level structural target choices, not severity repetitions."""
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    seen: set[tuple[str, str, str]] = set()
    for row in results:
        if row.get("status") != "valid" or row.get("family") != "structural":
            continue
        raw = str(row.get("perturbation_metadata_json", ""))
        if not raw:
            continue
        try:
            metadata = json.loads(raw)
        except json.JSONDecodeError:
            continue
        channel = metadata.get("target_channel")
        if not channel:
            continue
        key = (
            str(row.get("reference_id", "")),
            str(row["perturbation"]),
            str(channel),
        )
        if key in seen:
            continue
        seen.add(key)
        counts[key[1]][key[2]] += 1
    return {
        name: dict(sorted(channel_counts.items()))
        for name, channel_counts in sorted(counts.items())
    }


def overall_audit_summary(
    results: Sequence[dict[str, Any]],
    behavior_rows: Sequence[dict[str, Any]],
    baselines: Sequence[dict[str, Any]],
    definitions: Sequence[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> dict[str, Any]:
    valid_results = [row for row in results if row.get("status") == "valid"]
    invalid_results = [row for row in results if row.get("status") != "valid"]
    nuisance_drops = np.asarray(
        [
            float(row["score_drop_from_identity"])
            for row in valid_results
            if row["family"] == "nuisance"
        ],
        dtype=np.float64,
    )
    structural_drops = np.asarray(
        [
            float(row["score_drop_from_identity"])
            for row in valid_results
            if row["family"] == "structural"
        ],
        dtype=np.float64,
    )
    structural_behaviors = [row for row in behavior_rows if row["family"] == "structural"]
    nuisance_behaviors = [row for row in behavior_rows if row["family"] == "nuisance"]
    baseline_scores = np.asarray(
        [float(row["prototype_structure_score"]) for row in baselines], dtype=np.float64
    )
    maximum_rows = _max_severity_rows(valid_results, definitions)
    nuisance_max_drops = np.asarray(
        [
            abs(float(row["score_drop_from_identity"]))
            for row in maximum_rows
            if row["family"] == "nuisance"
        ],
        dtype=np.float64,
    )
    structural_max_drops = np.asarray(
        [
            float(row["score_drop_from_identity"])
            for row in maximum_rows
            if row["family"] == "structural"
        ],
        dtype=np.float64,
    )
    return {
        "baseline_identity": {
            "n": len(baseline_scores),
            "min_score": float(baseline_scores.min()) if len(baseline_scores) else None,
            "max_abs_deviation_from_100": (
                float(np.max(np.abs(100.0 - baseline_scores))) if len(baseline_scores) else None
            ),
        },
        "nuisance_invariance": {
            "n_valid_observations": int(len(nuisance_drops)),
            "mean_abs_score_drop": (
                float(np.mean(np.abs(nuisance_drops))) if len(nuisance_drops) else None
            ),
            "p95_abs_score_drop": (
                float(np.quantile(np.abs(nuisance_drops), 0.95)) if len(nuisance_drops) else None
            ),
            "max_abs_score_drop": (
                float(np.max(np.abs(nuisance_drops))) if len(nuisance_drops) else None
            ),
            "per_perturbation": nuisance_behaviors,
        },
        "structural_sensitivity": {
            "n_valid_observations": int(len(structural_drops)),
            "mean_score_drop": float(np.mean(structural_drops)) if len(structural_drops) else None,
            "median_score_drop": (
                float(np.median(structural_drops)) if len(structural_drops) else None
            ),
            "per_perturbation": structural_behaviors,
        },
        "family_separation": {
            "interpretation": (
                "descriptive only; perturbation severity units are not matched across families"
            ),
            "all_severities_structural_mean_drop_minus_nuisance_mean_abs_drop": (
                float(np.mean(structural_drops) - np.mean(np.abs(nuisance_drops)))
                if len(structural_drops) and len(nuisance_drops)
                else None
            ),
            "max_severity_nuisance_mean_abs_drop": (
                float(np.mean(nuisance_max_drops)) if len(nuisance_max_drops) else None
            ),
            "max_severity_structural_mean_drop": (
                float(np.mean(structural_max_drops)) if len(structural_max_drops) else None
            ),
            "max_severity_structural_minus_nuisance_drop": (
                float(np.mean(structural_max_drops) - np.mean(nuisance_max_drops))
                if len(structural_max_drops) and len(nuisance_max_drops)
                else None
            ),
        },
        "structural_target_channel_distribution": structural_target_channel_distribution(
            valid_results
        ),
        "validity": {
            "n_valid": len(valid_results),
            "n_invalid": len(invalid_results),
            "invalid_fraction": (
                float(len(invalid_results) / len(results)) if results else 0.0
            ),
            "invalid_reasons": _count_invalid_reasons(invalid_results),
        },
    }


def _count_invalid_reasons(rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get("invalid_reason", "unknown"))] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def write_csv(
    path: str | Path,
    rows: Sequence[dict[str, Any]],
    fieldnames: Sequence[str] | None = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        ordered: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    ordered.append(key)
                    seen.add(key)
        fieldnames = ordered
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: Any, digits: int = 3) -> str:
    if value in (None, ""):
        return "—"
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{digits}f}"
    return str(value)


def _write_markdown_report(
    path: Path,
    report: dict[str, Any],
    behavior_rows: Sequence[dict[str, Any]],
) -> None:
    audit = report["audit"]
    lines = [
        "# OneStroke Controlled Perturbation Benchmark",
        "",
        "> This is a mask-space audit of deterministic reference alignment and structural scoring. "
        "It is not an end-to-end segmentation robustness benchmark.",
        "",
        "## Input provenance",
        "",
        f"- Selected references: **{report['input']['selected_references']}**",
        f"- Reference model version: `{report['input'].get('model_version')}`",
        f"- Cache index SHA-256: `{report['input'].get('index_sha256')}`",
        f"- Checkpoint SHA-256: `{report['input'].get('checkpoint_sha256')}`",
        "",
        "## Identity sanity check",
        "",
        f"- Minimum identity score: **{_fmt(audit['baseline_identity']['min_score'])}**",
        "- Maximum absolute deviation from 100: "
        f"**{_fmt(audit['baseline_identity']['max_abs_deviation_from_100'], 6)}**",
        "",
        "## Nuisance invariance",
        "",
        "| Perturbation | Valid | Mean | P95 | Max | Score >=95 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in behavior_rows:
        if row["family"] != "nuisance":
            continue
        lines.append(
            "| {name} | {valid} | {mean} | {p95} | {maximum} | {fraction} |".format(
                name=row["perturbation"],
                valid=_fmt(row["valid_fraction"]),
                mean=_fmt(row["mean_abs_score_drop"]),
                p95=_fmt(row["p95_abs_score_drop"]),
                maximum=_fmt(row["max_abs_score_drop"]),
                fraction=_fmt(row["fraction_score_ge_95"]),
            )
        )
    lines.extend(
        [
            "",
            "## Structural sensitivity",
            "",
            "| Perturbation | Complete curves | Median rho | Non-increasing pairs | "
            "Strict-decrease pairs | Mean max drop | Mean normalized drop AUC |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in behavior_rows:
        if row["family"] != "structural":
            continue
        lines.append(
            "| {name} | {complete} | {rho} | {noninc} | {strict} | {maxdrop} | {auc} |".format(
                name=row["perturbation"],
                complete=_fmt(row["n_complete_curves"]),
                rho=_fmt(row["median_sample_spearman_rho"]),
                noninc=_fmt(row["adjacent_nonincreasing_pair_rate"]),
                strict=_fmt(row["adjacent_strict_decrease_pair_rate"]),
                maxdrop=_fmt(row["mean_max_score_drop"]),
                auc=_fmt(row["mean_normalized_drop_auc"]),
            )
        )
    separation = audit["family_separation"]
    validity = audit["validity"]
    lines.extend(
        [
            "",
            "## Descriptive family separation",
            "",
            "- Max-severity nuisance mean absolute drop: "
            f"**{_fmt(separation['max_severity_nuisance_mean_abs_drop'])}**",
            "- Max-severity structural mean drop: "
            f"**{_fmt(separation['max_severity_structural_mean_drop'])}**",
            "- Structural minus nuisance drop: "
            f"**{_fmt(separation['max_severity_structural_minus_nuisance_drop'])}**",
            "",
            "## Validity",
            "",
            f"- Valid perturbations: **{validity['n_valid']}**",
            f"- Invalid perturbations retained with reason: **{validity['n_invalid']}**",
            f"- Invalid fraction: **{_fmt(validity['invalid_fraction'])}**",
            "",
            "## Interpretation guardrails",
            "",
            "- Nuisance drops measure the current discretized nearest-neighbor "
            "mask-space implementation, not an ideal continuous optimizer.",
            "- Structural perturbations operate on semantic direction regions, not "
            "manually annotated stroke instances.",
            "- The prototype structure score remains an agreement score and is not "
            "a calibrated calligraphy/aesthetic grade.",
            "- Family-separation summaries compare preregistered maximum severity "
            "within each perturbation but severity units differ, so they are descriptive "
            "and not a matched-effect-size test.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_benchmark_outputs(
    output_dir: str | Path,
    input_metadata: dict[str, Any],
    results: Sequence[dict[str, Any]],
    baselines: Sequence[dict[str, Any]],
    definitions: Sequence[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    severity_summary = summarize_by_severity(
        results, definitions=definitions, bootstrap_iterations=2000
    )
    style_summary = summarize_by_style(results, bootstrap_iterations=2000)
    behavior_summary = summarize_behavior(results, definitions=definitions)
    audit = overall_audit_summary(
        results, behavior_summary, baselines, definitions=definitions
    )

    write_csv(output_dir / "perturbation_results.csv", results, fieldnames=RESULT_FIELDS)
    write_csv(output_dir / "baseline_identity.csv", baselines)
    write_csv(output_dir / "perturbation_summary.csv", severity_summary)
    write_csv(output_dir / "style_perturbation_summary.csv", style_summary)
    write_csv(output_dir / "behavior_summary.csv", behavior_summary)

    report = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "benchmark_name": BENCHMARK_NAME,
        "benchmark_scope": (
            "mask-space audit of deterministic reference alignment and structural scoring; "
            "does not measure segmentation robustness"
        ),
        "scoring_contract": {
            "schema_version": SCHEMA_VERSION,
            "channels": list(CHANNELS),
            "score": (
                "100 * (0.55 * direction_macro_dice + 0.25 * ink_iou + "
                "0.20 * keypoint_tolerant_f1_radius_3)"
            ),
            "alignment": {
                "translation": "centroid-derived",
                "isotropic_scale_range": [0.80, 1.20],
                "scale_grid_points": 9,
                "rotation_range_degrees": [-3.0, 3.0],
                "rotation_grid_points": 7,
                "objective": "direction-ink IoU",
                "deformable_warp": False,
            },
        },
        "input": input_metadata,
        "runtime": collect_runtime_metadata(),
        "protocol_notes": [
            "The benchmark perturbs cached six-channel masks, not source images, "
            "to isolate scoring behavior from segmentation error.",
            "Rotation/scale/compound nuisance severities are deliberately off the "
            "7x9 production alignment search grid to measure robustness of the current "
            "discrete nearest-neighbor mask-space implementation rather than only exact "
            "grid recovery.",
            "Global rotation/scale/compound perturbations use a conservative "
            "foreground-bounding-box precheck; cases at risk of canvas clipping are "
            "retained as invalid rather than mixed into nuisance-invariance estimates.",
            "Local structural target channels are selected by a stable SHA-256 rule "
            "among non-empty direction channels; selection never uses model errors or "
            "score outcomes.",
            "Invalid perturbations are retained in the raw results with a reason and "
            "are never silently dropped.",
        ],
        "statistical_protocol": {
            "severity_curve_mean_ci": (
                "nonparametric bootstrap over references, 2000 resamples, deterministic "
                "SHA-256-derived seed"
            ),
            "structural_monotonicity": (
                "within-reference Spearman rho plus adjacent "
                "non-increasing/strict-decrease pair rates"
            ),
            "nuisance_invariance": "absolute drop from identity score",
        },
        "perturbations": [asdict(item) for item in definitions],
        "audit": audit,
        "files": {
            "raw_results": "perturbation_results.csv",
            "baseline_identity": "baseline_identity.csv",
            "severity_summary": "perturbation_summary.csv",
            "style_severity_summary": "style_perturbation_summary.csv",
            "behavior_summary": "behavior_summary.csv",
        },
    }
    (output_dir / "benchmark_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_markdown_report(output_dir / "benchmark_report.md", report, behavior_summary)
    report["files"]["human_readable_report"] = "benchmark_report.md"
    # Rewrite JSON once so its file manifest includes the Markdown report itself.
    (output_dir / "benchmark_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
