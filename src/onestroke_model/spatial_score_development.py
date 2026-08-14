"""Development-only analysis for the frozen spatial structure score.

The existing 150 rated pairs are treated as a development study.  Weight
search and grouped cross-validation are reported transparently, while the
rounded score specification is frozen before a separate confirmatory rating
set is collected.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from onestroke_model.controlled_perturbations import PreparedReferenceScorer
from onestroke_model.perturbation_benchmark import spearman_rho
from onestroke_model.spatial_structure_score import (
    SPATIAL_SCORE_VERSION,
    SPATIAL_SCORE_WEIGHTS,
    compute_spatial_structure_components,
    spatial_structure_score,
)

FEATURE_ORDER = (
    "grid_js_similarity",
    "polar_js_similarity",
    "projection_js_similarity",
)
WEIGHT_GRID_DENOMINATOR = 40
GROUP_FOLD_COUNT = 5
GROUP_FOLD_SALT = "spatial-score-development-group-cv-v1"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    fieldnames: Sequence[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(fieldnames or ())
    if not fields:
        for row in rows:
            for field in row:
                if field not in fields:
                    fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["status"])
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_fold(char_id: str) -> int:
    digest = hashlib.sha256(f"{GROUP_FOLD_SALT}:{char_id}".encode()).hexdigest()
    return int(digest[:8], 16) % GROUP_FOLD_COUNT


def _load_masks(data_root: Path, relative_image_path: str) -> np.ndarray:
    relative = Path(relative_image_path.replace("\\", "/"))
    mask_path = (data_root / relative).with_suffix(".npy")
    value = np.load(mask_path, allow_pickle=False)
    masks = np.asarray(value) > 0
    if masks.ndim != 3 or masks.shape[-1] != 6:
        raise ValueError(f"invalid six-channel mask stack: {mask_path} {masks.shape}")
    return masks


def _feature_matrix(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    return np.asarray(
        [[float(row[name]) for name in FEATURE_ORDER] for row in rows],
        dtype=np.float64,
    )


def _score_with_weights(matrix: np.ndarray, weights: Sequence[float]) -> np.ndarray:
    values = np.asarray(weights, dtype=np.float64)
    if values.shape != (len(FEATURE_ORDER),):
        raise ValueError(f"expected {len(FEATURE_ORDER)} weights, got {values.shape}")
    if np.any(values < 0) or not np.isclose(values.sum(), 1.0):
        raise ValueError("weights must be non-negative and sum to one")
    return 100.0 * (matrix @ values)


def _simplex_weights() -> list[np.ndarray]:
    candidates: list[np.ndarray] = []
    denominator = WEIGHT_GRID_DENOMINATOR
    for grid_weight in range(denominator + 1):
        for polar_weight in range(denominator + 1 - grid_weight):
            projection_weight = denominator - grid_weight - polar_weight
            candidates.append(
                np.asarray(
                    [grid_weight, polar_weight, projection_weight],
                    dtype=np.float64,
                )
                / denominator
            )
    return candidates


def _select_weights(
    matrix: np.ndarray,
    targets: np.ndarray,
    indices: np.ndarray,
) -> tuple[np.ndarray, float]:
    best_weights: np.ndarray | None = None
    best_key: tuple[float, float, float, float, float] | None = None
    frozen = np.asarray(
        [
            SPATIAL_SCORE_WEIGHTS["grid_js_similarity"],
            SPATIAL_SCORE_WEIGHTS["polar_js_similarity"],
            SPATIAL_SCORE_WEIGHTS["projection_js_similarity"],
        ],
        dtype=np.float64,
    )
    for weights in _simplex_weights():
        rho = spearman_rho(
            _score_with_weights(matrix[indices], weights).tolist(),
            targets[indices].tolist(),
        )
        if rho is None:
            continue
        # Prefer higher rho, then a less data-adaptive solution closer to the
        # rounded frozen weights. Remaining fields make ties deterministic.
        key = (
            float(rho),
            -float(np.abs(weights - frozen).sum()),
            float(weights[1]),
            float(weights[0]),
            float(weights[2]),
        )
        if best_key is None or key > best_key:
            best_key = key
            best_weights = weights
    if best_weights is None or best_key is None:
        raise ValueError("weight search produced no valid Spearman estimate")
    return best_weights, float(best_key[0])


def _cluster_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    *,
    score_fields: Sequence[str],
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    by_character: defaultdict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_character[str(row["char_id"])].append(index)
    characters = sorted(by_character, key=int)
    rng = np.random.default_rng(seed)
    metric_samples: dict[str, list[float]] = {field: [] for field in score_fields}
    difference_samples: dict[str, list[float]] = {}
    for first_index, first in enumerate(score_fields):
        for second in score_fields[:first_index]:
            difference_samples[f"{first}_minus_{second}"] = []

    for _ in range(iterations):
        sampled_characters = rng.choice(characters, size=len(characters), replace=True)
        sampled_indices = [
            index
            for character in sampled_characters
            for index in by_character[str(character)]
        ]
        human = [float(rows[index]["human_mean"]) for index in sampled_indices]
        estimates: dict[str, float] = {}
        valid = True
        for field in score_fields:
            rho = spearman_rho(
                [float(rows[index][field]) for index in sampled_indices],
                human,
            )
            if rho is None:
                valid = False
                break
            estimates[field] = float(rho)
        if not valid:
            continue
        for field, value in estimates.items():
            metric_samples[field].append(value)
        for name, samples in difference_samples.items():
            first, second = name.split("_minus_", maxsplit=1)
            samples.append(estimates[first] - estimates[second])

    def interval(values: Sequence[float]) -> list[float | None]:
        if not values:
            return [None, None]
        return [
            float(np.quantile(values, 0.025)),
            float(np.quantile(values, 0.975)),
        ]

    return {
        "iterations_requested": iterations,
        "valid_iterations": min(
            [len(values) for values in metric_samples.values()] or [0]
        ),
        "cluster_unit": "char_id",
        "rho_ci95": {
            field: interval(values) for field, values in metric_samples.items()
        },
        "paired_difference_ci95": {
            field: interval(values) for field, values in difference_samples.items()
        },
    }


def _spearman_with_p(first: Sequence[float], second: Sequence[float]) -> dict[str, Any]:
    rho = spearman_rho(first, second)
    try:
        from scipy.stats import spearmanr
    except ImportError:
        p_value = None
    else:
        result = spearmanr(first, second)
        p_value = float(result.pvalue)
    return {"rho": rho, "p_two_sided": p_value}


def build_development_features(
    *,
    frozen_pairs: Sequence[Mapping[str, str]],
    canonical_ratings: Sequence[Mapping[str, str]],
    data_root: Path,
) -> list[dict[str, Any]]:
    frozen_by_id = {str(row["pair_id"]): row for row in frozen_pairs}
    rows: list[dict[str, Any]] = []
    scorer_cache: dict[str, PreparedReferenceScorer] = {}
    for index, rating in enumerate(canonical_ratings, start=1):
        source_pair_id = str(rating["source_pair_id"])
        pair = frozen_by_id.get(source_pair_id)
        if pair is None:
            raise ValueError(f"rated pair missing from frozen study: {source_pair_id}")
        candidate_masks = _load_masks(data_root, str(pair["candidate_image_path"]))
        reference_masks = _load_masks(data_root, str(pair["reference_image_path"]))
        reference_id = str(pair["reference_instance_id"])
        scorer = scorer_cache.get(reference_id)
        if scorer is None:
            scorer = PreparedReferenceScorer(reference_masks)
            scorer_cache[reference_id] = scorer
        _, aligned_reference = scorer.score(candidate_masks)
        components = compute_spatial_structure_components(
            candidate_masks,
            aligned_reference,
        )
        score = spatial_structure_score(components)
        rows.append(
            {
                "source_pair_id": source_pair_id,
                "char_id": str(pair["char_id"]),
                "target_char": str(pair["target_char"]),
                "candidate_instance_id": str(pair["candidate_instance_id"]),
                "reference_instance_id": str(pair["reference_instance_id"]),
                "human_mean": float(rating["human_mean"]),
                "production_score": float(rating["system_score"]),
                "coverage_aware_score": float(rating["coverage_aware_score"]),
                **components.as_dict(),
                "spatial_structure_score": score,
                "group_cv_fold": _stable_fold(str(pair["char_id"])),
            }
        )
        if index % 25 == 0:
            print(f"spatial_score_features={index}/{len(canonical_ratings)}")
    return rows


def analyze_development_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_iterations: int = 10_000,
    bootstrap_seed: int = 20260814,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("development analysis requires at least one row")
    matrix = _feature_matrix(rows)
    targets = np.asarray([float(row["human_mean"]) for row in rows])
    folds = np.asarray([int(row["group_cv_fold"]) for row in rows])

    out_of_fold = np.full(len(rows), np.nan, dtype=np.float64)
    fold_rows: list[dict[str, Any]] = []
    for fold in range(GROUP_FOLD_COUNT):
        test_indices = np.flatnonzero(folds == fold)
        train_indices = np.flatnonzero(folds != fold)
        if len(test_indices) == 0 or len(train_indices) == 0:
            raise ValueError(f"group fold {fold} is empty")
        weights, training_rho = _select_weights(matrix, targets, train_indices)
        out_of_fold[test_indices] = _score_with_weights(matrix[test_indices], weights)
        fold_rows.append(
            {
                "fold": fold,
                "train_pair_count": len(train_indices),
                "test_pair_count": len(test_indices),
                "training_spearman": training_rho,
                **{
                    f"weight_{name}": float(weights[index])
                    for index, name in enumerate(FEATURE_ORDER)
                },
            }
        )
    if np.any(~np.isfinite(out_of_fold)):
        raise RuntimeError("out-of-fold predictions are incomplete")

    enriched = [
        {**dict(row), "spatial_group_cv_oof_score": float(out_of_fold[index])}
        for index, row in enumerate(rows)
    ]
    full_weights, full_weight_search_rho = _select_weights(
        matrix,
        targets,
        np.arange(len(rows)),
    )
    score_fields = (
        "production_score",
        "coverage_aware_score",
        "spatial_structure_score",
        "spatial_group_cv_oof_score",
    )
    correlation = {
        field: _spearman_with_p(
            [float(row[field]) for row in enriched],
            [float(row["human_mean"]) for row in enriched],
        )
        for field in score_fields
    }
    component_fields = tuple(FEATURE_ORDER)
    component_correlation = {
        field: _spearman_with_p(
            [float(row[field]) for row in enriched],
            [float(row["human_mean"]) for row in enriched],
        )
        for field in component_fields
    }
    bootstrap = _cluster_bootstrap(
        enriched,
        score_fields=score_fields,
        iterations=bootstrap_iterations,
        seed=bootstrap_seed,
    )
    component_bootstrap = _cluster_bootstrap(
        enriched,
        score_fields=component_fields,
        iterations=bootstrap_iterations,
        seed=bootstrap_seed + 1,
    )
    return {
        "rows": enriched,
        "folds": fold_rows,
        "report": {
            "schema_version": 1,
            "analysis_name": "spatial_structure_score_development_v1",
            "status": "DEVELOPMENT_ONLY_AWAITING_INDEPENDENT_CONFIRMATION",
            "claim_scope": (
                "Post-rating method development. The frozen formula requires evaluation "
                "on a new, previously unrated same-character confirmatory set."
            ),
            "pair_count": len(enriched),
            "character_count": len({str(row["char_id"]) for row in enriched}),
            "feature_order": list(FEATURE_ORDER),
            "frozen_rounded_weights": dict(SPATIAL_SCORE_WEIGHTS),
            "full_development_grid_search": {
                "grid_denominator": WEIGHT_GRID_DENOMINATOR,
                "best_weights": {
                    name: float(full_weights[index])
                    for index, name in enumerate(FEATURE_ORDER)
                },
                "apparent_training_spearman": full_weight_search_rho,
            },
            "group_cross_validation": {
                "fold_count": GROUP_FOLD_COUNT,
                "group_unit": "char_id",
                "fold_salt": GROUP_FOLD_SALT,
                "weight_selection_uses_training_fold_only": True,
            },
            "correlation_with_human_mean": correlation,
            "cluster_bootstrap": bootstrap,
            "component_ablation": {
                "correlation_with_human_mean": component_correlation,
                "cluster_bootstrap": component_bootstrap,
            },
        },
    }


def _latex_table(report: Mapping[str, Any]) -> str:
    results = report["correlation_with_human_mean"]
    bootstrap = report["cluster_bootstrap"]["rho_ci95"]
    labels = (
        ("production_score", "Frozen production"),
        ("coverage_aware_score", "Coverage-aware audit"),
        ("spatial_structure_score", "Frozen spatial formula (development)"),
        ("spatial_group_cv_oof_score", "Grouped-CV spatial predictions"),
    )

    def fmt(value: Any) -> str:
        return "--" if value is None else f"{float(value):.3f}"

    lines = [
        r"\begin{table}[t]",
        r"\caption{Development-stage association with mean human structural rating.}",
        r"\label{tab:spatial-score-development}",
        r"\centering",
        r"\begin{tabular}{lrr}",
        r"\toprule",
        r"Score & Spearman $\rho$ & Cluster-bootstrap 95\% CI \\",
        r"\midrule",
    ]
    for field, label in labels:
        interval = bootstrap[field]
        lines.append(
            f"{label} & {fmt(results[field]['rho'])} & "
            f"[{fmt(interval[0])}, {fmt(interval[1])}] \\\\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\begin{minipage}{0.96\columnwidth}\footnotesize",
            (
                "The spatial formula and its grouped cross-validation were developed "
                "after observing the original human study. They are exploratory until "
                "evaluated on the frozen confirmatory pair set."
            ),
            r"\end{minipage}",
            r"\end{table}",
            "",
        ]
    )
    return "\n".join(lines)


def write_spatial_score_development(
    output_dir: str | Path,
    result: Mapping[str, Any],
    *,
    frozen_pairs_path: Path,
    ratings_path: Path,
    data_root: Path,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows = list(result["rows"])
    report = dict(result["report"])
    report["generated_at_utc"] = datetime.now(UTC).isoformat()
    report["inputs"] = {
        "frozen_pairs": {
            "path": frozen_pairs_path.as_posix(),
            "sha256": _sha256(frozen_pairs_path),
        },
        "canonical_ratings": {
            "path": ratings_path.as_posix(),
            "sha256": _sha256(ratings_path),
        },
        "data_root": data_root.as_posix(),
    }
    report["frozen_score_specification"] = {
        "version": SPATIAL_SCORE_VERSION,
        "formula": (
            "100 * (0.70 * polar_js_similarity + 0.15 * grid_js_similarity "
            "+ 0.15 * projection_js_similarity)"
        ),
        "uses_character_identity": False,
        "uses_human_rating_at_inference": False,
        "alignment": "existing frozen constrained alignment",
        "change_policy": (
            "Do not change features, bins, weights, alignment, or thresholds after "
            "confirmatory human rating begins."
        ),
    }
    _write_csv(output / "development_features_and_predictions.csv", rows)
    _write_csv(output / "group_cv_folds.csv", list(result["folds"]))
    (output / "development_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "frozen_spatial_score_v1.json").write_text(
        json.dumps(report["frozen_score_specification"], ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (output / "table_spatial_score_development.tex").write_text(
        _latex_table(report),
        encoding="utf-8",
    )
    return report
