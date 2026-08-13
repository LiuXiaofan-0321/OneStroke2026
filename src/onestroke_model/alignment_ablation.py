"""Benchmark-only alignment variants for the IJDAR alignment ablation."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from onestroke_model.constants import SCHEMA_VERSION
from onestroke_model.controlled_perturbations import (
    DEFAULT_PERTURBATIONS,
    PerturbationDefinition,
    PreparedReferenceScorer,
    apply_perturbation,
)
from onestroke_model.perturbation_benchmark import spearman_rho
from onestroke_model.style_scoring import _as_masks, _dice, _ink, _iou, _tolerant_f1

ALIGNMENT_VARIANTS: dict[str, dict[str, Any]] = {
    "no_alignment": {
        "translation": False,
        "isotropic_scale_range": [1.0, 1.0],
        "max_rotation_degrees": 0.0,
        "description": "No global alignment.",
    },
    "current_constrained": {
        "translation": True,
        "isotropic_scale_range": [0.80, 1.20],
        "max_rotation_degrees": 3.0,
        "description": "Unmodified production alignment policy.",
    },
    "wide_similarity": {
        "translation": True,
        "isotropic_scale_range": [0.60, 1.40],
        "max_rotation_degrees": 12.0,
        "description": (
            "Pre-registered benchmark-only wide similarity transform. "
            "No affine, nonuniform, or deformable warp is used."
        ),
    },
}

ERROR_MASKING_RATIO_FORMULA = (
    "(no_alignment_structural_drop - variant_structural_drop) "
    "/ max(abs(no_alignment_structural_drop), 1e-8)"
)


def _score_pre_aligned(
    user_masks: np.ndarray,
    reference_masks: np.ndarray,
    *,
    alignment_policy: Mapping[str, Any],
    selected_transform: Mapping[str, float],
) -> dict[str, Any]:
    user = _as_masks(user_masks)
    reference = _as_masks(reference_masks)
    if user.shape != reference.shape:
        raise ValueError("user and reference masks must share a canonical canvas")
    direction_dice = [
        _dice(user[..., index], reference[..., index]) for index in range(5)
    ]
    direction_mean = float(np.mean(direction_dice))
    ink_iou = _iou(_ink(user), _ink(reference))
    keypoint_f1 = _tolerant_f1(user[..., 5], reference[..., 5], radius=3)
    score = 100.0 * (
        0.55 * direction_mean + 0.25 * ink_iou + 0.20 * keypoint_f1
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "prototype_structure_score": float(score),
        "direction_macro_dice": direction_mean,
        "ink_iou": ink_iou,
        "keypoint_tolerant_f1_radius_3": keypoint_f1,
        "alignment_policy": dict(alignment_policy),
        "selected_transform": dict(selected_transform),
    }


def _variant_scorers(reference_masks: np.ndarray) -> dict[str, Any]:
    reference = _as_masks(reference_masks)
    return {
        "no_alignment": None,
        "current_constrained": PreparedReferenceScorer(
            reference,
            min_scale=0.80,
            max_scale=1.20,
            max_rotation_degrees=3.0,
        ),
        "wide_similarity": PreparedReferenceScorer(
            reference,
            min_scale=0.60,
            max_scale=1.40,
            max_rotation_degrees=12.0,
        ),
    }


def score_alignment_variant(
    user_masks: np.ndarray,
    reference_masks: np.ndarray,
    variant: str,
    *,
    prepared_scorer: PreparedReferenceScorer | None = None,
) -> dict[str, Any]:
    if variant not in ALIGNMENT_VARIANTS:
        raise ValueError(f"unknown alignment variant: {variant!r}")
    if variant == "no_alignment":
        return _score_pre_aligned(
            user_masks,
            reference_masks,
            alignment_policy=ALIGNMENT_VARIANTS[variant],
            selected_transform={
                "scale": 1.0,
                "rotation_degrees": 0.0,
                "translation_x": 0.0,
                "translation_y": 0.0,
                "alignment_ink_iou": _iou(_ink(user_masks), _ink(reference_masks)),
            },
        )
    scorer = prepared_scorer
    if scorer is None:
        policy = ALIGNMENT_VARIANTS[variant]
        scorer = PreparedReferenceScorer(
            reference_masks,
            min_scale=float(policy["isotropic_scale_range"][0]),
            max_scale=float(policy["isotropic_scale_range"][1]),
            max_rotation_degrees=float(policy["max_rotation_degrees"]),
        )
    evidence, _ = scorer.score(user_masks)
    evidence["alignment_policy"] = dict(ALIGNMENT_VARIANTS[variant])
    return evidence


def error_masking_ratio(no_alignment_drop: float, variant_drop: float) -> float | None:
    """Positive values mean alignment hides part of a structural penalty."""
    denominator = abs(float(no_alignment_drop))
    if denominator <= 1e-8:
        return None
    return float((float(no_alignment_drop) - float(variant_drop)) / denominator)


def nuisance_suppression_ratio(no_alignment_drop: float, variant_drop: float) -> float | None:
    denominator = abs(float(no_alignment_drop))
    if denominator <= 1e-8:
        return None
    return float(1.0 - abs(float(variant_drop)) / denominator)


def run_alignment_ablation(
    references: Sequence[Mapping[str, Any]],
    *,
    definitions: Sequence[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
    progress: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    baselines: list[dict[str, Any]] = []
    for reference_number, reference in enumerate(references, start=1):
        reference_id = str(reference["reference_id"])
        reference_masks = _as_masks(np.asarray(reference["masks"]))
        scorers = _variant_scorers(reference_masks)
        baseline_scores: dict[str, float] = {}
        for variant, scorer in scorers.items():
            evidence = score_alignment_variant(
                reference_masks,
                reference_masks,
                variant,
                prepared_scorer=scorer,
            )
            baseline_scores[variant] = float(evidence["prototype_structure_score"])
            baselines.append(
                {
                    "reference_id": reference_id,
                    "style_id": str(reference.get("style_id", "")),
                    "target_char": str(reference.get("target_char", "")),
                    "alignment_variant": variant,
                    "baseline_score": baseline_scores[variant],
                }
            )

        for definition in definitions:
            for severity in definition.severities:
                outcome = apply_perturbation(
                    reference_masks,
                    reference_id,
                    definition.name,
                    float(severity),
                )
                observation_key = (
                    reference_id,
                    definition.name,
                    float(severity),
                )
                for variant, scorer in scorers.items():
                    common = {
                        "reference_id": reference_id,
                        "style_id": str(reference.get("style_id", "")),
                        "target_char": str(reference.get("target_char", "")),
                        "perturbation": definition.name,
                        "family": definition.family,
                        "severity": float(severity),
                        "unit": definition.unit,
                        "expected_behavior": definition.expected_behavior,
                        "alignment_variant": variant,
                        "observation_key": json.dumps(
                            observation_key,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        "valid": bool(outcome.valid),
                        "invalid_reason": outcome.invalid_reason or "",
                        "perturbation_metadata_json": json.dumps(
                            outcome.metadata,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "baseline_score": baseline_scores[variant],
                    }
                    if not outcome.valid:
                        rows.append(
                            {
                                **common,
                                "score": None,
                                "score_drop": None,
                                "direction_macro_dice": None,
                                "ink_iou": None,
                                "keypoint_f1_radius_3": None,
                                "selected_scale": None,
                                "selected_rotation_degrees": None,
                                "selected_translation_x": None,
                                "selected_translation_y": None,
                                "nuisance_suppression_ratio": None,
                                "error_masking_ratio": None,
                            }
                        )
                        continue
                    evidence = score_alignment_variant(
                        outcome.masks,
                        reference_masks,
                        variant,
                        prepared_scorer=scorer,
                    )
                    transform = evidence["selected_transform"]
                    score = float(evidence["prototype_structure_score"])
                    rows.append(
                        {
                            **common,
                            "score": score,
                            "score_drop": baseline_scores[variant] - score,
                            "direction_macro_dice": evidence["direction_macro_dice"],
                            "ink_iou": evidence["ink_iou"],
                            "keypoint_f1_radius_3": evidence[
                                "keypoint_tolerant_f1_radius_3"
                            ],
                            "selected_scale": transform["scale"],
                            "selected_rotation_degrees": transform[
                                "rotation_degrees"
                            ],
                            "selected_translation_x": transform["translation_x"],
                            "selected_translation_y": transform["translation_y"],
                            "nuisance_suppression_ratio": None,
                            "error_masking_ratio": None,
                        }
                    )

        if progress:
            print(f"alignment_ablation_reference={reference_number}/{len(references)}")

    by_observation: defaultdict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row["valid"]:
            by_observation[str(row["observation_key"])][str(row["alignment_variant"])] = row
    for variants in by_observation.values():
        no_alignment = variants.get("no_alignment")
        if no_alignment is None:
            continue
        no_drop = float(no_alignment["score_drop"])
        for variant, row in variants.items():
            variant_drop = float(row["score_drop"])
            if row["family"] == "nuisance":
                row["nuisance_suppression_ratio"] = (
                    0.0
                    if variant == "no_alignment"
                    else nuisance_suppression_ratio(no_drop, variant_drop)
                )
            if row["family"] == "structural":
                row["error_masking_ratio"] = (
                    0.0
                    if variant == "no_alignment"
                    else error_masking_ratio(no_drop, variant_drop)
                )
    return rows, baselines


def summarize_alignment_ablation(
    rows: Sequence[Mapping[str, Any]],
    definitions: Sequence[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    definition_map = {definition.name: definition for definition in definitions}
    valid_rows = [row for row in rows if row.get("valid")]
    overall: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    for variant in ALIGNMENT_VARIANTS:
        variant_rows = [
            row for row in valid_rows if row["alignment_variant"] == variant
        ]
        nuisance = [row for row in variant_rows if row["family"] == "nuisance"]
        structural = [row for row in variant_rows if row["family"] == "structural"]
        masking = [
            float(row["error_masking_ratio"])
            for row in structural
            if row.get("error_masking_ratio") is not None
        ]
        suppression = [
            float(row["nuisance_suppression_ratio"])
            for row in nuisance
            if row.get("nuisance_suppression_ratio") is not None
        ]

        complete_rhos: list[float] = []
        adjacent_hits = 0
        adjacent_total = 0
        grouped: defaultdict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
        for row in structural:
            grouped[(str(row["reference_id"]), str(row["perturbation"]))].append(row)
        for (reference_id, perturbation), group in sorted(grouped.items()):
            definition = definition_map[perturbation]
            by_severity = {float(row["severity"]): row for row in group}
            configured = [float(value) for value in definition.severities]
            complete = all(value in by_severity for value in configured)
            rho = None
            nonincreasing = None
            if complete:
                scores = [float(by_severity[value]["score"]) for value in configured]
                rho = spearman_rho(configured, scores)
                if rho is not None:
                    complete_rhos.append(float(rho))
                hits = sum(
                    first >= second - 1e-9
                    for first, second in pairwise(scores)
                )
                adjacent_hits += hits
                adjacent_total += max(0, len(scores) - 1)
                nonincreasing = hits / max(1, len(scores) - 1)
            curve_rows.append(
                {
                    "alignment_variant": variant,
                    "reference_id": reference_id,
                    "perturbation": perturbation,
                    "complete_severity_curve": complete,
                    "spearman_severity_vs_score": rho,
                    "adjacent_nonincreasing_rate": nonincreasing,
                }
            )

        all_variant_rows = [row for row in rows if row["alignment_variant"] == variant]
        invalid_count = sum(not bool(row["valid"]) for row in all_variant_rows)
        overall.append(
            {
                "alignment_variant": variant,
                "n_observations": len(all_variant_rows),
                "n_valid_observations": len(variant_rows),
                "invalid_rate": invalid_count / max(1, len(all_variant_rows)),
                "nuisance_mean_abs_score_drop": (
                    float(np.mean([abs(float(row["score_drop"])) for row in nuisance]))
                    if nuisance
                    else None
                ),
                "structural_mean_score_drop": (
                    float(np.mean([float(row["score_drop"]) for row in structural]))
                    if structural
                    else None
                ),
                "mean_nuisance_suppression_ratio": (
                    float(np.mean(suppression)) if suppression else None
                ),
                "mean_structural_error_masking_ratio": (
                    float(np.mean(masking)) if masking else None
                ),
                "mean_structural_negative_spearman_magnitude": (
                    float(np.mean([-value for value in complete_rhos]))
                    if complete_rhos
                    else None
                ),
                "structural_adjacent_nonincreasing_rate": (
                    adjacent_hits / adjacent_total if adjacent_total else None
                ),
            }
        )
    return overall, curve_rows


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_alignment_ablation_outputs(
    output_dir: str | Path,
    *,
    rows: Sequence[Mapping[str, Any]] | None,
    baselines: Sequence[Mapping[str, Any]] | None,
    input_metadata: Mapping[str, Any],
    definitions: Sequence[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    preregistration = {
        "schema_version": 1,
        "variants": ALIGNMENT_VARIANTS,
        "error_masking_ratio_formula": ERROR_MASKING_RATIO_FORMULA,
        "wide_variant_fixed_before_formal_results": True,
        "production_defaults_modified": False,
        "definitions": [
            {
                "name": definition.name,
                "family": definition.family,
                "severities": list(definition.severities),
                "unit": definition.unit,
            }
            for definition in definitions
        ],
    }
    (output / "alignment_ablation_preregistered_config.json").write_text(
        json.dumps(preregistration, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "benchmark_name": "onestroke_alignment_ablation_v1",
        "formal_results_available": rows is not None,
        "input_metadata": dict(input_metadata),
        "preregistration": preregistration,
    }
    if rows is None or baselines is None:
        (output / "BLOCKED.md").write_text(
            """# Alignment Ablation Formal Run Blocked

The benchmark variants and fixed ranges are preregistered.
Formal execution is blocked by the missing approved real reference mask cache.
No synthetic numbers are substituted for paper results.
""",
            encoding="utf-8",
        )
    else:
        (output / "BLOCKED.md").unlink(missing_ok=True)
        overall, curves = summarize_alignment_ablation(rows, definitions)
        _write_csv(output / "alignment_ablation_results.csv", rows)
        _write_csv(output / "alignment_baselines.csv", baselines)
        _write_csv(output / "alignment_ablation_summary.csv", overall)
        _write_csv(output / "alignment_ablation_curves.csv", curves)
        report["summary"] = overall
        report["validity"] = {
            "invalid_observations_are_not_scored": True,
            "invalid_reason_preserved": True,
        }
    (output / "alignment_ablation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown = [
        "# Alignment Ablation",
        "",
        "The three variants are benchmark-only. Production alignment remains unchanged.",
        "",
        f"`error masking ratio = {ERROR_MASKING_RATIO_FORMULA}`",
        "",
        "Positive error masking means alignment reduced the penalty caused by a structural perturbation.",
        "Negative values mean the variant amplified the penalty. Values are not clipped.",
        "",
        f"- Formal results available: **{report['formal_results_available']}**",
    ]
    (output / "alignment_ablation_report.md").write_text(
        "\n".join(markdown) + "\n",
        encoding="utf-8",
    )
    return report
