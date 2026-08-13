"""Blinded expert-study sampling and rating analysis utilities."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from onestroke_model.perturbation_benchmark import spearman_rho

EXPERT_PAIR_FIELDS = (
    "blinded_pair_id",
    "source_pair_id",
    "duplicate_of_source_pair_id",
    "is_repeat",
    "target_char",
    "style_id",
    "candidate_asset",
    "reference_asset",
    "system_score",
    "score_bin",
    "selection_seed",
)
EXPERT_FORM_FIELDS = (
    "blinded_pair_id",
    "target_char",
    "candidate_asset",
    "reference_asset",
    "structural_similarity_rating_1_to_5",
    "optional_comment",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        discovered: list[str] = []
        for row in rows:
            for field in row:
                if field not in discovered:
                    discovered.append(field)
        fields = discovered
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def _stable_hash(seed: int, *values: str) -> str:
    return hashlib.sha256(":".join([str(seed), *values]).encode("utf-8")).hexdigest()


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _score_bins(rows: Sequence[Mapping[str, Any]], num_bins: int) -> dict[str, int]:
    ordered = sorted(
        rows,
        key=lambda row: (
            float(row["system_score"]),
            str(row["pair_id"]),
        ),
    )
    return {
        str(row["pair_id"]): min(num_bins - 1, index * num_bins // len(ordered))
        for index, row in enumerate(ordered)
    }


def select_expert_rating_pairs(
    candidates: Sequence[Mapping[str, Any]],
    *,
    target_pairs: int = 180,
    duplicate_fraction: float = 0.10,
    seed: int = 20260811,
    score_bins: int = 10,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not candidates:
        raise ValueError("candidate pair table is empty")
    if target_pairs <= 0:
        raise ValueError("target_pairs must be positive")
    if not 0 <= duplicate_fraction < 0.5:
        raise ValueError("duplicate_fraction must be in [0, 0.5)")
    required = ("pair_id", "target_char", "system_score")
    normalized: list[dict[str, Any]] = []
    for row in candidates:
        missing = [field for field in required if str(row.get(field, "")).strip() == ""]
        if missing:
            raise ValueError(f"candidate row is missing {missing}: {row!r}")
        score = float(row["system_score"])
        if not math.isfinite(score):
            raise ValueError(f"non-finite system_score: {row!r}")
        normalized.append({**dict(row), "system_score": score})
    ids = [str(row["pair_id"]) for row in normalized]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate pair_id values must be unique")

    bins = _score_bins(normalized, score_bins)
    grouped: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        grouped[bins[str(row["pair_id"])]].append(row)
    for bin_rows in grouped.values():
        bin_rows.sort(
            key=lambda row: _stable_hash(
                seed,
                str(row.get("target_char", "")),
                str(row.get("style_id", row.get("reference_style_id", ""))),
                str(row["pair_id"]),
            )
        )

    unique_target = min(target_pairs, len(normalized))
    selected: list[dict[str, Any]] = []
    offsets = {bin_id: 0 for bin_id in range(score_bins)}
    while len(selected) < unique_target:
        made_progress = False
        for bin_id in range(score_bins):
            rows = grouped.get(bin_id, [])
            offset = offsets[bin_id]
            if offset >= len(rows):
                continue
            selected.append(rows[offset])
            offsets[bin_id] += 1
            made_progress = True
            if len(selected) >= unique_target:
                break
        if not made_progress:
            break

    duplicate_count = min(
        len(selected),
        round(len(selected) * duplicate_fraction),
    )
    duplicate_sources = sorted(
        selected,
        key=lambda row: _stable_hash(seed, "duplicate", str(row["pair_id"])),
    )[:duplicate_count]
    presentation = [({**row}, None) for row in selected] + [
        ({**row}, str(row["pair_id"])) for row in duplicate_sources
    ]
    presentation.sort(
        key=lambda item: _stable_hash(
            seed,
            "presentation",
            str(item[0]["pair_id"]),
            str(item[1] or "original"),
        )
    )

    internal_rows: list[dict[str, Any]] = []
    form_rows: list[dict[str, Any]] = []
    for index, (row, duplicate_of) in enumerate(presentation, start=1):
        blinded_id = f"EXP-{index:04d}-{_stable_hash(seed, str(index), str(row['pair_id']))[:8]}"
        internal = {
            "blinded_pair_id": blinded_id,
            "source_pair_id": row["pair_id"],
            "duplicate_of_source_pair_id": duplicate_of or "",
            "is_repeat": bool(duplicate_of),
            "target_char": row["target_char"],
            "style_id": row.get("style_id", row.get("reference_style_id", "")),
            "candidate_asset": row.get("candidate_asset", ""),
            "reference_asset": row.get("reference_asset", ""),
            "system_score": row["system_score"],
            "score_bin": bins[str(row["pair_id"])],
            "selection_seed": seed,
        }
        internal_rows.append(internal)
        form_rows.append(
            {
                "blinded_pair_id": blinded_id,
                "target_char": row["target_char"],
                "candidate_asset": row.get("candidate_asset", ""),
                "reference_asset": row.get("reference_asset", ""),
                "structural_similarity_rating_1_to_5": "",
                "optional_comment": "",
            }
        )
    metadata = {
        "schema_version": 1,
        "study_type": "blinded_structural_similarity",
        "seed": seed,
        "candidate_count": len(normalized),
        "selected_unique_pairs": len(selected),
        "repeat_presentations": duplicate_count,
        "total_presentations": len(internal_rows),
        "duplicate_fraction_actual": duplicate_count / max(1, len(selected)),
        "score_bins": score_bins,
        "selection_uses_system_score_only_for_range_stratification": True,
        "evaluator_form_exposes_system_score": False,
        "rating_scale": {
            "1": "very dissimilar",
            "2": "dissimilar",
            "3": "moderate",
            "4": "similar",
            "5": "very similar",
        },
        "claim_scope": "structural similarity only, not aesthetic quality",
    }
    return internal_rows, form_rows, metadata


def write_expert_study_package(
    output_dir: str | Path,
    *,
    internal_rows: Sequence[Mapping[str, Any]],
    form_rows: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "expert_rating_pairs.csv", internal_rows, EXPERT_PAIR_FIELDS)
    _write_csv(output / "expert_rating_form.csv", form_rows, EXPERT_FORM_FIELDS)
    (output / "expert_study_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "expert_rating_instructions.md").write_text(
        """# Expert Structural Similarity Rating Instructions

Evaluate only the structural agreement between the candidate and reference character.
Do not evaluate artistic value, beauty, historical authenticity, or overall calligraphy quality.

Use the following 1-5 scale:

1. Very dissimilar
2. Dissimilar
3. Moderate
4. Similar
5. Very similar

The OneStroke system score is hidden. Some pairs may be repeated under different blinded IDs
to estimate intra-rater consistency. Do not try to identify repeats.
""",
        encoding="utf-8",
    )


def write_pending_expert_study_package(
    output_dir: str | Path,
    *,
    target_pairs: int = 180,
    target_evaluators: int = 3,
    duplicate_fraction: float = 0.10,
    seed: int = 20260811,
) -> dict[str, Any]:
    metadata = {
        "schema_version": 1,
        "status": "PENDING_PAIR_SCORES_AND_HUMAN_RATINGS",
        "target_unique_pairs": target_pairs,
        "target_evaluators": target_evaluators,
        "duplicate_fraction": duplicate_fraction,
        "seed": seed,
        "claim_scope": "structural similarity only, not aesthetic quality",
        "next_gate": (
            "Generate real candidate-reference pairs with system scores, then run "
            "build_expert_rating_package.py before collecting ratings."
        ),
    }
    write_expert_study_package(
        output_dir,
        internal_rows=[],
        form_rows=[],
        metadata=metadata,
    )
    return metadata


def _bootstrap_spearman_by_character(
    rows: Sequence[Mapping[str, Any]],
    *,
    iterations: int,
    seed: int,
) -> tuple[float | None, float | None]:
    by_char: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_char[str(row["target_char"])].append(row)
    characters = sorted(by_char)
    if len(characters) < 2 or iterations <= 0:
        return None, None
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(iterations):
        sampled = rng.choice(characters, size=len(characters), replace=True)
        bootstrap_rows = [row for char in sampled for row in by_char[str(char)]]
        rho = spearman_rho(
            [float(row["system_score"]) for row in bootstrap_rows],
            [float(row["expert_mean"]) for row in bootstrap_rows],
        )
        if rho is not None:
            values.append(float(rho))
    if not values:
        return None, None
    return float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))


def icc_2_1_and_2_k(matrix: np.ndarray) -> dict[str, float | int | None]:
    """Two-way random-effects, absolute-agreement ICC(2,1) and ICC(2,k)."""
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError("ratings matrix must be 2D")
    n, k = values.shape
    if n < 2 or k < 2 or not np.all(np.isfinite(values)):
        return {"n_targets": n, "n_raters": k, "icc_2_1": None, "icc_2_k": None}
    grand = float(values.mean())
    row_means = values.mean(axis=1)
    column_means = values.mean(axis=0)
    ms_rows = k * float(np.square(row_means - grand).sum()) / (n - 1)
    ms_columns = n * float(np.square(column_means - grand).sum()) / (k - 1)
    residual = values - row_means[:, None] - column_means[None, :] + grand
    ms_error = float(np.square(residual).sum()) / ((n - 1) * (k - 1))
    denominator_single = (
        ms_rows + (k - 1) * ms_error + k * (ms_columns - ms_error) / n
    )
    denominator_average = ms_rows + (ms_columns - ms_error) / n
    return {
        "n_targets": n,
        "n_raters": k,
        "ms_rows": ms_rows,
        "ms_columns": ms_columns,
        "ms_error": ms_error,
        "icc_2_1": (
            float((ms_rows - ms_error) / denominator_single)
            if abs(denominator_single) > 1e-12
            else None
        ),
        "icc_2_k": (
            float((ms_rows - ms_error) / denominator_average)
            if abs(denominator_average) > 1e-12
            else None
        ),
    }


def analyze_expert_ratings(
    pair_rows: Sequence[Mapping[str, Any]],
    rating_rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_iterations: int = 2000,
    seed: int = 20260811,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pair_by_blinded = {str(row["blinded_pair_id"]): dict(row) for row in pair_rows}
    if len(pair_by_blinded) != len(pair_rows):
        raise ValueError("blinded_pair_id values must be unique")
    ratings: defaultdict[str, dict[str, float]] = defaultdict(dict)
    for row in rating_rows:
        blinded_id = str(row.get("blinded_pair_id", ""))
        evaluator_id = str(row.get("evaluator_id", "")).strip()
        if blinded_id not in pair_by_blinded:
            raise ValueError(f"unknown blinded_pair_id in ratings: {blinded_id!r}")
        if not evaluator_id:
            raise ValueError("evaluator_id is required")
        rating = float(row.get("rating", row.get("structural_similarity_rating_1_to_5", "")))
        if rating < 1 or rating > 5:
            raise ValueError(f"rating must be in [1,5], got {rating}")
        if evaluator_id in ratings[blinded_id]:
            raise ValueError(f"duplicate evaluator rating for {blinded_id}: {evaluator_id}")
        ratings[blinded_id][evaluator_id] = rating

    aggregate_rows: list[dict[str, Any]] = []
    for blinded_id, pair in pair_by_blinded.items():
        values = list(ratings.get(blinded_id, {}).values())
        aggregate_rows.append(
            {
                **pair,
                "rating_count": len(values),
                "expert_mean": float(np.mean(values)) if values else None,
                "expert_median": float(np.median(values)) if values else None,
            }
        )

    # System correlation uses one canonical presentation per source pair so the
    # deliberate repeats do not receive extra statistical weight.
    canonical: dict[str, dict[str, Any]] = {}
    for row in aggregate_rows:
        source_id = str(row["source_pair_id"])
        if row["expert_mean"] is None:
            continue
        current = canonical.get(source_id)
        if current is None or (
            _boolish(current.get("is_repeat"))
            and not _boolish(row.get("is_repeat"))
        ):
            canonical[source_id] = row
    canonical_rows = list(canonical.values())
    rho = spearman_rho(
        [float(row["system_score"]) for row in canonical_rows],
        [float(row["expert_mean"]) for row in canonical_rows],
    )
    ci_low, ci_high = _bootstrap_spearman_by_character(
        canonical_rows,
        iterations=bootstrap_iterations,
        seed=seed,
    )

    evaluator_ids = sorted(
        {evaluator for values in ratings.values() for evaluator in values}
    )
    complete_rows = [
        row
        for row in aggregate_rows
        if all(evaluator in ratings[str(row["blinded_pair_id"])] for evaluator in evaluator_ids)
    ]
    matrix = np.asarray(
        [
            [ratings[str(row["blinded_pair_id"])][evaluator] for evaluator in evaluator_ids]
            for row in complete_rows
        ],
        dtype=np.float64,
    )
    if not complete_rows or len(evaluator_ids) < 2:
        matrix = np.empty((len(complete_rows), len(evaluator_ids)), dtype=np.float64)
    icc = icc_2_1_and_2_k(matrix)

    repeats_by_source: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in aggregate_rows:
        repeats_by_source[str(row["source_pair_id"])].append(row)
    repeat_differences: list[float] = []
    repeat_exact = 0
    repeat_total = 0
    for presentations in repeats_by_source.values():
        if len(presentations) < 2:
            continue
        first, second = presentations[:2]
        for evaluator in evaluator_ids:
            first_rating = ratings[str(first["blinded_pair_id"])].get(evaluator)
            second_rating = ratings[str(second["blinded_pair_id"])].get(evaluator)
            if first_rating is None or second_rating is None:
                continue
            difference = abs(first_rating - second_rating)
            repeat_differences.append(float(difference))
            repeat_exact += int(difference == 0)
            repeat_total += 1

    report = {
        "schema_version": 1,
        "rated_presentations": sum(row["rating_count"] > 0 for row in aggregate_rows),
        "canonical_rated_pairs": len(canonical_rows),
        "evaluator_count": len(evaluator_ids),
        "evaluator_ids": evaluator_ids,
        "spearman_system_vs_expert_mean": rho,
        "cluster_bootstrap_by_character_ci95": [ci_low, ci_high],
        "bootstrap_iterations": bootstrap_iterations,
        "icc": icc,
        "complete_presentations_for_icc": len(complete_rows),
        "incomplete_presentations_excluded_from_icc": len(aggregate_rows) - len(complete_rows),
        "intra_rater_repeat_consistency": {
            "paired_repeat_ratings": repeat_total,
            "mean_absolute_difference": (
                float(np.mean(repeat_differences)) if repeat_differences else None
            ),
            "exact_agreement_rate": (
                repeat_exact / repeat_total if repeat_total else None
            ),
        },
        "claim_scope": "structural similarity validation, not aesthetic grading",
    }
    return aggregate_rows, report


def write_expert_analysis_outputs(
    output_dir: str | Path,
    aggregate_rows: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "expert_rating_aggregate.csv", aggregate_rows)
    (output / "expert_rating_analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    canonical: dict[str, Mapping[str, Any]] = {}
    for row in aggregate_rows:
        if row.get("expert_mean") is None:
            continue
        source_id = str(row["source_pair_id"])
        if source_id not in canonical or (
            _boolish(canonical[source_id].get("is_repeat"))
            and not _boolish(row.get("is_repeat"))
        ):
            canonical[source_id] = row
    values = list(canonical.values())
    if not values:
        return
    figure, axis = plt.subplots(figsize=(5.5, 4.2))
    axis.scatter(
        [float(row["system_score"]) for row in values],
        [float(row["expert_mean"]) for row in values],
        s=20,
        alpha=0.75,
    )
    axis.set_xlabel("OneStroke structural agreement score")
    axis.set_ylabel("Expert structural similarity mean (1-5)")
    axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(output / "system_vs_expert_scatter.png", dpi=220)
    figure.savefig(output / "system_vs_expert_scatter.pdf")
    plt.close(figure)
