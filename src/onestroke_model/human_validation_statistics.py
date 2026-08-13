"""Paper-grade statistics for the frozen blinded human validation study."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from onestroke_model.expert_validation import _boolish, icc_2_1_and_2_k
from onestroke_model.perturbation_benchmark import spearman_rho


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


def _finite_float(value: Any, *, field: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite, got {value!r}")
    return result


def _spearman_with_p(
    x_values: Sequence[float],
    y_values: Sequence[float],
) -> tuple[float | None, float | None]:
    rho = spearman_rho(x_values, y_values)
    if rho is None:
        return None, None
    try:
        from scipy.stats import spearmanr
    except ImportError:
        return float(rho), None
    result = spearmanr(x_values, y_values)
    return float(result.statistic), float(result.pvalue)


def _character_cluster_bootstrap_correlations(
    rows: Sequence[Mapping[str, Any]],
    *,
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    by_character: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_character[str(row["target_char"])].append(row)
    characters = sorted(by_character)
    if len(characters) < 2 or iterations <= 0:
        return {
            "iterations": iterations,
            "cluster_count": len(characters),
            "current_ci95": [None, None],
            "coverage_aware_ci95": [None, None],
            "coverage_minus_current_ci95": [None, None],
            "coverage_minus_current_two_sided_bootstrap_p": None,
        }

    rng = np.random.default_rng(seed)
    current_values: list[float] = []
    coverage_values: list[float] = []
    differences: list[float] = []
    for _ in range(iterations):
        sampled = rng.choice(characters, size=len(characters), replace=True)
        bootstrap_rows = [
            row
            for character in sampled
            for row in by_character[str(character)]
        ]
        human = [float(row["human_mean"]) for row in bootstrap_rows]
        current = spearman_rho(
            [float(row["system_score"]) for row in bootstrap_rows],
            human,
        )
        coverage = spearman_rho(
            [float(row["coverage_aware_score"]) for row in bootstrap_rows],
            human,
        )
        if current is None or coverage is None:
            continue
        current_values.append(float(current))
        coverage_values.append(float(coverage))
        differences.append(float(coverage - current))

    def interval(values: Sequence[float]) -> list[float | None]:
        if not values:
            return [None, None]
        return [
            float(np.quantile(values, 0.025)),
            float(np.quantile(values, 0.975)),
        ]

    bootstrap_p = None
    if differences:
        difference_array = np.asarray(differences)
        nonpositive = int(np.sum(difference_array <= 0))
        nonnegative = int(np.sum(difference_array >= 0))
        # Add one pseudo-observation so a finite Monte Carlo run never reports
        # an impossible exact p-value of zero.
        bootstrap_p = min(
            1.0,
            2.0 * (min(nonpositive, nonnegative) + 1) / (len(differences) + 1),
        )
    return {
        "iterations": iterations,
        "valid_iterations": len(differences),
        "cluster_count": len(characters),
        "cluster_unit": "target_char",
        "current_ci95": interval(current_values),
        "coverage_aware_ci95": interval(coverage_values),
        "coverage_minus_current_ci95": interval(differences),
        "coverage_minus_current_two_sided_bootstrap_p": bootstrap_p,
    }


def quadratic_weighted_kappa(
    first: Sequence[float],
    second: Sequence[float],
    *,
    minimum_rating: int = 1,
    maximum_rating: int = 5,
) -> float | None:
    """Compute quadratic weighted kappa without a scikit-learn dependency."""

    a = np.asarray(first, dtype=np.int64)
    b = np.asarray(second, dtype=np.int64)
    if a.shape != b.shape:
        raise ValueError("rating arrays must have the same shape")
    if a.ndim != 1:
        raise ValueError("rating arrays must be one-dimensional")
    if not len(a):
        return None
    if (
        np.any(a < minimum_rating)
        or np.any(a > maximum_rating)
        or np.any(b < minimum_rating)
        or np.any(b > maximum_rating)
    ):
        raise ValueError("ratings fall outside the declared scale")

    categories = maximum_rating - minimum_rating + 1
    observed = np.zeros((categories, categories), dtype=np.float64)
    for first_rating, second_rating in zip(a, b, strict=True):
        observed[first_rating - minimum_rating, second_rating - minimum_rating] += 1
    observed /= len(a)

    first_hist = np.bincount(a - minimum_rating, minlength=categories).astype(float)
    second_hist = np.bincount(b - minimum_rating, minlength=categories).astype(float)
    expected = np.outer(first_hist, second_hist) / float(len(a) ** 2)
    denominator = max(1, categories - 1)
    indices = np.arange(categories, dtype=np.float64)
    weights = np.square(indices[:, None] - indices[None, :]) / float(
        denominator**2
    )
    observed_disagreement = float(np.sum(weights * observed))
    expected_disagreement = float(np.sum(weights * expected))
    if expected_disagreement <= 1e-12:
        return 1.0 if observed_disagreement <= 1e-12 else None
    return float(1.0 - observed_disagreement / expected_disagreement)


def _canonical_presentations(
    pair_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_source: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in pair_rows:
        row = dict(raw)
        source_pair_id = str(row.get("source_pair_id", "")).strip()
        blinded_pair_id = str(row.get("blinded_pair_id", "")).strip()
        if not source_pair_id or not blinded_pair_id:
            raise ValueError("pair rows require source_pair_id and blinded_pair_id")
        by_source[source_pair_id].append(row)

    canonical: list[dict[str, Any]] = []
    for source_pair_id, presentations in sorted(by_source.items()):
        originals = [row for row in presentations if not _boolish(row.get("is_repeat"))]
        if len(originals) != 1:
            raise ValueError(
                f"{source_pair_id} must have exactly one non-repeat presentation; "
                f"found {len(originals)}"
            )
        canonical.append(originals[0])
        if len(presentations) > 2:
            raise ValueError(f"{source_pair_id} has more than one hidden repeat")
    return canonical, by_source


def _rating_lookup(
    pair_rows: Sequence[Mapping[str, Any]],
    rating_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[tuple[str, str], float], list[str]]:
    valid_blinded_ids = {str(row["blinded_pair_id"]) for row in pair_rows}
    lookup: dict[tuple[str, str], float] = {}
    evaluators: set[str] = set()
    for row in rating_rows:
        blinded_id = str(row.get("blinded_pair_id", "")).strip()
        evaluator_id = str(row.get("evaluator_id", "")).strip()
        if blinded_id not in valid_blinded_ids:
            raise ValueError(f"unknown blinded_pair_id in ratings: {blinded_id!r}")
        if not evaluator_id:
            raise ValueError("evaluator_id is required")
        rating = _finite_float(
            row.get("rating", row.get("structural_similarity_rating_1_to_5", "")),
            field="rating",
        )
        if rating < 1 or rating > 5 or not float(rating).is_integer():
            raise ValueError(f"rating must be an integer in [1, 5], got {rating}")
        key = (blinded_id, evaluator_id)
        if key in lookup:
            raise ValueError(f"duplicate rating for {blinded_id} by {evaluator_id}")
        lookup[key] = rating
        evaluators.add(evaluator_id)

    evaluator_ids = sorted(evaluators)
    expected = {
        (str(row["blinded_pair_id"]), evaluator)
        for row in pair_rows
        for evaluator in evaluator_ids
    }
    missing = sorted(expected - set(lookup))
    extra_count = len(set(lookup) - expected)
    if missing or extra_count:
        raise ValueError(
            f"ratings must form a complete presentation-by-evaluator matrix; "
            f"missing={len(missing)} extra={extra_count}"
        )
    return lookup, evaluator_ids


def _canonical_rating_rows(
    canonical_pairs: Sequence[Mapping[str, Any]],
    rating_lookup: Mapping[tuple[str, str], float],
    evaluator_ids: Sequence[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in canonical_pairs:
        blinded_id = str(pair["blinded_pair_id"])
        values = [float(rating_lookup[(blinded_id, evaluator)]) for evaluator in evaluator_ids]
        output = {
            **dict(pair),
            "system_score": _finite_float(pair["system_score"], field="system_score"),
            "coverage_aware_score": _finite_float(
                pair["coverage_aware_score"],
                field="coverage_aware_score",
            ),
        }
        for evaluator, value in zip(evaluator_ids, values, strict=True):
            output[f"rating_{evaluator}"] = int(value)
        output.update(
            {
                "human_mean": float(np.mean(values)),
                "human_median": float(np.median(values)),
                "human_std_ddof1": (
                    float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
                ),
                "human_rating_min": int(min(values)),
                "human_rating_max": int(max(values)),
                "human_rating_range": int(max(values) - min(values)),
            }
        )
        rows.append(output)
    return rows


def _per_evaluator_summary(
    canonical_rows: Sequence[Mapping[str, Any]],
    evaluator_ids: Sequence[str],
) -> list[dict[str, Any]]:
    grand_mean = float(
        np.mean([float(row["human_mean"]) for row in canonical_rows])
    )
    output: list[dict[str, Any]] = []
    for evaluator in evaluator_ids:
        ratings = [float(row[f"rating_{evaluator}"]) for row in canonical_rows]
        current_rho, current_p = _spearman_with_p(
            [float(row["system_score"]) for row in canonical_rows],
            ratings,
        )
        coverage_rho, coverage_p = _spearman_with_p(
            [float(row["coverage_aware_score"]) for row in canonical_rows],
            ratings,
        )
        counts = Counter(int(value) for value in ratings)
        output.append(
            {
                "evaluator_id": evaluator,
                "n_canonical_pairs": len(ratings),
                "mean_rating": float(np.mean(ratings)),
                "median_rating": float(np.median(ratings)),
                "std_rating_ddof1": (
                    float(np.std(ratings, ddof=1)) if len(ratings) > 1 else 0.0
                ),
                "mean_offset_from_grand_human_mean": float(np.mean(ratings) - grand_mean),
                "rating_1_count": counts[1],
                "rating_2_count": counts[2],
                "rating_3_count": counts[3],
                "rating_4_count": counts[4],
                "rating_5_count": counts[5],
                "spearman_current_vs_rating": current_rho,
                "spearman_current_p_two_sided": current_p,
                "spearman_coverage_vs_rating": coverage_rho,
                "spearman_coverage_p_two_sided": coverage_p,
            }
        )
    return output


def _repeat_consistency(
    presentations_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    rating_lookup: Mapping[tuple[str, str], float],
    evaluator_ids: Sequence[str],
) -> list[dict[str, Any]]:
    repeat_pairs: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for presentations in presentations_by_source.values():
        if len(presentations) < 2:
            continue
        original = next(
            row for row in presentations if not _boolish(row.get("is_repeat"))
        )
        repeat = next(row for row in presentations if _boolish(row.get("is_repeat")))
        repeat_pairs.append((original, repeat))

    rows: list[dict[str, Any]] = []
    pooled_first: list[float] = []
    pooled_second: list[float] = []
    for evaluator in evaluator_ids:
        first = [
            rating_lookup[(str(original["blinded_pair_id"]), evaluator)]
            for original, _ in repeat_pairs
        ]
        second = [
            rating_lookup[(str(repeat["blinded_pair_id"]), evaluator)]
            for _, repeat in repeat_pairs
        ]
        pooled_first.extend(first)
        pooled_second.extend(second)
        difference = np.abs(np.asarray(first) - np.asarray(second))
        rows.append(
            {
                "evaluator_id": evaluator,
                "n_hidden_repeat_pairs": len(first),
                "exact_agreement_rate": float(np.mean(difference == 0)),
                "within_one_agreement_rate": float(np.mean(difference <= 1)),
                "mean_absolute_difference": float(np.mean(difference)),
                "quadratic_weighted_kappa": quadratic_weighted_kappa(first, second),
            }
        )
    pooled_difference = np.abs(
        np.asarray(pooled_first, dtype=float) - np.asarray(pooled_second, dtype=float)
    )
    rows.append(
        {
            "evaluator_id": "POOLED",
            "n_hidden_repeat_pairs": len(pooled_first),
            "exact_agreement_rate": float(np.mean(pooled_difference == 0)),
            "within_one_agreement_rate": float(np.mean(pooled_difference <= 1)),
            "mean_absolute_difference": float(np.mean(pooled_difference)),
            "quadratic_weighted_kappa": quadratic_weighted_kappa(
                pooled_first,
                pooled_second,
            ),
        }
    )
    return rows


def _per_character_summary(
    canonical_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in canonical_rows:
        grouped[str(row["target_char"])].append(row)
    output: list[dict[str, Any]] = []
    for character, rows in sorted(grouped.items()):
        current_rho, _ = _spearman_with_p(
            [float(row["system_score"]) for row in rows],
            [float(row["human_mean"]) for row in rows],
        )
        coverage_rho, _ = _spearman_with_p(
            [float(row["coverage_aware_score"]) for row in rows],
            [float(row["human_mean"]) for row in rows],
        )
        output.append(
            {
                "target_char": character,
                "n_pairs": len(rows),
                "human_mean": float(
                    np.mean([float(row["human_mean"]) for row in rows])
                ),
                "human_std_ddof1": (
                    float(
                        np.std(
                            [float(row["human_mean"]) for row in rows],
                            ddof=1,
                        )
                    )
                    if len(rows) > 1
                    else 0.0
                ),
                "current_score_mean": float(
                    np.mean([float(row["system_score"]) for row in rows])
                ),
                "coverage_aware_score_mean": float(
                    np.mean([float(row["coverage_aware_score"]) for row in rows])
                ),
                "spearman_current_vs_human": current_rho,
                "spearman_coverage_vs_human": coverage_rho,
            }
        )
    return output


def _pair_disagreement_cases(
    canonical_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ordered = sorted(
        canonical_rows,
        key=lambda row: (
            -int(row["human_rating_range"]),
            -float(row["human_std_ddof1"]),
            str(row["source_pair_id"]),
        ),
    )
    return [
        {
            "disagreement_rank": index,
            **dict(row),
        }
        for index, row in enumerate(ordered, start=1)
    ]


def _rater_metadata_audit(
    raw_return_rows: Sequence[Mapping[str, Any]],
    evaluator_ids: Sequence[str],
) -> list[dict[str, Any]]:
    by_evaluator: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in raw_return_rows:
        by_evaluator[str(row.get("evaluator_id", "")).strip()].append(row)
    output: list[dict[str, Any]] = []
    for evaluator in evaluator_ids:
        rows = by_evaluator.get(evaluator, [])
        metadata_fields = (
            "expertise_category",
            "years_calligraphy_experience",
            "teaching_experience_years",
            "study_version",
            "consent_confirmed",
        )
        values = {
            field: sorted({str(row.get(field, "")).strip() for row in rows})
            for field in metadata_fields
        }
        inconsistent = [field for field, options in values.items() if len(options) != 1]
        if not rows:
            output.append(
                {
                    "evaluator_id": evaluator,
                    "metadata_status": "NOT_PROVIDED",
                    "recommended_claim": "blinded human rater",
                }
            )
            continue
        if inconsistent:
            raise ValueError(
                f"inconsistent rater metadata for {evaluator}: {inconsistent}"
            )
        category = values["expertise_category"][0]
        years = values["years_calligraphy_experience"][0]
        teaching = values["teaching_experience_years"][0]
        output.append(
            {
                "evaluator_id": evaluator,
                "metadata_status": "VERIFIED_FROM_RAW_RETURN",
                "expertise_category": category,
                "years_calligraphy_experience": years,
                "teaching_experience_years": teaching,
                "study_version": values["study_version"][0],
                "consent_confirmed": values["consent_confirmed"][0],
                "recommended_claim": "blinded human rater",
                "unqualified_expert_claim_warning": (
                    category != "书法教师"
                    or _finite_float(years or 0, field="years_calligraphy_experience") < 1
                ),
            }
        )
    return output


def build_human_validation_statistics(
    pair_rows: Sequence[Mapping[str, Any]],
    rating_rows: Sequence[Mapping[str, Any]],
    *,
    raw_return_rows: Sequence[Mapping[str, Any]] = (),
    bootstrap_iterations: int = 10_000,
    seed: int = 20260812,
) -> dict[str, Any]:
    """Build complete paper statistics without changing frozen scores or pairs."""

    blinded_ids = [str(row.get("blinded_pair_id", "")) for row in pair_rows]
    if len(blinded_ids) != len(set(blinded_ids)):
        raise ValueError("blinded_pair_id values must be unique")
    canonical_pairs, presentations_by_source = _canonical_presentations(pair_rows)
    rating_lookup, evaluator_ids = _rating_lookup(pair_rows, rating_rows)
    canonical_rows = _canonical_rating_rows(
        canonical_pairs,
        rating_lookup,
        evaluator_ids,
    )
    human_means = [float(row["human_mean"]) for row in canonical_rows]
    current_rho, current_p = _spearman_with_p(
        [float(row["system_score"]) for row in canonical_rows],
        human_means,
    )
    coverage_rho, coverage_p = _spearman_with_p(
        [float(row["coverage_aware_score"]) for row in canonical_rows],
        human_means,
    )
    bootstrap = _character_cluster_bootstrap_correlations(
        canonical_rows,
        iterations=bootstrap_iterations,
        seed=seed,
    )
    matrix = np.asarray(
        [
            [float(row[f"rating_{evaluator}"]) for evaluator in evaluator_ids]
            for row in canonical_rows
        ],
        dtype=np.float64,
    )
    icc = icc_2_1_and_2_k(matrix)
    evaluator_summary = _per_evaluator_summary(canonical_rows, evaluator_ids)
    repeat_consistency = _repeat_consistency(
        presentations_by_source,
        rating_lookup,
        evaluator_ids,
    )
    per_character = _per_character_summary(canonical_rows)
    disagreement = _pair_disagreement_cases(canonical_rows)
    metadata_audit = _rater_metadata_audit(raw_return_rows, evaluator_ids)
    repeated_sources = sum(
        len(presentations) == 2 for presentations in presentations_by_source.values()
    )

    report = {
        "schema_version": 1,
        "study_version": "expert_structural_validation_v1",
        "analysis_name": "human_structural_validation_paper_statistics_v1",
        "claim_scope": "structural similarity only, not aesthetic grading",
        "terminology": {
            "recommended": "blinded human raters / human structural validation",
            "avoid_without_additional_qualification_evidence": (
                "three calligraphy experts / expert aesthetic grading"
            ),
        },
        "data_integrity": {
            "presentation_count": len(pair_rows),
            "canonical_pair_count": len(canonical_rows),
            "hidden_repeat_source_pair_count": repeated_sources,
            "evaluator_count": len(evaluator_ids),
            "evaluator_ids": evaluator_ids,
            "rating_row_count": len(rating_rows),
            "complete_matrix": True,
            "canonical_only_for_correlation_and_icc": True,
            "hidden_repeats_only_for_intra_rater_consistency": True,
        },
        "system_vs_human_mean": {
            "current_score": {
                "spearman_rho": current_rho,
                "p_two_sided": current_p,
                "cluster_bootstrap_ci95": bootstrap["current_ci95"],
            },
            "coverage_aware_score": {
                "spearman_rho": coverage_rho,
                "p_two_sided": coverage_p,
                "cluster_bootstrap_ci95": bootstrap["coverage_aware_ci95"],
            },
            "coverage_minus_current_spearman": (
                float(coverage_rho - current_rho)
                if current_rho is not None and coverage_rho is not None
                else None
            ),
            "coverage_minus_current_cluster_bootstrap_ci95": bootstrap[
                "coverage_minus_current_ci95"
            ],
            "coverage_minus_current_two_sided_bootstrap_p": bootstrap[
                "coverage_minus_current_two_sided_bootstrap_p"
            ],
            "bootstrap": bootstrap,
        },
        "canonical_inter_rater_reliability": icc,
        "per_evaluator_summary": evaluator_summary,
        "hidden_repeat_consistency": repeat_consistency,
        "rater_metadata_audit": metadata_audit,
        "human_rating_distribution": {
            "pair_mean_mean": float(np.mean(human_means)),
            "pair_mean_median": float(np.median(human_means)),
            "pair_mean_std_ddof1": float(np.std(human_means, ddof=1)),
            "pair_rating_range_ge_2_count": sum(
                int(row["human_rating_range"]) >= 2 for row in canonical_rows
            ),
            "pair_rating_range_ge_3_count": sum(
                int(row["human_rating_range"]) >= 3 for row in canonical_rows
            ),
        },
        "bootstrap_iterations": bootstrap_iterations,
        "seed": seed,
    }
    return {
        "report": report,
        "canonical_pair_ratings": canonical_rows,
        "per_evaluator_summary": evaluator_summary,
        "per_character_summary": per_character,
        "repeat_consistency": repeat_consistency,
        "pair_disagreement_cases": disagreement,
        "rater_metadata_audit": metadata_audit,
    }


def _format_float(value: Any, digits: int = 3) -> str:
    if value is None:
        return "--"
    return f"{float(value):.{digits}f}"


def _format_p(value: Any) -> str:
    if value is None:
        return "--"
    numeric = float(value)
    if numeric < 0.0001:
        return r"\(<0.0001\)"
    return f"{numeric:.4f}"


def _latex_escape(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    return text


def _human_validation_table(report: Mapping[str, Any]) -> str:
    comparison = report["system_vs_human_mean"]
    current = comparison["current_score"]
    coverage = comparison["coverage_aware_score"]
    return rf"""\begin{{table}}[t]
\caption{{Association between the structural scores and the mean rating of
three blinded human raters across 150 canonical pairs. Confidence intervals
use 10,000 bootstrap resamples clustered by character.}}
\label{{tab:human-validation}}
\centering
\small
\begin{{tabular}}{{lrrr}}
\toprule
Score & Spearman $\rho$ & 95\% CI & $p$ \\
\midrule
Production & {_format_float(current["spearman_rho"])} &
[{_format_float(current["cluster_bootstrap_ci95"][0])},
 {_format_float(current["cluster_bootstrap_ci95"][1])}] &
{_format_p(current["p_two_sided"])} \\
Coverage-aware audit & {_format_float(coverage["spearman_rho"])} &
[{_format_float(coverage["cluster_bootstrap_ci95"][0])},
 {_format_float(coverage["cluster_bootstrap_ci95"][1])}] &
{_format_p(coverage["p_two_sided"])} \\
\bottomrule
\end{{tabular}}
\end{{table}}
"""


def _rater_reliability_table(
    report: Mapping[str, Any],
) -> str:
    icc = report["canonical_inter_rater_reliability"]
    rows = []
    for row in report["hidden_repeat_consistency"]:
        rows.append(
            "{} & {} & {} & {} & {} \\\\".format(
                _latex_escape(row["evaluator_id"]),
                _format_float(row["exact_agreement_rate"]),
                _format_float(row["within_one_agreement_rate"]),
                _format_float(row["mean_absolute_difference"]),
                _format_float(row["quadratic_weighted_kappa"]),
            )
        )
    return rf"""\begin{{table}}[t]
\caption{{Human-rater reliability. ICC uses only the 150 canonical
presentations. Repeat statistics use the 15 hidden repeats per rater.}}
\label{{tab:rater-reliability}}
\centering
\small
\begin{{tabular}}{{lrrrr}}
\toprule
Rater & Exact & Within $\pm 1$ & MAD & QWK \\
\midrule
{chr(10).join(rows)}
\bottomrule
\end{{tabular}}
\vspace{{2pt}}
\begin{{minipage}}{{0.96\columnwidth}}\footnotesize
Canonical ICC(2,1)={_format_float(icc["icc_2_1"])} and
ICC(2,$k$)={_format_float(icc["icc_2_k"])} for
{int(icc["n_targets"])} pairs and {int(icc["n_raters"])} raters.
\end{{minipage}}
\end{{table}}
"""


def _markdown_report(report: Mapping[str, Any]) -> str:
    comparison = report["system_vs_human_mean"]
    current = comparison["current_score"]
    coverage = comparison["coverage_aware_score"]
    icc = report["canonical_inter_rater_reliability"]
    lines = [
        "# Human Structural Validation Report",
        "",
        "## Scope",
        "",
        (
            "This study validates reference-conditioned structural similarity only. "
            "It does not validate aesthetic quality or expert calligraphy grading."
        ),
        "",
        (
            "Use the terms **blinded human raters** and **human structural validation**. "
            "Do not describe all three raters as calligraphy experts without separate "
            "qualification evidence."
        ),
        "",
        "## Integrity",
        "",
        f"- Canonical pairs: {report['data_integrity']['canonical_pair_count']}",
        (
            f"- Hidden repeat pairs per rater: "
            f"{report['data_integrity']['hidden_repeat_source_pair_count']}"
        ),
        f"- Raters: {report['data_integrity']['evaluator_count']}",
        "- Correlation and ICC use canonical non-repeat presentations only.",
        "- Hidden repeats are used only for intra-rater consistency.",
        "",
        "## System association with mean human rating",
        "",
        "| Score | Spearman rho | Character-cluster bootstrap 95% CI | p |",
        "|---|---:|---:|---:|",
        (
            f"| Production | {_format_float(current['spearman_rho'])} | "
            f"[{_format_float(current['cluster_bootstrap_ci95'][0])}, "
            f"{_format_float(current['cluster_bootstrap_ci95'][1])}] | "
            f"{_format_float(current['p_two_sided'], 4)} |"
        ),
        (
            f"| Coverage-aware audit | {_format_float(coverage['spearman_rho'])} | "
            f"[{_format_float(coverage['cluster_bootstrap_ci95'][0])}, "
            f"{_format_float(coverage['cluster_bootstrap_ci95'][1])}] | "
            f"{_format_float(coverage['p_two_sided'], 4)} |"
        ),
        "",
        (
            "Coverage-aware minus production rho: "
            f"{_format_float(comparison['coverage_minus_current_spearman'])}, "
            "paired character-cluster bootstrap 95% CI "
            f"[{_format_float(comparison['coverage_minus_current_cluster_bootstrap_ci95'][0])}, "
            f"{_format_float(comparison['coverage_minus_current_cluster_bootstrap_ci95'][1])}]."
        ),
        "",
        "## Inter-rater reliability",
        "",
        f"- Canonical ICC(2,1): {_format_float(icc['icc_2_1'])}",
        f"- Canonical ICC(2,k): {_format_float(icc['icc_2_k'])}",
        "",
        "| Rater | Exact repeat agreement | Within ±1 | MAD | QWK |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in report["hidden_repeat_consistency"]:
        lines.append(
            f"| {row['evaluator_id']} | "
            f"{_format_float(row['exact_agreement_rate'])} | "
            f"{_format_float(row['within_one_agreement_rate'])} | "
            f"{_format_float(row['mean_absolute_difference'])} | "
            f"{_format_float(row['quadratic_weighted_kappa'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation guardrails",
            "",
            (
                "- A positive correlation supports structural-score validity but does "
                "not turn the score into a calibrated aesthetic grade."
            ),
            (
                "- Moderate or weak inter-rater reliability must be reported as a "
                "property of the task and rater pool; no rater is removed after seeing "
                "results."
            ),
            (
                "- The coverage-aware score remains an audit quantity. The production "
                "formula is not changed post hoc."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _write_figures(
    output: Path,
    canonical_rows: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    human = [float(row["human_mean"]) for row in canonical_rows]
    figure, axis = plt.subplots(figsize=(5.5, 4.2))
    axis.scatter(
        [float(row["system_score"]) for row in canonical_rows],
        human,
        s=22,
        alpha=0.72,
        edgecolors="none",
    )
    axis.set_xlabel("Production structure score")
    axis.set_ylabel("Mean blinded human rating (1--5)")
    axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(output / "system_vs_human_current.png", dpi=240)
    figure.savefig(output / "system_vs_human_current.pdf")
    plt.close(figure)

    comparison = report["system_vs_human_mean"]
    labels = ["Production", "Coverage-aware"]
    values = [
        comparison["current_score"]["spearman_rho"],
        comparison["coverage_aware_score"]["spearman_rho"],
    ]
    intervals = [
        comparison["current_score"]["cluster_bootstrap_ci95"],
        comparison["coverage_aware_score"]["cluster_bootstrap_ci95"],
    ]
    lower = [value - interval[0] for value, interval in zip(values, intervals, strict=True)]
    upper = [interval[1] - value for value, interval in zip(values, intervals, strict=True)]
    figure, axis = plt.subplots(figsize=(5.2, 3.8))
    axis.errorbar(
        labels,
        values,
        yerr=np.asarray([lower, upper]),
        fmt="o",
        capsize=6,
        markersize=7,
    )
    axis.axhline(0, color="black", linewidth=0.8, alpha=0.5)
    axis.set_ylabel("Spearman correlation with mean human rating")
    axis.grid(axis="y", alpha=0.2)
    figure.tight_layout()
    figure.savefig(output / "current_vs_coverage_human_correlation.png", dpi=240)
    figure.savefig(output / "current_vs_coverage_human_correlation.pdf")
    plt.close(figure)


def write_human_validation_statistics(
    output_dir: str | Path,
    result: Mapping[str, Any],
) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report = result["report"]
    (output / "human_validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "HUMAN_VALIDATION_REPORT.md").write_text(
        _markdown_report(report),
        encoding="utf-8",
    )
    _write_csv(output / "canonical_pair_ratings.csv", result["canonical_pair_ratings"])
    _write_csv(output / "per_evaluator_summary.csv", result["per_evaluator_summary"])
    _write_csv(output / "per_character_summary.csv", result["per_character_summary"])
    _write_csv(output / "repeat_consistency.csv", result["repeat_consistency"])
    _write_csv(output / "pair_disagreement_cases.csv", result["pair_disagreement_cases"])
    _write_csv(output / "rater_metadata_audit.csv", result["rater_metadata_audit"])
    (output / "table_human_validation.tex").write_text(
        _human_validation_table(report),
        encoding="utf-8",
    )
    (output / "table_rater_reliability.tex").write_text(
        _rater_reliability_table(report),
        encoding="utf-8",
    )
    _write_figures(output, result["canonical_pair_ratings"], report)
