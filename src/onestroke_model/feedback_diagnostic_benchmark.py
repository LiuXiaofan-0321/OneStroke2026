"""Paired feedback-rule diagnostic on deterministic real-reference perturbations."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from onestroke_model.constants import CHANNELS
from onestroke_model.controlled_perturbations import (
    DEFAULT_PERTURBATIONS,
    PerturbationDefinition,
    PreparedReferenceScorer,
    apply_perturbation,
)
from onestroke_model.feedback_diagnostic_rules import (
    RULE_VARIANTS,
    diagnostic_findings,
    finding_ids,
)

BENCHMARK_NAME = "onestroke_feedback_diagnostic_v1"

PRIMARY_CAUSE = {
    "global_translation": "layout_center_offset",
    "global_scale_up": "layout_ink_scale",
    "global_scale_down": "layout_ink_scale",
    "direction_terminal_deletion": "local_direction_structure",
    "extra_direction_fragment": "local_direction_structure",
    "local_fragment_shift": "local_direction_structure",
    "direction_width_dilate": "local_direction_structure",
    "direction_width_erode": "local_direction_structure",
    "keypoint_shift": "keypoint_relation",
}

EXPECTED_DIFFERENCE = {
    "direction_terminal_deletion": "missing_reference_structure",
    "extra_direction_fragment": "extra_user_structure",
    "direction_width_dilate": "extra_user_structure",
    "direction_width_erode": "missing_reference_structure",
}

SPECIFICITY_ONLY = {"global_rotation", "compound_allowed_transform"}


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["status"])
        writer.writeheader()
        writer.writerows(rows)


def _grid_cells(mask: np.ndarray, grid: int = 3) -> set[str]:
    mask = np.asarray(mask, dtype=bool)
    height, width = mask.shape
    cells: set[str] = set()
    for row in range(grid):
        y0, y1 = row * height // grid, (row + 1) * height // grid
        for column in range(grid):
            x0, x1 = column * width // grid, (column + 1) * width // grid
            if np.any(mask[y0:y1, x0:x1]):
                cells.add(f"r{row}c{column}")
    return cells


def _truth(
    perturbation: str,
    reference_masks: np.ndarray,
    user_masks: np.ndarray,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    primary = PRIMARY_CAUSE.get(perturbation)
    channel = str(metadata.get("target_channel", "")) or None
    affected_regions: set[str] = set()
    difference_type = EXPECTED_DIFFERENCE.get(perturbation)
    if channel in CHANNELS[:5]:
        index = CHANNELS.index(channel)
        changed = np.logical_xor(
            np.asarray(reference_masks, dtype=bool)[..., index],
            np.asarray(user_masks, dtype=bool)[..., index],
        )
        affected_regions = _grid_cells(changed)
    expected_center_direction = None
    if perturbation == "global_translation":
        dx = int(metadata.get("translation_x", 0))
        dy = int(metadata.get("translation_y", 0))
        if dx and dy:
            expected_center_direction = (
                ("down" if dy > 0 else "up")
                + "_"
                + ("right" if dx > 0 else "left")
            )
        elif dx:
            expected_center_direction = "right" if dx > 0 else "left"
        elif dy:
            expected_center_direction = "down" if dy > 0 else "up"
    return {
        "required_finding_ids": [primary] if primary else [],
        "primary_cause": primary,
        "target_channel": channel,
        "difference_type": difference_type,
        "affected_regions": sorted(affected_regions),
        "expected_center_direction": expected_center_direction,
        "specificity_only": perturbation in SPECIFICITY_ONLY,
    }


def _evaluate(
    findings: Sequence[Mapping[str, object]],
    truth: Mapping[str, Any],
) -> dict[str, Any]:
    ids = finding_ids(findings)
    required = [str(value) for value in truth.get("required_finding_ids", [])]
    primary = truth.get("primary_cause")
    local = next(
        (
            item
            for item in findings
            if str(item.get("finding_id")) == "local_direction_structure"
        ),
        None,
    )
    center = next(
        (
            item
            for item in findings
            if str(item.get("finding_id")) == "layout_center_offset"
        ),
        None,
    )
    target_channel = truth.get("target_channel")
    difference_type = truth.get("difference_type")
    affected_regions = set(truth.get("affected_regions", []))
    expected_direction = truth.get("expected_center_direction")
    return {
        "required_recall_at_3": (
            None
            if not required
            else all(value in ids[:3] for value in required)
        ),
        "strict_primary_top1": (
            None if primary is None else bool(ids and ids[0] == primary)
        ),
        "policy_conditioned_recall_at_3": (
            None
            if primary is None
            else primary in ids[:3]
        ),
        "canonical_local_channel_accuracy": (
            None
            if target_channel is None
            else bool(local and local.get("channel") == target_channel)
        ),
        "missing_extra_accuracy": (
            None
            if difference_type is None
            else bool(local and local.get("difference_type") == difference_type)
        ),
        "exact_region_localization": (
            None
            if not affected_regions
            else bool(
                local
                and len(affected_regions) == 1
                and local.get("region") in affected_regions
            )
        ),
        "overlap_region_localization": (
            None
            if not affected_regions
            else bool(local and local.get("region") in affected_regions)
        ),
        "false_positive_specificity": (
            None
            if not truth.get("specificity_only")
            else len(findings) == 0
        ),
        "center_direction_wording_correctness": (
            None
            if expected_direction is None
            else bool(
                center and center.get("center_direction") == expected_direction
            )
        ),
    }


def run_feedback_diagnostic(
    references: Sequence[Mapping[str, Any]],
    definitions: Iterable[PerturbationDefinition] = DEFAULT_PERTURBATIONS,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    definitions = tuple(definitions)
    for reference_index, reference in enumerate(references, start=1):
        masks = np.asarray(reference["masks"], dtype=bool)
        scorer = PreparedReferenceScorer(masks)
        for definition in definitions:
            for severity in definition.severities:
                outcome = apply_perturbation(
                    masks,
                    str(reference["reference_id"]),
                    definition.name,
                    float(severity),
                )
                common = {
                    "reference_id": str(reference["reference_id"]),
                    "style_id": str(reference.get("style_id", "")),
                    "target_char": str(reference.get("target_char", "")),
                    "perturbation": definition.name,
                    "family": definition.family,
                    "severity": float(severity),
                    "valid": outcome.valid,
                    "invalid_reason": outcome.invalid_reason or "",
                    "perturbation_metadata_json": json.dumps(
                        outcome.metadata, ensure_ascii=False, sort_keys=True
                    ),
                }
                if not outcome.valid:
                    rows.append({**common, "rule_variant": "", "status": "invalid"})
                    continue
                evidence, aligned_reference = scorer.score(outcome.masks)
                truth = _truth(
                    definition.name,
                    masks,
                    outcome.masks,
                    outcome.metadata,
                )
                for variant in RULE_VARIANTS:
                    findings = diagnostic_findings(
                        variant,
                        evidence,
                        outcome.masks,
                        aligned_reference,
                        max_findings=3,
                    )
                    rows.append(
                        {
                            **common,
                            "rule_variant": variant,
                            "status": "valid",
                            "score": float(evidence["prototype_structure_score"]),
                            "truth_json": json.dumps(
                                truth, ensure_ascii=False, sort_keys=True
                            ),
                            "findings_json": json.dumps(
                                findings, ensure_ascii=False, sort_keys=True
                            ),
                            **_evaluate(findings, truth),
                        }
                    )
        print(
            f"feedback-diagnostic reference={reference_index}/{len(references)}",
            flush=True,
        )
    return rows


def _mean_boolean(rows: Sequence[Mapping[str, Any]], field: str) -> tuple[int, float | None]:
    values = [bool(row[field]) for row in rows if row.get(field) is not None]
    return len(values), float(np.mean(values)) if values else None


def summarize_feedback_diagnostic(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    valid = [row for row in rows if row.get("status") == "valid"]
    metric_fields = (
        "required_recall_at_3",
        "strict_primary_top1",
        "policy_conditioned_recall_at_3",
        "canonical_local_channel_accuracy",
        "missing_extra_accuracy",
        "exact_region_localization",
        "overlap_region_localization",
        "false_positive_specificity",
        "center_direction_wording_correctness",
    )
    summaries: list[dict[str, Any]] = []
    by_variant: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in valid:
        by_variant[str(row["rule_variant"])].append(row)
    for variant in RULE_VARIANTS:
        variant_rows = by_variant[variant]
        record: dict[str, Any] = {
            "rule_variant": variant,
            "n_valid_observations": len(variant_rows),
        }
        for field in metric_fields:
            count, value = _mean_boolean(variant_rows, field)
            record[f"{field}_n"] = count
            record[field] = value
        summaries.append(record)

    paired: dict[str, Any] = {"metrics": {}, "regressions": [], "improvements": []}
    by_key: defaultdict[tuple[str, str, float], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in valid:
        key = (
            str(row["reference_id"]),
            str(row["perturbation"]),
            float(row["severity"]),
        )
        by_key[key][str(row["rule_variant"])] = row
    for field in metric_fields:
        improvements = 0
        regressions = 0
        ties = 0
        eligible = 0
        for key, variants in by_key.items():
            if set(variants) != set(RULE_VARIANTS):
                continue
            before = variants["legacy-v1"].get(field)
            after = variants["current"].get(field)
            if before is None or after is None:
                continue
            eligible += 1
            if bool(after) and not bool(before):
                improvements += 1
                paired["improvements"].append({"metric": field, "observation": key})
            elif bool(before) and not bool(after):
                regressions += 1
                paired["regressions"].append({"metric": field, "observation": key})
            else:
                ties += 1
        paired["metrics"][field] = {
            "eligible_pairs": eligible,
            "improvements": improvements,
            "regressions": regressions,
            "ties": ties,
        }
    paired["invalid_observation_count"] = sum(
        1 for row in rows if row.get("status") == "invalid"
    )
    paired["invalid_reason_counts"] = dict(
        Counter(
            str(row.get("invalid_reason", ""))
            for row in rows
            if row.get("status") == "invalid"
        )
    )
    return summaries, paired


def write_feedback_diagnostic_outputs(
    output_dir: str | Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    input_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    output = Path(output_dir)
    before = output / "before"
    after = output / "after"
    paired_dir = output / "paired_comparison"
    for path in (before, after, paired_dir):
        path.mkdir(parents=True, exist_ok=True)
    valid = [row for row in rows if row.get("status") == "valid"]
    _write_csv(output / "feedback_diagnostic_results.csv", rows)
    _write_csv(
        before / "feedback_diagnostic_results.csv",
        [row for row in valid if row.get("rule_variant") == "legacy-v1"],
    )
    _write_csv(
        after / "feedback_diagnostic_results.csv",
        [row for row in valid if row.get("rule_variant") == "current"],
    )
    summaries, paired = summarize_feedback_diagnostic(rows)
    _write_csv(output / "feedback_diagnostic_summary.csv", summaries)
    (paired_dir / "paired_comparison.json").write_text(
        json.dumps(paired, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report = {
        "schema_version": 1,
        "benchmark_name": BENCHMARK_NAME,
        "input": dict(input_metadata),
        "summary": summaries,
        "paired_comparison": paired,
        "interpretation_guardrails": [
            "Ground truth is the deterministic perturbation generator, not an expert aesthetic label.",
            "The benchmark evaluates rule diagnosis, not LLM prose quality.",
            "Legacy and current variants consume identical references, perturbations, alignments and scores.",
            "No score, alignment, segmentation threshold or production feedback rule is changed by this benchmark.",
        ],
    }
    (output / "feedback_diagnostic_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Feedback Diagnostic Formal Report",
        "",
        "> Paired rule diagnostic on deterministic mask perturbations. This is not an expert aesthetic evaluation.",
        "",
        "| Variant | Recall@3 | Top-1 | Local channel | Missing/extra | Region overlap | Specificity | Center direction |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    def value(row: Mapping[str, Any], field: str) -> str:
        raw = row.get(field)
        return "-" if raw is None else f"{float(raw):.3f}"

    for row in summaries:
        lines.append(
            "| {variant} | {recall} | {top1} | {channel} | {kind} | {region} | {specificity} | {direction} |".format(
                variant=row["rule_variant"],
                recall=value(row, "required_recall_at_3"),
                top1=value(row, "strict_primary_top1"),
                channel=value(row, "canonical_local_channel_accuracy"),
                kind=value(row, "missing_extra_accuracy"),
                region=value(row, "overlap_region_localization"),
                specificity=value(row, "false_positive_specificity"),
                direction=value(row, "center_direction_wording_correctness"),
            )
        )
    lines.extend(
        [
            "",
            f"- Paired improvements: **{len(paired['improvements'])}**",
            f"- Paired regressions: **{len(paired['regressions'])}**",
            "",
            "Production behavior must not be changed solely from this controlled diagnostic.",
            "",
        ]
    )
    (output / "FEEDBACK_DIAGNOSTIC_FORMAL_REPORT.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    return report
