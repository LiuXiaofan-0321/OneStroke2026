"""Controlled audit of OneStroke structure-score aggregation variants.

The runner reuses the existing controlled perturbation suite and the
production-equivalent prepared reference scorer.  It does not tune score weights
against the perturbation outcomes; candidate formulas are fixed in
``structure_score_audit.py`` before evaluation.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from onestroke_model.constants import CHANNELS
from onestroke_model.controlled_perturbations import (
    DEFAULT_PERTURBATIONS,
    PerturbationDefinition,
    PreparedReferenceScorer,
    apply_perturbation,
    iter_suite,
)
from onestroke_model.perturbation_benchmark import spearman_rho
from onestroke_model.structure_score_audit import (
    SCORE_VARIANTS,
    compute_score_components,
    empty_direction_credit,
    keypoint_empty_credit_exposed,
    score_variants,
    v1_weighted_contributions,
)

AUDIT_NAME = "onestroke_structure_score_audit_v1"
AUDIT_SCHEMA_VERSION = 1

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
    "target_channel",
    "active_direction_count",
    "inactive_direction_count",
    "direction_dice_vec1",
    "direction_dice_vec2",
    "direction_dice_vec3",
    "direction_dice_vec4",
    "direction_dice_vec5",
    "direction_dice_coverage_vec1",
    "direction_dice_coverage_vec2",
    "direction_dice_coverage_vec3",
    "direction_dice_coverage_vec4",
    "direction_dice_coverage_vec5",
    "source_reference_present_vec1",
    "source_reference_present_vec2",
    "source_reference_present_vec3",
    "source_reference_present_vec4",
    "source_reference_present_vec5",
    "aligned_reference_present_vec1",
    "aligned_reference_present_vec2",
    "aligned_reference_present_vec3",
    "aligned_reference_present_vec4",
    "aligned_reference_present_vec5",
    "alignment_lost_direction_count",
    "direction_macro_all",
    "direction_macro_active",
    "direction_min_active",
    "empty_direction_macro_credit",
    "ink_iou",
    "alignment_ink_iou",
    "ink_iou_minus_alignment_objective",
    "keypoint_available",
    "user_keypoint_pixels",
    "reference_keypoint_pixels",
    "source_reference_keypoint_pixels",
    "alignment_lost_keypoint_evidence",
    "keypoint_f1_r0",
    "keypoint_f1_r1",
    "keypoint_f1_r3",
    "keypoint_f1_r3_coverage",
    "keypoint_f1_r5",
    "keypoint_component_center_f1_r3",
    "keypoint_component_center_f1_r5",
    "user_keypoint_component_count",
    "reference_keypoint_component_count",
    "keypoint_empty_credit_exposed",
    "v1_current",
    "v1_current_drop",
    "v1_coverage_corrected",
    "v1_coverage_corrected_drop",
    "v2_nonredundant_candidate",
    "v2_nonredundant_candidate_drop",
    "v1_direction_points",
    "v1_ink_points",
    "v1_keypoint_points",
    "production_reported_score",
    "v1_recompute_minus_production",
    "selected_scale",
    "selected_rotation_degrees",
    "selected_translation_x",
    "selected_translation_y",
    "perturbation_metadata_json",
)


def _target_channel(metadata: Mapping[str, Any]) -> str:
    value = metadata.get("target_channel")
    return "" if value is None else str(value)


def _valid_row(
    reference: Mapping[str, Any],
    definition: PerturbationDefinition,
    severity: float,
    user_masks: np.ndarray,
    evidence: Mapping[str, Any],
    aligned_reference: np.ndarray,
    source_reference: np.ndarray,
    baseline_scores: Mapping[str, float],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    components = compute_score_components(
        user_masks, aligned_reference, source_reference_masks=source_reference
    )
    variants = score_variants(components)
    contributions = v1_weighted_contributions(components)
    transform = dict(evidence["selected_transform"])
    production_score = float(evidence["prototype_structure_score"])
    direction_values = list(components.direction_dice)
    direction_coverage_values = list(components.direction_dice_coverage)
    source_present = list(components.reference_direction_present)
    aligned_present = list(components.aligned_reference_direction_present)
    return {
        "reference_id": str(reference.get("reference_id", "")),
        "style_id": str(reference.get("style_id", "")),
        "target_char": str(reference.get("target_char", "")),
        "perturbation": definition.name,
        "family": definition.family,
        "expected_behavior": definition.expected_behavior,
        "severity": float(severity),
        "severity_unit": definition.unit,
        "status": "valid",
        "invalid_reason": "",
        "target_channel": _target_channel(metadata),
        "active_direction_count": int(components.active_direction_count),
        "inactive_direction_count": int(5 - components.active_direction_count),
        **{
            f"direction_dice_vec{index + 1}": float(direction_values[index])
            for index in range(5)
        },
        **{
            f"direction_dice_coverage_vec{index + 1}": float(direction_coverage_values[index])
            for index in range(5)
        },
        **{
            f"source_reference_present_vec{index + 1}": bool(source_present[index])
            for index in range(5)
        },
        **{
            f"aligned_reference_present_vec{index + 1}": bool(aligned_present[index])
            for index in range(5)
        },
        "alignment_lost_direction_count": int(components.alignment_lost_direction_count),
        "direction_macro_all": float(components.direction_macro_all),
        "direction_macro_active": float(components.direction_macro_active),
        "direction_min_active": float(components.direction_min_active),
        "empty_direction_macro_credit": float(empty_direction_credit(components)),
        "ink_iou": float(components.ink_iou),
        "alignment_ink_iou": float(transform["alignment_ink_iou"]),
        "ink_iou_minus_alignment_objective": float(
            components.ink_iou - float(transform["alignment_ink_iou"])
        ),
        "keypoint_available": bool(components.keypoint_available),
        "user_keypoint_pixels": int(components.user_keypoint_pixels),
        "reference_keypoint_pixels": int(components.reference_keypoint_pixels),
        "source_reference_keypoint_pixels": int(components.source_reference_keypoint_pixels),
        "alignment_lost_keypoint_evidence": bool(components.alignment_lost_keypoint_evidence),
        "keypoint_f1_r0": float(components.keypoint_f1_radius_0),
        "keypoint_f1_r1": float(components.keypoint_f1_radius_1),
        "keypoint_f1_r3": float(components.keypoint_f1_radius_3),
        "keypoint_f1_r3_coverage": float(components.keypoint_f1_radius_3_coverage),
        "keypoint_f1_r5": float(components.keypoint_f1_radius_5),
        "keypoint_component_center_f1_r3": float(
            components.keypoint_component_center_f1_radius_3
        ),
        "keypoint_component_center_f1_r5": float(
            components.keypoint_component_center_f1_radius_5
        ),
        "user_keypoint_component_count": int(components.user_keypoint_component_count),
        "reference_keypoint_component_count": int(
            components.reference_keypoint_component_count
        ),
        "keypoint_empty_credit_exposed": bool(keypoint_empty_credit_exposed(components)),
        "v1_current": float(variants["v1_current"]),
        "v1_current_drop": float(baseline_scores["v1_current"] - variants["v1_current"]),
        "v1_coverage_corrected": float(variants["v1_coverage_corrected"]),
        "v1_coverage_corrected_drop": float(
            baseline_scores["v1_coverage_corrected"] - variants["v1_coverage_corrected"]
        ),
        "v2_nonredundant_candidate": float(variants["v2_nonredundant_candidate"]),
        "v2_nonredundant_candidate_drop": float(
            baseline_scores["v2_nonredundant_candidate"]
            - variants["v2_nonredundant_candidate"]
        ),
        "v1_direction_points": float(contributions["direction_points"]),
        "v1_ink_points": float(contributions["ink_points"]),
        "v1_keypoint_points": float(contributions["keypoint_points"]),
        "production_reported_score": production_score,
        "v1_recompute_minus_production": float(variants["v1_current"] - production_score),
        "selected_scale": float(transform["scale"]),
        "selected_rotation_degrees": float(transform["rotation_degrees"]),
        "selected_translation_x": float(transform["translation_x"]),
        "selected_translation_y": float(transform["translation_y"]),
        "perturbation_metadata_json": json.dumps(dict(metadata), ensure_ascii=False, sort_keys=True),
    }


def _invalid_row(
    reference: Mapping[str, Any],
    definition: PerturbationDefinition,
    severity: float,
    reason: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    row = {field: "" for field in RESULT_FIELDS}
    row.update(
        {
            "reference_id": str(reference.get("reference_id", "")),
            "style_id": str(reference.get("style_id", "")),
            "target_char": str(reference.get("target_char", "")),
            "perturbation": definition.name,
            "family": definition.family,
            "expected_behavior": definition.expected_behavior,
            "severity": float(severity),
            "severity_unit": definition.unit,
            "status": "invalid",
            "invalid_reason": str(reason),
            "target_channel": _target_channel(metadata),
            "perturbation_metadata_json": json.dumps(dict(metadata), ensure_ascii=False, sort_keys=True),
        }
    )
    return row


def run_structure_score_audit(
    references: Sequence[Mapping[str, Any]],
    definitions: Iterable[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run identity coverage checks plus all configured perturbations."""

    definitions = tuple(definitions)
    rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []

    identity_definition = PerturbationDefinition(
        name="identity",
        family="baseline",
        severities=(0.0,),
        unit="none",
        expected_behavior="identity",
        description="Reference scored against itself.",
    )

    for reference in references:
        masks = np.asarray(reference["masks"], dtype=bool)
        scorer = PreparedReferenceScorer(masks)
        identity_evidence, identity_aligned = scorer.score(masks)
        identity_components = compute_score_components(
            masks, identity_aligned, source_reference_masks=masks
        )
        baseline_scores = score_variants(identity_components)
        identity_row = _valid_row(
            reference,
            identity_definition,
            0.0,
            masks,
            identity_evidence,
            identity_aligned,
            masks,
            baseline_scores,
            {},
        )
        rows.append(identity_row)
        inactive = [
            CHANNELS[index]
            for index, active in enumerate(identity_components.direction_active)
            if not active
        ]
        source_direction_pixels = [int(masks[..., index].sum()) for index in range(5)]
        nonzero_source_pixels = [value for value in source_direction_pixels if value > 0]
        area_imbalance = (
            float(max(nonzero_source_pixels) / min(nonzero_source_pixels))
            if nonzero_source_pixels
            else None
        )
        source_ink = np.any(masks[..., :5], axis=-1)
        ink_ys, ink_xs = np.nonzero(source_ink)
        if len(ink_xs):
            bbox_width = int(ink_xs.max() - ink_xs.min() + 1)
            bbox_height = int(ink_ys.max() - ink_ys.min() + 1)
            bbox_diagonal = float(np.hypot(bbox_width, bbox_height))
            kp_radius3_relative_to_bbox = (
                float(3.0 / bbox_diagonal) if bbox_diagonal > 0 else None
            )
        else:
            bbox_width = 0
            bbox_height = 0
            bbox_diagonal = None
            kp_radius3_relative_to_bbox = None
        coverage_rows.append(
            {
                "reference_id": str(reference.get("reference_id", "")),
                "style_id": str(reference.get("style_id", "")),
                "target_char": str(reference.get("target_char", "")),
                **{
                    f"source_direction_pixels_vec{index + 1}": source_direction_pixels[index]
                    for index in range(5)
                },
                "source_direction_area_max_to_min_ratio": area_imbalance,
                "reference_ink_bbox_width": bbox_width,
                "reference_ink_bbox_height": bbox_height,
                "reference_ink_bbox_diagonal": bbox_diagonal,
                "keypoint_radius3_fraction_of_reference_bbox_diagonal": kp_radius3_relative_to_bbox,
                "active_direction_count": int(identity_components.active_direction_count),
                "inactive_direction_count": int(5 - identity_components.active_direction_count),
                "inactive_direction_channels": ",".join(inactive),
                "keypoint_available": bool(identity_components.keypoint_available),
                "reference_keypoint_pixels": int(identity_components.reference_keypoint_pixels),
                "source_reference_keypoint_pixels": int(identity_components.source_reference_keypoint_pixels),
                "alignment_lost_direction_count": int(identity_components.alignment_lost_direction_count),
                "alignment_lost_keypoint_evidence": bool(identity_components.alignment_lost_keypoint_evidence),
                "v1_identity_score": float(baseline_scores["v1_current"]),
                "coverage_corrected_identity_score": float(
                    baseline_scores["v1_coverage_corrected"]
                ),
                "nonredundant_identity_score": float(
                    baseline_scores["v2_nonredundant_candidate"]
                ),
            }
        )

        for definition, severity in iter_suite(definitions):
            outcome = apply_perturbation(masks, str(reference.get("reference_id", "")), definition.name, severity)
            if not outcome.valid:
                rows.append(
                    _invalid_row(
                        reference,
                        definition,
                        severity,
                        outcome.invalid_reason or "unspecified invalid perturbation",
                        outcome.metadata,
                    )
                )
                continue
            evidence, aligned = scorer.score(outcome.masks)
            rows.append(
                _valid_row(
                    reference,
                    definition,
                    severity,
                    outcome.masks,
                    evidence,
                    aligned,
                    masks,
                    baseline_scores,
                    outcome.metadata,
                )
            )

    return rows, coverage_rows


def _pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    first = np.asarray(x, dtype=np.float64)
    second = np.asarray(y, dtype=np.float64)
    if len(first) < 3 or len(first) != len(second):
        return None
    if float(np.std(first)) <= 1e-15 or float(np.std(second)) <= 1e-15:
        return None
    return float(np.corrcoef(first, second)[0, 1])


def _valid(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if row.get("status") == "valid"]


def _numeric(row: Mapping[str, Any], field: str) -> float | None:
    value = row.get(field)
    if value in (None, ""):
        return None
    try:
        output = float(value)
    except (TypeError, ValueError):
        return None
    return output if math.isfinite(output) else None


def component_correlations(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Correlate component *losses* from identity across preregistered subsets."""

    valid = [row for row in _valid(rows) if row.get("family") != "baseline"]
    subsets: dict[str, list[Mapping[str, Any]]] = {
        "all_perturbations": valid,
        "nuisance": [row for row in valid if row.get("family") == "nuisance"],
        "structural": [row for row in valid if row.get("family") == "structural"],
    }
    fields = (
        "direction_macro_all",
        "direction_macro_active",
        "ink_iou",
        "keypoint_f1_r3",
        "keypoint_component_center_f1_r3",
    )
    output: list[dict[str, Any]] = []
    for subset_name, subset_rows in subsets.items():
        for index, first_field in enumerate(fields):
            for second_field in fields[index + 1 :]:
                first_values: list[float] = []
                second_values: list[float] = []
                for row in subset_rows:
                    keypoint_fields = {
                        "keypoint_f1_r3",
                        "keypoint_component_center_f1_r3",
                    }
                    if (
                        (first_field in keypoint_fields or second_field in keypoint_fields)
                        and not bool(row.get("keypoint_available"))
                    ):
                        continue
                    first = _numeric(row, first_field)
                    second = _numeric(row, second_field)
                    if first is None or second is None:
                        continue
                    first_values.append(1.0 - first)
                    second_values.append(1.0 - second)
                output.append(
                    {
                        "subset": subset_name,
                        "component_a": first_field,
                        "component_b": second_field,
                        "n": len(first_values),
                        "pearson_r_loss": _pearson(first_values, second_values),
                        "spearman_rho_loss": spearman_rho(first_values, second_values),
                    }
                )
    return output


def keypoint_metric_comparison(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Compare tolerant pixel F1 with connected-component-center F1."""

    valid = [
        row
        for row in _valid(rows)
        if row.get("family") != "baseline" and bool(row.get("keypoint_available"))
    ]
    subsets: dict[str, list[Mapping[str, Any]]] = {
        "all_perturbations": valid,
        "nuisance": [row for row in valid if row.get("family") == "nuisance"],
        "structural": [row for row in valid if row.get("family") == "structural"],
    }
    for perturbation in sorted({str(row["perturbation"]) for row in valid}):
        subsets[f"perturbation:{perturbation}"] = [
            row for row in valid if str(row["perturbation"]) == perturbation
        ]

    output: list[dict[str, Any]] = []
    for subset_name, subset_rows in subsets.items():
        pixel_r3 = np.asarray(
            [float(row["keypoint_f1_r3"]) for row in subset_rows],
            dtype=np.float64,
        )
        center_r3 = np.asarray(
            [float(row["keypoint_component_center_f1_r3"]) for row in subset_rows],
            dtype=np.float64,
        )
        pixel_r5 = np.asarray(
            [float(row["keypoint_f1_r5"]) for row in subset_rows],
            dtype=np.float64,
        )
        center_r5 = np.asarray(
            [float(row["keypoint_component_center_f1_r5"]) for row in subset_rows],
            dtype=np.float64,
        )
        output.append(
            {
                "subset": subset_name,
                "n": len(subset_rows),
                "pixel_f1_r3_mean": float(np.mean(pixel_r3)) if len(pixel_r3) else None,
                "center_f1_r3_mean": float(np.mean(center_r3)) if len(center_r3) else None,
                "mean_abs_pixel_center_difference_r3": (
                    float(np.mean(np.abs(pixel_r3 - center_r3)))
                    if len(pixel_r3)
                    else None
                ),
                "spearman_pixel_vs_center_r3": (
                    spearman_rho(pixel_r3.tolist(), center_r3.tolist())
                    if len(pixel_r3)
                    else None
                ),
                "pixel_f1_r5_mean": float(np.mean(pixel_r5)) if len(pixel_r5) else None,
                "center_f1_r5_mean": float(np.mean(center_r5)) if len(center_r5) else None,
                "mean_abs_pixel_center_difference_r5": (
                    float(np.mean(np.abs(pixel_r5 - center_r5)))
                    if len(pixel_r5)
                    else None
                ),
                "mean_user_keypoint_component_count": (
                    float(
                        np.mean(
                            [
                                int(row["user_keypoint_component_count"])
                                for row in subset_rows
                            ]
                        )
                    )
                    if subset_rows
                    else None
                ),
                "mean_reference_keypoint_component_count": (
                    float(
                        np.mean(
                            [
                                int(row["reference_keypoint_component_count"])
                                for row in subset_rows
                            ]
                        )
                    )
                    if subset_rows
                    else None
                ),
            }
        )
    return output


def variant_correlations(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    valid = [row for row in _valid(rows) if row.get("family") != "baseline"]
    output: list[dict[str, Any]] = []
    for index, first in enumerate(SCORE_VARIANTS):
        for second in SCORE_VARIANTS[index + 1 :]:
            a = [float(row[first]) for row in valid]
            b = [float(row[second]) for row in valid]
            output.append(
                {
                    "score_a": first,
                    "score_b": second,
                    "n": len(a),
                    "pearson_r": _pearson(a, b),
                    "spearman_rho": spearman_rho(a, b),
                    "mean_abs_difference_points": float(np.mean(np.abs(np.asarray(a) - np.asarray(b)))) if a else None,
                    "max_abs_difference_points": float(np.max(np.abs(np.asarray(a) - np.asarray(b)))) if a else None,
                }
            )
    return output


def coverage_summary(coverage_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(coverage_rows)
    inactive_counts = np.asarray(
        [int(row["inactive_direction_count"]) for row in coverage_rows], dtype=np.int64
    ) if n else np.asarray([], dtype=np.int64)
    kp_available = np.asarray(
        [bool(row["keypoint_available"]) for row in coverage_rows], dtype=bool
    ) if n else np.asarray([], dtype=bool)
    area_ratios = np.asarray(
        [
            float(row["source_direction_area_max_to_min_ratio"])
            for row in coverage_rows
            if row.get("source_direction_area_max_to_min_ratio") not in (None, "")
        ],
        dtype=np.float64,
    )
    kp_radius_relative = np.asarray(
        [
            float(row["keypoint_radius3_fraction_of_reference_bbox_diagonal"])
            for row in coverage_rows
            if row.get("keypoint_radius3_fraction_of_reference_bbox_diagonal")
            not in (None, "")
        ],
        dtype=np.float64,
    )
    return {
        "n_references": n,
        "references_with_inactive_direction": int(np.count_nonzero(inactive_counts > 0)) if n else 0,
        "fraction_with_inactive_direction": float(np.mean(inactive_counts > 0)) if n else None,
        "mean_inactive_direction_count": float(np.mean(inactive_counts)) if n else None,
        "max_inactive_direction_count": int(np.max(inactive_counts)) if n else None,
        "references_without_keypoint_evidence": int(np.count_nonzero(~kp_available)) if n else 0,
        "fraction_without_keypoint_evidence": float(np.mean(~kp_available)) if n else None,
        "median_source_direction_area_max_to_min_ratio": (
            float(np.median(area_ratios)) if len(area_ratios) else None
        ),
        "p95_source_direction_area_max_to_min_ratio": (
            float(np.quantile(area_ratios, 0.95)) if len(area_ratios) else None
        ),
        "max_source_direction_area_max_to_min_ratio": (
            float(np.max(area_ratios)) if len(area_ratios) else None
        ),
        "median_keypoint_radius3_fraction_of_reference_bbox_diagonal": (
            float(np.median(kp_radius_relative)) if len(kp_radius_relative) else None
        ),
        "p05_keypoint_radius3_fraction_of_reference_bbox_diagonal": (
            float(np.quantile(kp_radius_relative, 0.05))
            if len(kp_radius_relative)
            else None
        ),
        "p95_keypoint_radius3_fraction_of_reference_bbox_diagonal": (
            float(np.quantile(kp_radius_relative, 0.95))
            if len(kp_radius_relative)
            else None
        ),
    }


def coverage_summary_by_style(
    coverage_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Apply the same reference-coverage audit separately to each style pack."""

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in coverage_rows:
        grouped[str(row.get("style_id", ""))].append(row)
    output: list[dict[str, Any]] = []
    for style_id in sorted(grouped):
        summary = coverage_summary(grouped[style_id])
        output.append({"style_id": style_id, **summary})
    return output


def component_sensitivity(
    rows: Sequence[Mapping[str, Any]],
    definitions: Iterable[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> list[dict[str, Any]]:
    valid = _valid(rows)
    definitions = tuple(definitions)
    output: list[dict[str, Any]] = []
    for definition in definitions:
        max_severity = float(max(definition.severities))
        subset = [
            row
            for row in valid
            if row.get("perturbation") == definition.name
            and float(row["severity"]) == max_severity
        ]
        if not subset:
            continue
        def mean_loss(
            field: str,
            availability: str | None = None,
            *,
            current_subset: Sequence[Mapping[str, Any]] = subset,
        ) -> float | None:
            values: list[float] = []
            for row in current_subset:
                if availability and not bool(row.get(availability)):
                    continue
                value = _numeric(row, field)
                if value is not None:
                    values.append(1.0 - value)
            return float(np.mean(values)) if values else None

        output.append(
            {
                "perturbation": definition.name,
                "family": definition.family,
                "max_severity": max_severity,
                "severity_unit": definition.unit,
                "n_valid": len(subset),
                "mean_direction_macro_all_loss": mean_loss("direction_macro_all"),
                "mean_direction_macro_active_loss": mean_loss("direction_macro_active"),
                "mean_ink_iou_loss": mean_loss("ink_iou"),
                "mean_keypoint_f1_r3_loss": mean_loss(
                    "keypoint_f1_r3", "keypoint_available"
                ),
                "mean_keypoint_component_center_f1_r3_loss": mean_loss(
                    "keypoint_component_center_f1_r3", "keypoint_available"
                ),
                "mean_v1_current_drop": float(
                    np.mean([float(row["v1_current_drop"]) for row in subset])
                ),
                "mean_v1_coverage_corrected_drop": float(np.mean([float(row["v1_coverage_corrected_drop"]) for row in subset])),
                "mean_v2_nonredundant_candidate_drop": float(np.mean([float(row["v2_nonredundant_candidate_drop"]) for row in subset])),
            }
        )
    return output


def _score_field(variant: str) -> str:
    if variant not in SCORE_VARIANTS:
        raise ValueError(f"unknown score variant: {variant}")
    return variant


def _drop_field(variant: str) -> str:
    return f"{variant}_drop"


def variant_behavior(
    rows: Sequence[Mapping[str, Any]],
    definitions: Iterable[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> list[dict[str, Any]]:
    """Apply the controlled-perturbation behavior checks to each scalar variant."""

    valid = _valid(rows)
    definitions = tuple(definitions)
    output: list[dict[str, Any]] = []

    for variant in SCORE_VARIANTS:
        score_field = _score_field(variant)
        drop_field = _drop_field(variant)
        for definition in definitions:
            all_rows = [row for row in rows if row.get("perturbation") == definition.name]
            subset = [row for row in valid if row.get("perturbation") == definition.name]
            common = {
                "score_variant": variant,
                "perturbation": definition.name,
                "family": definition.family,
                "expected_behavior": definition.expected_behavior,
                "n_valid_observations": len(subset),
                "n_invalid_observations": len(all_rows) - len(subset),
                "valid_fraction": float(len(subset) / len(all_rows)) if all_rows else None,
            }
            if definition.family == "nuisance":
                drops = np.asarray([abs(float(row[drop_field])) for row in subset], dtype=np.float64)
                scores = np.asarray([float(row[score_field]) for row in subset], dtype=np.float64)
                output.append(
                    {
                        **common,
                        "n_complete_curves": "",
                        "mean_abs_score_drop": float(np.mean(drops)) if len(drops) else None,
                        "p95_abs_score_drop": float(np.quantile(drops, 0.95)) if len(drops) else None,
                        "max_abs_score_drop": float(np.max(drops)) if len(drops) else None,
                        "fraction_score_ge_95": float(np.mean(scores >= 95.0)) if len(scores) else None,
                        "mean_sample_spearman_rho": "",
                        "median_sample_spearman_rho": "",
                        "adjacent_nonincreasing_pair_rate": "",
                        "adjacent_strict_decrease_pair_rate": "",
                        "mean_max_score_drop": "",
                        "mean_normalized_drop_auc": "",
                    }
                )
                continue

            configured = tuple(float(value) for value in definition.severities)
            by_reference: dict[str, dict[float, Mapping[str, Any]]] = defaultdict(dict)
            for row in subset:
                by_reference[str(row["reference_id"])][float(row["severity"])] = row
            complete = 0
            rhos: list[float] = []
            pair_count = 0
            nonincreasing = 0
            strict = 0
            max_drops: list[float] = []
            aucs: list[float] = []
            for severity_map in by_reference.values():
                for first_severity, second_severity in pairwise(configured):
                    if first_severity not in severity_map or second_severity not in severity_map:
                        continue
                    first_score = float(severity_map[first_severity][score_field])
                    second_score = float(severity_map[second_severity][score_field])
                    pair_count += 1
                    if second_score <= first_score + 1e-9:
                        nonincreasing += 1
                    if second_score < first_score - 1e-6:
                        strict += 1
                if any(severity not in severity_map for severity in configured):
                    continue
                complete += 1
                scores = [float(severity_map[severity][score_field]) for severity in configured]
                drops = [float(severity_map[severity][drop_field]) for severity in configured]
                rho = spearman_rho(configured, scores)
                if rho is not None:
                    rhos.append(rho)
                max_drops.append(drops[-1])
                max_severity = configured[-1]
                x = [0.0] + [value / max_severity for value in configured]
                y = [0.0] + drops
                auc = sum(
                    (x1 - x0) * (y0 + y1) / 2.0
                    for x0, x1, y0, y1 in zip(x[:-1], x[1:], y[:-1], y[1:], strict=True)
                )
                aucs.append(float(auc))
            output.append(
                {
                    **common,
                    "n_complete_curves": complete,
                    "mean_abs_score_drop": "",
                    "p95_abs_score_drop": "",
                    "max_abs_score_drop": "",
                    "fraction_score_ge_95": "",
                    "mean_sample_spearman_rho": float(np.mean(rhos)) if rhos else None,
                    "median_sample_spearman_rho": float(np.median(rhos)) if rhos else None,
                    "adjacent_nonincreasing_pair_rate": float(nonincreasing / pair_count) if pair_count else None,
                    "adjacent_strict_decrease_pair_rate": float(strict / pair_count) if pair_count else None,
                    "mean_max_score_drop": float(np.mean(max_drops)) if max_drops else None,
                    "mean_normalized_drop_auc": float(np.mean(aucs)) if aucs else None,
                }
            )
    return output


def variant_overall_summary(
    rows: Sequence[Mapping[str, Any]],
    definitions: Iterable[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> list[dict[str, Any]]:
    """Macro-average max-severity behavior over perturbation definitions.

    Each perturbation definition receives one vote after averaging over valid
    references. This avoids silently giving more aggregate weight to a
    perturbation merely because fewer of its observations were invalidated by
    clipping or another preregistered validity rule.
    """

    definitions = tuple(definitions)
    valid = _valid(rows)
    behavior = variant_behavior(rows, definitions)
    output: list[dict[str, Any]] = []
    for variant in SCORE_VARIANTS:
        nuisance_definition_means: list[float] = []
        structural_definition_means: list[float] = []
        for definition in definitions:
            maximum = float(max(definition.severities))
            subset = [
                row
                for row in valid
                if row.get("perturbation") == definition.name
                and math.isclose(
                    float(row["severity"]),
                    maximum,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
            ]
            if not subset:
                continue
            values = [
                abs(float(row[_drop_field(variant)]))
                if definition.family == "nuisance"
                else float(row[_drop_field(variant)])
                for row in subset
            ]
            mean_value = float(np.mean(values))
            if definition.family == "nuisance":
                nuisance_definition_means.append(mean_value)
            elif definition.family == "structural":
                structural_definition_means.append(mean_value)

        structural_behavior = [
            row
            for row in behavior
            if row["score_variant"] == variant and row["family"] == "structural"
        ]
        noninc_pairs = [
            float(row["adjacent_nonincreasing_pair_rate"])
            for row in structural_behavior
            if row["adjacent_nonincreasing_pair_rate"] not in (None, "")
        ]
        rhos = [
            float(row["median_sample_spearman_rho"])
            for row in structural_behavior
            if row["median_sample_spearman_rho"] not in (None, "")
        ]
        nuisance_mean = (
            float(np.mean(nuisance_definition_means))
            if nuisance_definition_means
            else None
        )
        structural_mean = (
            float(np.mean(structural_definition_means))
            if structural_definition_means
            else None
        )
        output.append(
            {
                "score_variant": variant,
                "n_nuisance_perturbations_in_macro": len(nuisance_definition_means),
                "n_structural_perturbations_in_macro": len(structural_definition_means),
                "max_severity_nuisance_mean_abs_drop": nuisance_mean,
                "max_severity_structural_mean_drop": structural_mean,
                "structural_minus_nuisance_drop": (
                    structural_mean - nuisance_mean
                    if nuisance_mean is not None and structural_mean is not None
                    else None
                ),
                "mean_structural_adjacent_nonincreasing_rate_across_families": (
                    float(np.mean(noninc_pairs)) if noninc_pairs else None
                ),
                "mean_structural_median_spearman_across_families": (
                    float(np.mean(rhos)) if rhos else None
                ),
            }
        )
    return output



def variant_overall_summary_by_style(
    rows: Sequence[Mapping[str, Any]],
    definitions: Iterable[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> list[dict[str, Any]]:
    """Macro score-variant behavior split by reference style."""

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("style_id", ""))].append(row)
    output: list[dict[str, Any]] = []
    for style_id in sorted(grouped):
        for summary in variant_overall_summary(grouped[style_id], definitions):
            output.append({"style_id": style_id, **summary})
    return output


def weight_sensitivity_grid(
    rows: Sequence[Mapping[str, Any]],
    definitions: Iterable[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
    step: float = 0.05,
) -> list[dict[str, Any]]:
    """Audit how strongly conclusions depend on the arbitrary v1 weight triple.

    This is a *sensitivity analysis*, not a tuning routine.  It intentionally
    leaves the current evidence semantics unchanged (all-five direction macro,
    ink IoU, current KP F1) and sweeps the unit simplex.  The output must not be
    used to pick weights and then claim the same perturbation suite as an
    independent validation benchmark.
    """

    if step <= 0 or step > 1:
        raise ValueError("weight-grid step must be in (0, 1]")
    divisions_float = 1.0 / float(step)
    divisions = round(divisions_float)
    if not math.isclose(divisions * float(step), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("weight-grid step must divide 1 exactly within tolerance")

    definitions = tuple(definitions)
    valid = [row for row in _valid(rows) if row.get("family") != "baseline"]
    configured = {
        definition.name: tuple(float(value) for value in definition.severities)
        for definition in definitions
    }
    maximum = {name: max(values) for name, values in configured.items()}

    def row_score(row: Mapping[str, Any], wd: float, wi: float, wk: float) -> float:
        return float(
            100.0
            * (
                wd * float(row["direction_macro_all"])
                + wi * float(row["ink_iou"])
                + wk * float(row["keypoint_f1_r3"])
            )
        )

    output: list[dict[str, Any]] = []
    for direction_units in range(divisions + 1):
        for ink_units in range(divisions - direction_units + 1):
            keypoint_units = divisions - direction_units - ink_units
            wd = direction_units / divisions
            wi = ink_units / divisions
            wk = keypoint_units / divisions
            max_rows = [
                row
                for row in valid
                if str(row["perturbation"]) in maximum
                and math.isclose(
                    float(row["severity"]),
                    maximum[str(row["perturbation"])],
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
            ]

            # Macro-average over perturbation definitions, rather than pooling
            # all surviving observations. This prevents validity/clipping rates
            # from implicitly changing the weight assigned to a perturbation.
            max_drop_means: dict[str, float] = {}
            for perturbation, maximum_severity in maximum.items():
                subset = [
                    row
                    for row in max_rows
                    if str(row["perturbation"]) == perturbation
                    and math.isclose(
                        float(row["severity"]),
                        maximum_severity,
                        rel_tol=0.0,
                        abs_tol=1e-12,
                    )
                ]
                if subset:
                    max_drop_means[perturbation] = float(
                        np.mean([100.0 - row_score(row, wd, wi, wk) for row in subset])
                    )

            nuisance_definition_means = [
                max_drop_means[definition.name]
                for definition in definitions
                if definition.family == "nuisance"
                and definition.name in max_drop_means
            ]
            structural_definition_means = [
                max_drop_means[definition.name]
                for definition in definitions
                if definition.family == "structural"
                and definition.name in max_drop_means
            ]
            keypoint_max_drops = [
                100.0 - row_score(row, wd, wi, wk)
                for row in max_rows
                if row.get("perturbation") == "keypoint_shift"
            ]

            by_curve: dict[tuple[str, str], dict[float, float]] = defaultdict(dict)
            for row in valid:
                if row.get("family") != "structural":
                    continue
                key = (str(row["perturbation"]), str(row["reference_id"]))
                by_curve[key][float(row["severity"])] = row_score(row, wd, wi, wk)

            pair_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
            for (perturbation, _reference_id), severity_map in by_curve.items():
                for first, second in zip(
                    configured[perturbation][:-1],
                    configured[perturbation][1:],
                    strict=True,
                ):
                    if first not in severity_map or second not in severity_map:
                        continue
                    pair_stats[perturbation][0] += 1
                    if severity_map[second] <= severity_map[first] + 1e-9:
                        pair_stats[perturbation][1] += 1
                    if severity_map[second] < severity_map[first] - 1e-6:
                        pair_stats[perturbation][2] += 1

            nonincreasing_rates = [
                nonincreasing / pair_count
                for pair_count, nonincreasing, _strict in pair_stats.values()
                if pair_count
            ]
            strict_rates = [
                strict / pair_count
                for pair_count, _nonincreasing, strict in pair_stats.values()
                if pair_count
            ]
            nuisance_mean = (
                float(np.mean(nuisance_definition_means))
                if nuisance_definition_means
                else None
            )
            structural_mean = (
                float(np.mean(structural_definition_means))
                if structural_definition_means
                else None
            )
            output.append(
                {
                    "direction_weight": wd,
                    "ink_weight": wi,
                    "keypoint_weight": wk,
                    "is_current_0.55_0.25_0.20": bool(
                        math.isclose(wd, 0.55, abs_tol=1e-12)
                        and math.isclose(wi, 0.25, abs_tol=1e-12)
                        and math.isclose(wk, 0.20, abs_tol=1e-12)
                    ),
                    "max_severity_nuisance_mean_drop": nuisance_mean,
                    "max_severity_structural_mean_drop": structural_mean,
                    "structural_minus_nuisance_drop": (
                        structural_mean - nuisance_mean
                        if structural_mean is not None and nuisance_mean is not None
                        else None
                    ),
                    "keypoint_shift_max_mean_drop": (
                        float(np.mean(keypoint_max_drops)) if keypoint_max_drops else None
                    ),
                    "structural_adjacent_nonincreasing_pair_rate": (
                        float(np.mean(nonincreasing_rates))
                        if nonincreasing_rates
                        else None
                    ),
                    "structural_adjacent_strict_decrease_pair_rate": (
                        float(np.mean(strict_rates)) if strict_rates else None
                    ),
                }
            )
    return output


def summarize_weight_sensitivity(grid: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    current = next(
        (row for row in grid if bool(row.get("is_current_0.55_0.25_0.20"))),
        None,
    )
    if current is None:
        raise ValueError("weight sensitivity grid does not contain current 0.55/0.25/0.20 weights")

    cur_nuisance = float(current["max_severity_nuisance_mean_drop"])
    cur_structural = float(current["max_severity_structural_mean_drop"])
    cur_monotonic = float(current["structural_adjacent_nonincreasing_pair_rate"])
    weakly_dominating = []
    for row in grid:
        nuisance = float(row["max_severity_nuisance_mean_drop"])
        structural = float(row["max_severity_structural_mean_drop"])
        monotonic = float(row["structural_adjacent_nonincreasing_pair_rate"])
        no_worse = (
            nuisance <= cur_nuisance + 1e-9
            and structural >= cur_structural - 1e-9
            and monotonic >= cur_monotonic - 1e-9
        )
        strictly_better = (
            nuisance < cur_nuisance - 1e-9
            or structural > cur_structural + 1e-9
            or monotonic > cur_monotonic + 1e-9
        )
        if no_worse and strictly_better:
            weakly_dominating.append(row)

    return {
        "n_weight_triples": len(grid),
        "grid_step": (
            None
            if len(grid) < 2
            else min(
                value
                for row in grid
                for value in (
                    float(row["direction_weight"]),
                    float(row["ink_weight"]),
                    float(row["keypoint_weight"]),
                )
                if value > 0
            )
        ),
        "current": dict(current),
        "n_triples_weakly_dominating_current_on_aggregate_diagnostics": len(weakly_dominating),
        "warning": (
            "Dominance on this synthetic/controlled diagnostic is not a license to retune weights: "
            "the apparent optimum changes with the chosen perturbation families and their relative frequency."
        ),
    }

def audit_invariants(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid = _valid(rows)
    parity_errors = np.asarray(
        [abs(float(row["v1_recompute_minus_production"])) for row in valid], dtype=np.float64
    )
    objective_diffs = np.asarray(
        [abs(float(row["ink_iou_minus_alignment_objective"])) for row in valid], dtype=np.float64
    )
    coverage_deltas = np.asarray(
        [float(row["v1_coverage_corrected"]) - float(row["v1_current"]) for row in valid],
        dtype=np.float64,
    )
    identity = [row for row in valid if row.get("family") == "baseline"]
    return {
        "n_valid_rows": len(valid),
        "n_invalid_rows": len(rows) - len(valid),
        "max_abs_v1_recompute_minus_production": float(np.max(parity_errors)) if len(parity_errors) else None,
        "max_abs_ink_iou_minus_alignment_objective": float(np.max(objective_diffs)) if len(objective_diffs) else None,
        "identity_min_v1": min((float(row["v1_current"]) for row in identity), default=None),
        "identity_min_coverage_corrected": min((float(row["v1_coverage_corrected"]) for row in identity), default=None),
        "identity_min_nonredundant": min((float(row["v2_nonredundant_candidate"]) for row in identity), default=None),
        "max_coverage_corrected_minus_v1": float(np.max(coverage_deltas)) if len(coverage_deltas) else None,
        "n_rows_coverage_score_changed": int(np.count_nonzero(np.abs(coverage_deltas) > 1e-9)),
        "mean_downward_coverage_correction_points": (
            float(np.mean(np.maximum(0.0, -coverage_deltas))) if len(coverage_deltas) else None
        ),
        "max_downward_coverage_correction_points": (
            float(np.max(np.maximum(0.0, -coverage_deltas))) if len(coverage_deltas) else None
        ),
        "rows_with_alignment_lost_direction_evidence": sum(
            1 for row in valid if int(row.get("alignment_lost_direction_count", 0)) > 0
        ),
        "rows_with_alignment_lost_keypoint_evidence": sum(
            1 for row in valid if bool(row.get("alignment_lost_keypoint_evidence"))
        ),
        "empty_direction_credit_rows": sum(
            1 for row in valid if float(row["empty_direction_macro_credit"]) > 1e-12
        ),
        "keypoint_empty_credit_rows": sum(
            1 for row in valid if bool(row["keypoint_empty_credit_exposed"])
        ),
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        ordered: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    ordered.append(str(key))
        fields = ordered
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _fmt(value: Any, digits: int = 3) -> str:
    if value in (None, ""):
        return "—"
    if isinstance(value, (float, np.floating)):
        numeric = float(value)
        if abs(numeric) < 0.5 * (10.0 ** (-digits)):
            numeric = 0.0
        return f"{numeric:.{digits}f}"
    return str(value)


def write_structure_score_audit_outputs(
    output_dir: str | Path,
    rows: Sequence[Mapping[str, Any]],
    coverage_rows: Sequence[Mapping[str, Any]],
    input_metadata: Mapping[str, Any],
    runtime_metadata: Mapping[str, Any] | None = None,
    definitions: Iterable[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "BLOCKED.md").unlink(missing_ok=True)
    definitions = tuple(definitions)

    correlations = component_correlations(rows)
    keypoint_comparison = keypoint_metric_comparison(rows)
    score_correlations = variant_correlations(rows)
    sensitivity = component_sensitivity(rows, definitions)
    behavior = variant_behavior(rows, definitions)
    overall = variant_overall_summary(rows, definitions)
    overall_by_style = variant_overall_summary_by_style(rows, definitions)
    weight_grid = weight_sensitivity_grid(rows, definitions, step=0.05)
    weight_summary = summarize_weight_sensitivity(weight_grid)
    coverage = coverage_summary(coverage_rows)
    coverage_by_style = coverage_summary_by_style(coverage_rows)
    invariants = audit_invariants(rows)

    _write_csv(output / "score_audit_results.csv", rows, RESULT_FIELDS)
    _write_csv(output / "reference_coverage.csv", coverage_rows)
    _write_csv(output / "component_correlation.csv", correlations)
    _write_csv(output / "keypoint_metric_comparison.csv", keypoint_comparison)
    _write_csv(output / "component_sensitivity.csv", sensitivity)
    _write_csv(output / "score_variant_correlation.csv", score_correlations)
    _write_csv(output / "score_variant_behavior.csv", behavior)
    _write_csv(output / "score_variant_overall.csv", overall)
    _write_csv(output / "score_variant_overall_by_style.csv", overall_by_style)
    _write_csv(output / "reference_coverage_by_style.csv", coverage_by_style)
    _write_csv(output / "weight_sensitivity_grid.csv", weight_grid)

    report = {
        "audit_name": AUDIT_NAME,
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "score_variants": {
            "v1_current": "100*(0.55*all-5 direction macro Dice + 0.25*ink IoU + 0.20*KP tolerant F1@3px)",
            "v1_coverage_corrected": "same evidence families/weights; active-evidence alternative excluding both-empty direction channels and omitting both-empty KP with weight renormalization",
            "v2_nonredundant_candidate": "coverage-aware; ink IoU retained as alignment/diagnostic only; original 0.55:0.20 direction:KP ratio renormalized over available evidence",
        },
        "input": dict(input_metadata),
        "runtime": dict(runtime_metadata or {}),
        "invariants": invariants,
        "coverage": coverage,
        "coverage_by_style": coverage_by_style,
        "component_correlation": correlations,
        "keypoint_metric_comparison": keypoint_comparison,
        "component_sensitivity": sensitivity,
        "score_variant_correlation": score_correlations,
        "score_variant_behavior": behavior,
        "score_variant_overall": overall,
        "score_variant_overall_by_style": overall_by_style,
        "weight_sensitivity": weight_summary,
        "interpretation_guardrails": [
            "This audit does not calibrate an aesthetic/calligraphy grade.",
            "No score weights are fit to controlled perturbation outcomes.",
            "The active-evidence and no-ink formulas are audit candidates until annotation semantics, real-reference behavior, and expert-rating validation are complete.",
            "Synthetic smoke results validate implementation behavior only and must not be reported as paper results.",
        ],
    }
    (output / "structure_score_audit_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    corr_lookup = {
        (row["subset"], row["component_a"], row["component_b"]): row
        for row in correlations
    }
    structural_dir_ink = corr_lookup.get(
        ("structural", "direction_macro_active", "ink_iou")
    )
    kp_comparison_lookup = {
        str(row["subset"]): row for row in keypoint_comparison
    }
    structural_kp_comparison = kp_comparison_lookup.get("structural")
    keypoint_shift_comparison = kp_comparison_lookup.get(
        "perturbation:keypoint_shift"
    )
    lines = [
        "# OneStroke Structure Score Audit",
        "",
        "> This report audits scalar aggregation after the existing production-equivalent alignment. It does not replace the production score.",
        "",
        "## Hard invariants",
        "",
        f"- Max |recomputed v1 - production-reported score|: **{_fmt(invariants['max_abs_v1_recompute_minus_production'], 9)}**",
        f"- Max |final ink IoU - alignment objective IoU|: **{_fmt(invariants['max_abs_ink_iou_minus_alignment_objective'], 9)}**",
        f"- Valid / invalid audit rows: **{invariants['n_valid_rows']} / {invariants['n_invalid_rows']}**",
        f"- Max (coverage-corrected - current): **{_fmt(invariants['max_coverage_corrected_minus_v1'], 9)}** points",
        "",
        "The second line directly audits the double-role of ink IoU: the same overlap quantity used to select alignment is also assigned 25% of the current final scalar. The active-evidence candidate is deliberately conservative in score magnitude: it may remove empty-channel uplift but must not increase the v1 score. Whether that uplift is inappropriate depends on the annotation ontology, because a true semantic absence can itself be meaningful agreement.",
        "",
        "## Evidence coverage",
        "",
        f"- References with >=1 both-empty direction channel: **{coverage['references_with_inactive_direction']} / {coverage['n_references']}**",
        f"- References with no keypoint evidence: **{coverage['references_without_keypoint_evidence']} / {coverage['n_references']}**",
        f"- Valid rows receiving direction-macro inflation from both-empty channels: **{invariants['empty_direction_credit_rows']}**",
        f"- Valid rows where both-empty keypoints are treated as F1=1 by v1: **{invariants['keypoint_empty_credit_rows']}**",
        f"- Rows changed by coverage correction: **{invariants['n_rows_coverage_score_changed']}**",
        f"- Mean / max downward coverage correction: **{_fmt(invariants['mean_downward_coverage_correction_points'])} / {_fmt(invariants['max_downward_coverage_correction_points'])}** points",
        f"- Rows where alignment removed an originally present direction/KP evidence channel: **{invariants['rows_with_alignment_lost_direction_evidence']} / {invariants['rows_with_alignment_lost_keypoint_evidence']}**",
        f"- Source direction-area max/min ratio, median / p95 / max: **{_fmt(coverage['median_source_direction_area_max_to_min_ratio'])} / {_fmt(coverage['p95_source_direction_area_max_to_min_ratio'])} / {_fmt(coverage['max_source_direction_area_max_to_min_ratio'])}**",
        f"- KP radius 3 px / reference ink-bbox diagonal, p05 / median / p95: **{_fmt(coverage['p05_keypoint_radius3_fraction_of_reference_bbox_diagonal'], 5)} / {_fmt(coverage['median_keypoint_radius3_fraction_of_reference_bbox_diagonal'], 5)} / {_fmt(coverage['p95_keypoint_radius3_fraction_of_reference_bbox_diagonal'], 5)}**",
        "",
        "The area-ratio line audits another design choice: v1 gives each active semantic direction equal macro weight even when their pixel areas differ substantially. This is not labeled an error because a small stroke can be semantically important; it is exported for later expert calibration rather than silently replaced by area weighting.",
        "",
        "The KP-radius line checks how constant the current fixed 3 px tolerance is in relative character scale. A wide range would motivate testing a scale-normalized tolerance, not changing production by fiat.",
        "",
        "## Empirical component redundancy",
        "",
        "Structural perturbation loss correlation between active-direction Dice and ink IoU:",
        "",
        f"- Pearson r: **{_fmt(structural_dir_ink.get('pearson_r_loss') if structural_dir_ink else None)}**",
        f"- Spearman rho: **{_fmt(structural_dir_ink.get('spearman_rho_loss') if structural_dir_ink else None)}**",
        "",
        "A high correlation is evidence of redundancy, not by itself proof that ink IoU should be removed. The formal real-reference audit and expert validation remain the decision gates.",
        "",
        "## Keypoint representation audit",
        "",
        "The production scalar uses tolerant **pixel-mask F1**. This audit also measures connected-component-center F1 at the same radii, because downstream keypoint coordinates are represented by component centers.",
        "",
        f"- Structural rows: mean |pixel F1@3 - center F1@3| = **{_fmt(structural_kp_comparison.get('mean_abs_pixel_center_difference_r3') if structural_kp_comparison else None)}**.",
        f"- Keypoint-shift rows: pixel F1@3 mean / center F1@3 mean = **{_fmt(keypoint_shift_comparison.get('pixel_f1_r3_mean') if keypoint_shift_comparison else None)} / {_fmt(keypoint_shift_comparison.get('center_f1_r3_mean') if keypoint_shift_comparison else None)}**.",
        "",
        "A material real-data difference would justify testing a component-center keypoint term as a separate candidate. It is not inserted into the production score in this audit.",
        "",
        "## Controlled-perturbation behavior by score variant",
        "",
        "| Variant | Max-severity nuisance mean | Max-severity structural mean | Separation | Mean structural non-increasing rate | Mean structural median rho |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in overall:
        lines.append(
            "| {score_variant} | {nuisance} | {structural} | {separation} | {noninc} | {rho} |".format(
                score_variant=row["score_variant"],
                nuisance=_fmt(row["max_severity_nuisance_mean_abs_drop"]),
                structural=_fmt(row["max_severity_structural_mean_drop"]),
                separation=_fmt(row["structural_minus_nuisance_drop"]),
                noninc=_fmt(row["mean_structural_adjacent_nonincreasing_rate_across_families"]),
                rho=_fmt(row["mean_structural_median_spearman_across_families"]),
            )
        )

    lines.extend(
        [
            "",
            "## Style-stratified aggregate check",
            "",
            "| Style | Variant | Nuisance max-severity mean | Structural max-severity mean | Separation |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in overall_by_style:
        lines.append(
            "| {style} | {variant} | {nuisance} | {structural} | {separation} |".format(
                style=row["style_id"] or "(missing style_id)",
                variant=row["score_variant"],
                nuisance=_fmt(row["max_severity_nuisance_mean_abs_drop"]),
                structural=_fmt(row["max_severity_structural_mean_drop"]),
                separation=_fmt(row["structural_minus_nuisance_drop"]),
            )
        )
    lines.extend(
        [
            "",
            "The style table is diagnostic rather than a fairness claim. It is intended to expose whether one reference pack drives the aggregate behavior.",
            "",
            "## Weight sensitivity (diagnostic only)",
            "",
            f"- Simplex grid size: **{weight_summary['n_weight_triples']}** weight triples at 0.05 increments.",
            f"- Triples that weakly dominate 0.55/0.25/0.20 on the aggregate nuisance/structural/monotonic diagnostics: **{weight_summary['n_triples_weakly_dominating_current_on_aggregate_diagnostics']}**.",
            "",
            "This does **not** mean those triples are better weights. It demonstrates the opposite methodological point: a controlled perturbation suite can be gamed by changing the relative weight placed on the perturbation families represented in that suite. Therefore the perturbation benchmark is suitable for auditing behavior, but not for calibrating the final user-facing scalar.",
            "",
            "## Decision rule",
            "",
            "1. `v1_current` remains the production baseline.",
            "2. `v1_coverage_corrected` is only a justified production change if the annotation ontology supports treating both-empty channels as unavailable evidence and real reference/user masks expose the condition at a meaningful rate.",
            "3. `v2_nonredundant_candidate` is not promoted merely because synthetic perturbation metrics look better. It must preserve nuisance robustness and structural monotonicity on the approved real-reference cache, then be compared against blinded expert structural ratings.",
            "4. Do not fit or select scalar weights on the same controlled perturbation benchmark that is later used as the headline validation experiment.",
        ]
    )
    (output / "structure_score_audit_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return report
