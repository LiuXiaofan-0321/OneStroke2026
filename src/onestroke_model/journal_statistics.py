"""Journal-grade statistics derived only from completed formal experiment rows."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from onestroke_model.controlled_perturbations import (
    DEFAULT_PERTURBATIONS,
    PreparedReferenceScorer,
    apply_perturbation,
)
from onestroke_model.perturbation_benchmark import load_reference_cache, spearman_rho


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _float(row: Mapping[str, Any], field: str) -> float:
    return float(row[field])


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _cluster_bootstrap_mean_ci(
    rows: Sequence[Mapping[str, Any]],
    *,
    value_field: str,
    cluster_field: str = "reference_id",
    iterations: int = 5000,
    seed_key: str,
) -> tuple[float | None, float | None]:
    grouped: defaultdict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row[cluster_field])].append(float(row[value_field]))
    clusters = sorted(grouped)
    if not clusters or iterations <= 0:
        return None, None
    rng = np.random.default_rng(_stable_seed("cluster-bootstrap", seed_key))
    values: list[float] = []
    for _ in range(iterations):
        sampled = rng.choice(clusters, size=len(clusters), replace=True)
        observations = [
            value
            for cluster in sampled
            for value in grouped[str(cluster)]
        ]
        values.append(float(np.mean(observations)))
    return (
        float(np.quantile(values, 0.025)),
        float(np.quantile(values, 0.975)),
    )


def _distribution(values: Sequence[float]) -> dict[str, float | int | None]:
    array = np.asarray(values, dtype=np.float64)
    if not len(array):
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "std_ddof1": None,
            "p05": None,
            "p95": None,
        }
    return {
        "n": len(array),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "std_ddof1": float(np.std(array, ddof=1)) if len(array) > 1 else 0.0,
        "p05": float(np.quantile(array, 0.05)),
        "p95": float(np.quantile(array, 0.95)),
    }


def controlled_perturbation_statistics(
    result_path: str | Path,
    *,
    bootstrap_iterations: int = 5000,
) -> list[dict[str, Any]]:
    """Summarize every perturbation without hiding family-specific weaknesses."""

    rows = _read_csv(Path(result_path))
    definition_map = {item.name: item for item in DEFAULT_PERTURBATIONS}
    output: list[dict[str, Any]] = []
    by_perturbation: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_perturbation[row["perturbation"]].append(row)

    for perturbation, definition in definition_map.items():
        all_rows = by_perturbation[perturbation]
        valid = [row for row in all_rows if row["status"] == "valid"]
        metric_rows: list[dict[str, Any]] = []
        for row in valid:
            raw_drop = _float(row, "score_drop_from_identity")
            metric_rows.append(
                {
                    **row,
                    "analysis_drop": abs(raw_drop)
                    if definition.family == "nuisance"
                    else raw_drop,
                }
            )
        stats = _distribution(
            [float(row["analysis_drop"]) for row in metric_rows]
        )
        ci_low, ci_high = _cluster_bootstrap_mean_ci(
            metric_rows,
            value_field="analysis_drop",
            iterations=bootstrap_iterations,
            seed_key=f"controlled:{perturbation}",
        )

        configured = tuple(float(value) for value in definition.severities)
        grouped: defaultdict[str, dict[float, float]] = defaultdict(dict)
        for row in valid:
            grouped[row["reference_id"]][_float(row, "severity")] = _float(
                row, "prototype_structure_score"
            )
        rhos: list[float] = []
        adjacent_hits = 0
        adjacent_total = 0
        complete_curves = 0
        for severity_map in grouped.values():
            if any(severity not in severity_map for severity in configured):
                continue
            complete_curves += 1
            scores = [severity_map[severity] for severity in configured]
            rho = spearman_rho(configured, scores)
            if rho is not None:
                rhos.append(float(rho))
            for first, second in pairwise(scores):
                adjacent_hits += int(second <= first + 1e-9)
                adjacent_total += 1

        output.append(
            {
                "perturbation": perturbation,
                "family": definition.family,
                "analysis_metric": (
                    "absolute_score_drop"
                    if definition.family == "nuisance"
                    else "score_drop"
                ),
                "n_total": len(all_rows),
                "n_valid": len(valid),
                "n_references_valid": len(grouped),
                "invalid_fraction": (
                    (len(all_rows) - len(valid)) / len(all_rows) if all_rows else None
                ),
                **stats,
                "bootstrap_mean_ci95_low": ci_low,
                "bootstrap_mean_ci95_high": ci_high,
                "n_complete_severity_curves": complete_curves,
                "severity_spearman_mean": (
                    float(np.mean(rhos)) if rhos else None
                ),
                "severity_spearman_median": (
                    float(np.median(rhos)) if rhos else None
                ),
                "adjacent_nonincreasing_rate": (
                    adjacent_hits / adjacent_total if adjacent_total else None
                ),
            }
        )
    return output


def _paired_bootstrap_ci(
    rows: Sequence[Mapping[str, Any]],
    *,
    value_field: str,
    iterations: int,
    seed_key: str,
) -> tuple[float | None, float | None]:
    return _cluster_bootstrap_mean_ci(
        rows,
        value_field=value_field,
        iterations=iterations,
        seed_key=seed_key,
    )


def _rank_biserial(values: Sequence[float]) -> float | None:
    from scipy.stats import rankdata

    array = np.asarray(values, dtype=np.float64)
    array = array[np.abs(array) > 1e-12]
    if not len(array):
        return 0.0
    ranks = rankdata(np.abs(array), method="average")
    denominator = float(np.sum(ranks))
    if denominator <= 0:
        return None
    return float(
        (np.sum(ranks[array > 0]) - np.sum(ranks[array < 0])) / denominator
    )


def _wilcoxon(values: Sequence[float]) -> tuple[float | None, float | None]:
    from scipy.stats import wilcoxon

    array = np.asarray(values, dtype=np.float64)
    if not len(array):
        return None, None
    if np.all(np.abs(array) <= 1e-12):
        return 0.0, 1.0
    result = wilcoxon(array, zero_method="wilcox", alternative="two-sided")
    return float(result.statistic), float(result.pvalue)


def alignment_paired_statistics(
    result_path: str | Path,
    *,
    bootstrap_iterations: int = 5000,
) -> list[dict[str, Any]]:
    """Paired comparison using per-reference inference for uncertainty/tests."""

    rows = [
        row for row in _read_csv(Path(result_path)) if _truthy(row.get("valid"))
    ]
    grouped: defaultdict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        grouped[row["observation_key"]][row["alignment_variant"]] = row

    paired: list[dict[str, Any]] = []
    for variants in grouped.values():
        if not {"no_alignment", "current_constrained", "wide_similarity"}.issubset(
            variants
        ):
            continue
        current = variants["current_constrained"]
        family = current["family"]
        current_metric = abs(_float(current, "score_drop")) if family == "nuisance" else _float(
            current, "score_drop"
        )
        for comparator in ("no_alignment", "wide_similarity"):
            other = variants[comparator]
            comparator_metric = (
                abs(_float(other, "score_drop"))
                if family == "nuisance"
                else _float(other, "score_drop")
            )
            raw_delta = current_metric - comparator_metric
            benefit_delta = (
                comparator_metric - current_metric
                if family == "nuisance"
                else current_metric - comparator_metric
            )
            paired.append(
                {
                    "reference_id": current["reference_id"],
                    "perturbation": current["perturbation"],
                    "family": family,
                    "severity": _float(current, "severity"),
                    "comparator": comparator,
                    "current_metric": current_metric,
                    "comparator_metric": comparator_metric,
                    "raw_delta_current_minus_comparator": raw_delta,
                    "benefit_delta_positive_favors_current": benefit_delta,
                }
            )

    scopes: list[tuple[str, str, str | None]] = [
        ("family", "nuisance", None),
        ("family", "structural", None),
    ]
    for perturbation in sorted({row["perturbation"] for row in paired}):
        family = next(
            row["family"] for row in paired if row["perturbation"] == perturbation
        )
        scopes.append(("perturbation", family, perturbation))

    output: list[dict[str, Any]] = []
    for comparator in ("no_alignment", "wide_similarity"):
        for scope_type, family, perturbation in scopes:
            subset = [
                row
                for row in paired
                if row["comparator"] == comparator
                and row["family"] == family
                and (perturbation is None or row["perturbation"] == perturbation)
            ]
            if not subset:
                continue
            by_reference: defaultdict[str, list[float]] = defaultdict(list)
            for row in subset:
                by_reference[str(row["reference_id"])].append(
                    float(row["benefit_delta_positive_favors_current"])
                )
            reference_means = [
                float(np.mean(values)) for values in by_reference.values()
            ]
            statistic, pvalue = _wilcoxon(reference_means)
            ci_low, ci_high = _paired_bootstrap_ci(
                subset,
                value_field="benefit_delta_positive_favors_current",
                iterations=bootstrap_iterations,
                seed_key=f"alignment:{comparator}:{scope_type}:{family}:{perturbation}",
            )
            output.append(
                {
                    "comparison": f"current_constrained_vs_{comparator}",
                    "scope_type": scope_type,
                    "family": family,
                    "perturbation": perturbation or "",
                    "metric": (
                        "absolute_score_drop"
                        if family == "nuisance"
                        else "score_drop"
                    ),
                    "n_paired_observations": len(subset),
                    "n_reference_pairs": len(by_reference),
                    "current_mean": float(
                        np.mean([float(row["current_metric"]) for row in subset])
                    ),
                    "comparator_mean": float(
                        np.mean([float(row["comparator_metric"]) for row in subset])
                    ),
                    "raw_delta_current_minus_comparator": float(
                        np.mean(
                            [
                                float(row["raw_delta_current_minus_comparator"])
                                for row in subset
                            ]
                        )
                    ),
                    "benefit_delta_positive_favors_current": float(
                        np.mean(
                            [
                                float(
                                    row[
                                        "benefit_delta_positive_favors_current"
                                    ]
                                )
                                for row in subset
                            ]
                        )
                    ),
                    "paired_bootstrap_ci95_low": ci_low,
                    "paired_bootstrap_ci95_high": ci_high,
                    "wilcoxon_unit": "per-reference mean paired difference",
                    "wilcoxon_statistic": statistic,
                    "wilcoxon_p_two_sided": pvalue,
                    "rank_biserial_positive_favors_current": _rank_biserial(
                        reference_means
                    ),
                }
            )
    return output


def structure_score_audit_statistics(
    reference_coverage_path: str | Path,
    score_rows_path: str | Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    coverage = _read_csv(Path(reference_coverage_path))
    score_rows = [
        row
        for row in _read_csv(Path(score_rows_path))
        if row.get("status") == "valid"
    ]

    inactive_distribution: list[dict[str, Any]] = []
    scopes: list[tuple[str, list[dict[str, str]]]] = [("ALL", coverage)]
    by_style: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in coverage:
        by_style[row["style_id"]].append(row)
    scopes.extend(sorted(by_style.items()))
    for style_id, rows in scopes:
        counts = Counter(int(row["inactive_direction_count"]) for row in rows)
        for inactive_count in range(6):
            inactive_distribution.append(
                {
                    "style_id": style_id,
                    "inactive_direction_count": inactive_count,
                    "reference_count": counts[inactive_count],
                    "fraction": counts[inactive_count] / len(rows) if rows else None,
                }
            )

    correction_rows: list[dict[str, Any]] = []
    for row in score_rows:
        correction = _float(row, "v1_current") - _float(
            row, "v1_coverage_corrected"
        )
        correction_rows.append(
            {
                "reference_id": row["reference_id"],
                "style_id": row["style_id"],
                "target_char": row["target_char"],
                "perturbation": row["perturbation"],
                "family": row["family"],
                "severity": _float(row, "severity"),
                "target_channel": row["target_channel"],
                "inactive_direction_count": int(row["inactive_direction_count"]),
                "empty_direction_macro_credit": _float(
                    row, "empty_direction_macro_credit"
                ),
                "direction_macro_all": _float(row, "direction_macro_all"),
                "direction_macro_active": _float(row, "direction_macro_active"),
                "v1_direction_points": _float(row, "v1_direction_points"),
                "v1_current": _float(row, "v1_current"),
                "v1_coverage_corrected": _float(
                    row, "v1_coverage_corrected"
                ),
                "coverage_correction": correction,
            }
        )
    correction_rows.sort(
        key=lambda row: float(row["coverage_correction"]), reverse=True
    )
    top_cases = correction_rows[:25]

    positive = [
        row for row in correction_rows if float(row["coverage_correction"]) > 1e-12
    ]
    qualitative: list[dict[str, Any]] = []
    used: set[tuple[str, str, float]] = set()
    for label, quantile in (
        ("maximum", 1.0),
        ("upper_quartile", 0.75),
        ("median_positive", 0.50),
        ("lower_quartile", 0.25),
        ("near_zero_positive", 0.0),
    ):
        if not positive:
            break
        target = float(
            np.quantile(
                [float(row["coverage_correction"]) for row in positive],
                quantile,
            )
        )
        candidates = sorted(
            positive,
            key=lambda row: (
                abs(float(row["coverage_correction"]) - target),
                row["reference_id"],
                row["perturbation"],
                float(row["severity"]),
            ),
        )
        selected = next(
            (
                row
                for row in candidates
                if (
                    row["reference_id"],
                    row["perturbation"],
                    float(row["severity"]),
                )
                not in used
            ),
            None,
        )
        if selected is None:
            continue
        used.add(
            (
                selected["reference_id"],
                selected["perturbation"],
                float(selected["severity"]),
            )
        )
        qualitative.append({"selection_label": label, **selected})
    return inactive_distribution, top_cases, qualitative


def feedback_failure_taxonomy(
    feedback_path: str | Path,
    score_audit_path: str | Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    feedback = [
        row
        for row in _read_csv(Path(feedback_path))
        if row.get("rule_variant") == "current"
        and row.get("status") == "valid"
        and row.get("exact_region_localization") != ""
        and not _truthy(row.get("exact_region_localization"))
    ]
    transforms = {
        (
            row["reference_id"],
            row["perturbation"],
            float(row["severity"]),
        ): row
        for row in _read_csv(Path(score_audit_path))
        if row.get("status") == "valid"
    }
    detailed: list[dict[str, Any]] = []
    for row in feedback:
        truth = json.loads(row["truth_json"])
        findings = json.loads(row["findings_json"])
        local_index = next(
            (
                index
                for index, finding in enumerate(findings)
                if finding.get("finding_id") == "local_direction_structure"
            ),
            None,
        )
        local = findings[local_index] if local_index is not None else None
        affected = list(truth.get("affected_regions", []))
        no_local = local is None
        wrong_channel = bool(
            local
            and truth.get("target_channel")
            and local.get("channel") != truth.get("target_channel")
        )
        wrong_difference = bool(
            local
            and truth.get("difference_type")
            and local.get("difference_type") != truth.get("difference_type")
        )
        multi_region = len(affected) > 1
        wrong_region = bool(local and local.get("region") not in set(affected))
        transform = transforms.get(
            (
                row["reference_id"],
                row["perturbation"],
                float(row["severity"]),
            ),
            {},
        )
        alignment_nonidentity = bool(
            transform
            and (
                abs(float(transform.get("selected_scale", 1.0)) - 1.0) > 1e-9
                or abs(float(transform.get("selected_rotation_degrees", 0.0)))
                > 1e-9
                or abs(float(transform.get("selected_translation_x", 0.0)))
                > 1e-9
                or abs(float(transform.get("selected_translation_y", 0.0)))
                > 1e-9
            )
        )

        if no_local:
            primary = "local_finding_absent_from_top3"
        elif wrong_channel:
            primary = "wrong_direction_channel"
        elif wrong_difference:
            primary = "wrong_missing_extra_type"
        elif multi_region:
            primary = "multi_region_or_grid_boundary_truth"
        elif wrong_region and alignment_nonidentity:
            primary = "alignment_residual_region_shift"
        elif wrong_region:
            primary = "wrong_grid_region"
        else:
            primary = "other_exact_region_failure"
        detailed.append(
            {
                "reference_id": row["reference_id"],
                "style_id": row["style_id"],
                "target_char": row["target_char"],
                "perturbation": row["perturbation"],
                "severity": float(row["severity"]),
                "primary_failure_type": primary,
                "target_channel": truth.get("target_channel") or "",
                "predicted_channel": local.get("channel", "") if local else "",
                "expected_difference_type": truth.get("difference_type") or "",
                "predicted_difference_type": (
                    local.get("difference_type", "") if local else ""
                ),
                "affected_regions": "|".join(affected),
                "predicted_region": local.get("region", "") if local else "",
                "local_finding_rank": (
                    local_index + 1 if local_index is not None else ""
                ),
                "flag_no_local_finding": no_local,
                "flag_wrong_channel": wrong_channel,
                "flag_wrong_missing_extra": wrong_difference,
                "flag_multi_region_or_boundary": multi_region,
                "flag_wrong_region": wrong_region,
                "flag_alignment_nonidentity": alignment_nonidentity,
            }
        )
    counts = Counter(row["primary_failure_type"] for row in detailed)
    summary = [
        {
            "failure_type": failure_type,
            "count": count,
            "fraction_of_exact_region_failures": count / len(detailed)
            if detailed
            else None,
        }
        for failure_type, count in counts.most_common()
    ]
    return detailed, summary


def build_structure_score_qualitative_figure(
    cases: Sequence[Mapping[str, Any]],
    *,
    cache_index: str | Path,
    output_path: str | Path,
) -> None:
    """Render preregistered quantile cases from real cached masks."""

    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    _, references = load_reference_cache(cache_index)
    by_id = {str(item["reference_id"]): item for item in references}
    figure, axes = plt.subplots(
        len(cases),
        3,
        figsize=(10.5, max(3.0, 2.6 * len(cases))),
        squeeze=False,
    )
    difference_cmap = ListedColormap(["white", "#2b6cb0", "#c53030", "#6b46c1"])
    for row_index, case in enumerate(cases):
        reference = by_id[str(case["reference_id"])]
        reference_masks = np.asarray(reference["masks"], dtype=bool)
        if case["perturbation"] == "identity":
            user_masks = reference_masks.copy()
        else:
            outcome = apply_perturbation(
                reference_masks,
                str(case["reference_id"]),
                str(case["perturbation"]),
                float(case["severity"]),
            )
            if not outcome.valid:
                raise ValueError("selected qualitative case is invalid")
            user_masks = outcome.masks
        _, aligned_reference = PreparedReferenceScorer(reference_masks).score(
            user_masks
        )
        reference_ink = np.any(aligned_reference[..., :5], axis=-1)
        user_ink = np.any(user_masks[..., :5], axis=-1)
        difference = np.zeros(reference_ink.shape, dtype=np.uint8)
        difference[np.logical_and(reference_ink, ~user_ink)] = 1
        difference[np.logical_and(user_ink, ~reference_ink)] = 2
        difference[np.logical_and(reference_ink, user_ink)] = 3

        axes[row_index, 0].imshow(reference_ink, cmap="gray_r")
        axes[row_index, 1].imshow(user_ink, cmap="gray_r")
        axes[row_index, 2].imshow(difference, cmap=difference_cmap, vmin=0, vmax=3)
        label = (
            f"{case['selection_label']}: correction={float(case['coverage_correction']):.3f}\n"
            f"{case['perturbation']} @ {float(case['severity']):g}; "
            f"inactive={case['inactive_direction_count']}"
        )
        axes[row_index, 0].set_ylabel(label, fontsize=8)
        for axis in axes[row_index]:
            axis.set_xticks([])
            axis.set_yticks([])
    axes[0, 0].set_title("Aligned reference ink")
    axes[0, 1].set_title("Perturbed user ink")
    axes[0, 2].set_title("Overlap (purple), missing (blue), extra (red)")
    figure.suptitle(
        "Coverage-correction cases selected by correction quantiles, not appearance",
        fontsize=11,
    )
    figure.tight_layout()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=220, bbox_inches="tight")
    figure.savefig(output.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)


def build_journal_statistics(
    project_root: str | Path,
    *,
    bootstrap_iterations: int = 5000,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    base = root / "artifacts/paper_ijdar"
    output = base / "journal_statistics"
    output.mkdir(parents=True, exist_ok=True)

    controlled = controlled_perturbation_statistics(
        base / "controlled_perturbation/perturbation_results.csv",
        bootstrap_iterations=bootstrap_iterations,
    )
    alignment = alignment_paired_statistics(
        base / "alignment_ablation/alignment_ablation_results.csv",
        bootstrap_iterations=bootstrap_iterations,
    )
    inactive, top_cases, qualitative = structure_score_audit_statistics(
        base / "structure_score_audit/reference_coverage.csv",
        base / "structure_score_audit/score_audit_results.csv",
    )
    failures, failure_summary = feedback_failure_taxonomy(
        base / "feedback_diagnostic/feedback_diagnostic_results.csv",
        base / "structure_score_audit/score_audit_results.csv",
    )

    _write_csv(output / "controlled_perturbation_journal_statistics.csv", controlled)
    _write_csv(output / "alignment_paired_statistics.csv", alignment)
    _write_csv(output / "inactive_channel_distribution.csv", inactive)
    _write_csv(output / "coverage_correction_top_cases.csv", top_cases)
    _write_csv(output / "coverage_qualitative_cases.csv", qualitative)
    _write_csv(output / "feedback_failure_taxonomy.csv", failures)
    _write_csv(output / "feedback_failure_taxonomy_summary.csv", failure_summary)
    build_structure_score_qualitative_figure(
        qualitative,
        cache_index=root / "references/cache/segformer_b2_v1/index.json",
        output_path=output / "coverage_correction_qualitative.png",
    )

    manifest = {
        "schema_version": 1,
        "source_policy": "completed formal per-observation artifacts only",
        "bootstrap_iterations": bootstrap_iterations,
        "bootstrap_unit": "reference",
        "alignment_test_unit": "per-reference mean paired difference",
        "production_configuration_modified": False,
        "files": sorted(
            str(path.relative_to(root))
            for path in output.iterdir()
            if path.is_file()
        ),
    }
    (output / "journal_statistics_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest
