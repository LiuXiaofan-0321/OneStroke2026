"""Direct-ink ablation for the frozen ASDS specification.

This analysis asks whether the ASDS scalar benefits from using the parser's
five-direction union, compared with applying the identical alignment and
frozen ASDS formula directly to the thresholded digital-writing raster.
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
from PIL import Image

from onestroke_model.controlled_perturbations import PreparedReferenceScorer
from onestroke_model.perturbation_benchmark import spearman_rho
from onestroke_model.spatial_structure_score import (
    SPATIAL_SCORE_VERSION,
    SPATIAL_SCORE_WEIGHTS,
    compute_spatial_structure_components,
    spatial_structure_score,
)

RAW_FOREGROUND_THRESHOLD = 240


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_image(data_root: Path, relative_path: str) -> Path:
    path = Path(relative_path.replace("\\", "/"))
    return path if path.is_absolute() else data_root / path


def _load_direct_ink(data_root: Path, relative_path: str) -> np.ndarray:
    image_path = _resolve_image(data_root, relative_path)
    with Image.open(image_path) as image:
        grayscale = np.asarray(image.convert("L"))
    foreground = grayscale < RAW_FOREGROUND_THRESHOLD
    if foreground.ndim != 2 or not np.any(foreground):
        raise ValueError(f"invalid direct-ink foreground: {image_path}")
    return foreground


def _ink_stack(foreground: np.ndarray) -> np.ndarray:
    """Place raw ink in one direction slot so the frozen union alignment applies."""

    mask = np.asarray(foreground, dtype=bool)
    stack = np.zeros((*mask.shape, 6), dtype=bool)
    stack[..., 0] = mask
    return stack


def build_direct_ink_rows(
    *,
    frozen_pairs: Sequence[Mapping[str, str]],
    parsed_rows: Sequence[Mapping[str, str]],
    data_root: Path,
) -> list[dict[str, Any]]:
    pairs = {str(row["pair_id"]): row for row in frozen_pairs}
    rows: list[dict[str, Any]] = []
    reference_cache: dict[str, PreparedReferenceScorer] = {}
    for index, parsed in enumerate(parsed_rows, start=1):
        pair_id = str(parsed["source_pair_id"])
        pair = pairs.get(pair_id)
        if pair is None:
            raise ValueError(f"parsed ASDS row missing from frozen pairs: {pair_id}")

        candidate_ink = _load_direct_ink(
            data_root, str(pair["candidate_image_path"])
        )
        reference_ink = _load_direct_ink(
            data_root, str(pair["reference_image_path"])
        )
        if candidate_ink.shape != reference_ink.shape:
            raise ValueError(
                f"direct-ink shape mismatch for {pair_id}: "
                f"{candidate_ink.shape} versus {reference_ink.shape}"
            )
        candidate_stack = _ink_stack(candidate_ink)
        reference_id = str(pair["reference_instance_id"])
        scorer = reference_cache.get(reference_id)
        if scorer is None:
            scorer = PreparedReferenceScorer(_ink_stack(reference_ink))
            reference_cache[reference_id] = scorer
        alignment, aligned_reference = scorer.score(candidate_stack)
        components = compute_spatial_structure_components(
            candidate_stack, aligned_reference
        )
        direct_score = spatial_structure_score(components)
        rows.append(
            {
                "source_pair_id": pair_id,
                "char_id": str(parsed["char_id"]),
                "target_char": str(parsed["target_char"]),
                "candidate_instance_id": str(parsed["candidate_instance_id"]),
                "reference_instance_id": str(parsed["reference_instance_id"]),
                "human_mean": float(parsed["human_mean"]),
                "parsed_asds_score": float(parsed["spatial_structure_score"]),
                "direct_ink_asds_score": direct_score,
                "direct_minus_parsed": direct_score
                - float(parsed["spatial_structure_score"]),
                **{
                    f"direct_{name}": value
                    for name, value in components.as_dict().items()
                },
                "direct_selected_scale": float(
                    alignment["selected_transform"]["scale"]
                ),
                "direct_selected_rotation_degrees": float(
                    alignment["selected_transform"]["rotation_degrees"]
                ),
                "direct_selected_translation_x": float(
                    alignment["selected_transform"]["translation_x"]
                ),
                "direct_selected_translation_y": float(
                    alignment["selected_transform"]["translation_y"]
                ),
                "direct_alignment_ink_iou": float(
                    alignment["selected_transform"]["alignment_ink_iou"]
                ),
            }
        )
        if index % 25 == 0:
            print(f"direct_ink_asds={index}/{len(parsed_rows)}")
    return rows


def _spearman(first: Sequence[float], second: Sequence[float]) -> dict[str, Any]:
    rho = spearman_rho(first, second)
    try:
        from scipy.stats import spearmanr
    except ImportError:
        p_value = None
    else:
        p_value = float(spearmanr(first, second).pvalue)
    return {"rho": rho, "p_two_sided": p_value}


def _cluster_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    *,
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    by_character: defaultdict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_character[str(row["char_id"])].append(index)
    characters = sorted(by_character, key=int)
    rng = np.random.default_rng(seed)
    parsed_samples: list[float] = []
    direct_samples: list[float] = []
    difference_samples: list[float] = []

    for _ in range(iterations):
        selected = rng.choice(characters, size=len(characters), replace=True)
        indices = [
            index for character in selected for index in by_character[str(character)]
        ]
        human = [float(rows[index]["human_mean"]) for index in indices]
        parsed = spearman_rho(
            [float(rows[index]["parsed_asds_score"]) for index in indices], human
        )
        direct = spearman_rho(
            [float(rows[index]["direct_ink_asds_score"]) for index in indices],
            human,
        )
        if parsed is None or direct is None:
            continue
        parsed_samples.append(float(parsed))
        direct_samples.append(float(direct))
        difference_samples.append(float(parsed - direct))

    def interval(values: Sequence[float]) -> list[float | None]:
        if not values:
            return [None, None]
        return [
            float(np.quantile(values, 0.025)),
            float(np.quantile(values, 0.975)),
        ]

    return {
        "cluster_unit": "char_id",
        "iterations_requested": iterations,
        "valid_iterations": len(difference_samples),
        "parsed_asds_rho_ci95": interval(parsed_samples),
        "direct_ink_asds_rho_ci95": interval(direct_samples),
        "parsed_minus_direct_rho_ci95": interval(difference_samples),
    }


def analyze_direct_ink_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_iterations: int = 10_000,
    bootstrap_seed: int = 20260814,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("direct-ink ASDS analysis requires at least one pair")
    human = [float(row["human_mean"]) for row in rows]
    parsed = [float(row["parsed_asds_score"]) for row in rows]
    direct = [float(row["direct_ink_asds_score"]) for row in rows]
    parsed_result = _spearman(parsed, human)
    direct_result = _spearman(direct, human)
    bootstrap = _cluster_bootstrap(
        rows, iterations=bootstrap_iterations, seed=bootstrap_seed
    )
    return {
        "schema_version": 1,
        "analysis_name": "direct_ink_asds_ablation_v1",
        "status": "RETROSPECTIVE_PAIRED_ABLATION_ON_ASDS_DEVELOPMENT_SET",
        "pair_count": len(rows),
        "character_count": len({str(row["char_id"]) for row in rows}),
        "foreground_extraction": {
            "source": "original direct-digital RGB raster",
            "conversion": "PIL grayscale",
            "threshold": f"pixel < {RAW_FOREGROUND_THRESHOLD}",
            "threshold_origin": "frozen dataset-QC foreground rule",
            "learned_preprocessing": False,
        },
        "alignment": (
            "same constrained translation/isotropic-scale/small-rotation search "
            "used by parsed ASDS"
        ),
        "asds_specification": {
            "version": SPATIAL_SCORE_VERSION,
            "weights": dict(SPATIAL_SCORE_WEIGHTS),
            "retuned_for_direct_ink": False,
        },
        "correlation_with_human_mean": {
            "parsed_asds": parsed_result,
            "direct_ink_asds": direct_result,
            "parsed_minus_direct_rho": (
                None
                if parsed_result["rho"] is None or direct_result["rho"] is None
                else float(parsed_result["rho"] - direct_result["rho"])
            ),
        },
        "parsed_direct_score_association": _spearman(parsed, direct),
        "character_cluster_bootstrap": bootstrap,
    }


def _latex_table(report: Mapping[str, Any]) -> str:
    results = report["correlation_with_human_mean"]
    bootstrap = report["character_cluster_bootstrap"]

    def fmt(value: Any) -> str:
        return "--" if value is None else f"{float(value):.3f}"

    parsed_ci = bootstrap["parsed_asds_rho_ci95"]
    direct_ci = bootstrap["direct_ink_asds_rho_ci95"]
    difference_ci = bootstrap["parsed_minus_direct_rho_ci95"]
    return "\n".join(
        [
            r"\begin{table}[t]",
            r"\caption{Direct-ink ablation of the frozen ASDS specification on the same 150 development pairs.}",
            r"\label{tab:direct-ink-asds}",
            r"\centering",
            r"\begin{tabular}{@{}lcc@{}}",
            r"\toprule",
            r"ASDS input & Spearman $\rho$ & 95\% CI \\",
            r"\midrule",
            (
                "Parsed union & "
                f"{fmt(results['parsed_asds']['rho'])} & "
                f"[{fmt(parsed_ci[0])}, {fmt(parsed_ci[1])}] \\\\"
            ),
            (
                "Direct ink & "
                f"{fmt(results['direct_ink_asds']['rho'])} & "
                f"[{fmt(direct_ci[0])}, {fmt(direct_ci[1])}] \\\\"
            ),
            r"\midrule",
            (
                r"$\Delta\rho$ (parsed--direct) & "
                f"{fmt(results['parsed_minus_direct_rho'])} & "
                f"[{fmt(difference_ci[0])}, {fmt(difference_ci[1])}] \\\\"
            ),
            r"\bottomrule",
            r"\end{tabular}",
            r"\parbox{0.86\columnwidth}{\footnotesize\raggedright",
            (
                "Both variants use the same alignment policy, ASDS features, "
                "and frozen weights. Direct ink uses the frozen dataset-QC rule: "
                "grayscale intensity $<240$. No threshold or weight was selected "
                "against the ratings.}"
            ),
            r"\end{table}",
            "",
        ]
    )


def write_direct_ink_analysis(
    output_dir: str | Path,
    *,
    rows: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    frozen_pairs_path: Path,
    parsed_rows_path: Path,
    data_root: Path,
) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    payload = dict(report)
    payload["generated_at_utc"] = datetime.now(UTC).isoformat()
    payload["inputs"] = {
        "frozen_pairs": {
            "path": frozen_pairs_path.as_posix(),
            "sha256": _sha256(frozen_pairs_path),
        },
        "parsed_asds_rows": {
            "path": parsed_rows_path.as_posix(),
            "sha256": _sha256(parsed_rows_path),
        },
        "data_root": data_root.as_posix(),
    }
    _write_csv(output / "direct_ink_asds_pairs.csv", rows)
    (output / "direct_ink_asds_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "table_direct_ink_asds.tex").write_text(
        _latex_table(payload), encoding="utf-8"
    )
