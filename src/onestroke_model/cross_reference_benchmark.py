"""Cross-reference pair selection and structural-score benchmarking."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from onestroke_model.perturbation_benchmark import bootstrap_mean_ci95
from onestroke_model.style_scoring import score_masks

PAIR_TYPES = (
    "same_character_same_style_different_instance",
    "same_character_cross_style",
    "different_character_negative",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def _stable_hash(seed: int, *values: str) -> str:
    payload = ":".join([str(seed), *values])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_approved_references(manifest_path: str | Path) -> list[dict[str, str]]:
    rows = _read_csv(Path(manifest_path))
    approved = [
        row
        for row in rows
        if row.get("review_status", "").strip().lower() == "approved"
    ]
    if not approved:
        raise ValueError("reference manifest contains no approved rows")
    required = ("reference_id", "style_id", "target_char")
    for row in approved:
        missing = [field for field in required if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError(f"approved reference is missing fields {missing}: {row!r}")
        if len(row["target_char"]) != 1:
            raise ValueError(f"target_char must be one Unicode character: {row!r}")
    ids = [row["reference_id"] for row in approved]
    duplicates = [value for value, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate approved reference IDs: {duplicates}")
    return approved


def _unordered_pairs(rows: Sequence[dict[str, str]]) -> list[tuple[dict[str, str], dict[str, str]]]:
    return [
        (rows[first], rows[second])
        for first in range(len(rows))
        for second in range(first + 1, len(rows))
    ]


def audit_pair_availability(references: Sequence[dict[str, str]]) -> dict[str, Any]:
    by_style_char: defaultdict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_char: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in references:
        by_style_char[(row["style_id"], row["target_char"])].append(row)
        by_char[row["target_char"]].append(row)

    same_style_pairs = sum(
        len(rows) * (len(rows) - 1) // 2 for rows in by_style_char.values()
    )
    cross_style_pairs = 0
    cross_style_characters: list[str] = []
    for target_char, rows in by_char.items():
        count = sum(
            1
            for first, second in _unordered_pairs(rows)
            if first["style_id"] != second["style_id"]
        )
        if count:
            cross_style_characters.append(target_char)
            cross_style_pairs += count
    return {
        "schema_version": 1,
        "reference_count": len(references),
        "style_count": len({row["style_id"] for row in references}),
        "character_count": len(by_char),
        "availability": {
            "same_character_same_style_different_instance": {
                "supported": same_style_pairs > 0,
                "available_unordered_pairs": same_style_pairs,
            },
            "same_character_cross_style": {
                "supported": cross_style_pairs > 0,
                "available_unordered_pairs": cross_style_pairs,
                "characters": sorted(cross_style_characters),
            },
            "different_character_negative": {
                "supported": len(by_char) > 1,
                "role": "sanity_check_only",
            },
        },
        "self_pairs_allowed": False,
        "selection_independent_of_score": True,
        "license_note": "Pair artifacts contain reference IDs and metadata only; source images are not redistributed.",
    }


def _orient_pair(
    first: dict[str, str],
    second: dict[str, str],
    *,
    seed: int,
) -> tuple[dict[str, str], dict[str, str]]:
    pair_hash = _stable_hash(seed, first["reference_id"], second["reference_id"])
    return (first, second) if int(pair_hash[-1], 16) % 2 == 0 else (second, first)


def _pair_row(
    first: dict[str, str],
    second: dict[str, str],
    *,
    pair_type: str,
    seed: int,
) -> dict[str, Any]:
    candidate, reference = _orient_pair(first, second, seed=seed)
    pair_id = _stable_hash(
        seed,
        pair_type,
        min(first["reference_id"], second["reference_id"]),
        max(first["reference_id"], second["reference_id"]),
    )[:20]
    return {
        "pair_id": pair_id,
        "pair_type": pair_type,
        "candidate_reference_id": candidate["reference_id"],
        "reference_reference_id": reference["reference_id"],
        "candidate_char": candidate["target_char"],
        "reference_char": reference["target_char"],
        "candidate_style_id": candidate["style_id"],
        "reference_style_id": reference["style_id"],
        "same_character": candidate["target_char"] == reference["target_char"],
        "same_style": candidate["style_id"] == reference["style_id"],
        "selection_seed": seed,
        "orientation_policy": "stable SHA-256 parity; one orientation per unordered pair",
    }


def select_cross_reference_pairs(
    references: Sequence[dict[str, str]],
    *,
    seed: int = 20260811,
    negative_pairs: int = 50,
) -> list[dict[str, Any]]:
    if negative_pairs < 0:
        raise ValueError("negative_pairs must be >= 0")
    by_style_char: defaultdict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_char: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in references:
        by_style_char[(row["style_id"], row["target_char"])].append(row)
        by_char[row["target_char"]].append(row)

    pairs: list[dict[str, Any]] = []
    for rows in by_style_char.values():
        for first, second in _unordered_pairs(sorted(rows, key=lambda row: row["reference_id"])):
            pairs.append(
                _pair_row(
                    first,
                    second,
                    pair_type="same_character_same_style_different_instance",
                    seed=seed,
                )
            )
    for rows in by_char.values():
        for first, second in _unordered_pairs(sorted(rows, key=lambda row: row["reference_id"])):
            if first["style_id"] != second["style_id"]:
                pairs.append(
                    _pair_row(
                        first,
                        second,
                        pair_type="same_character_cross_style",
                        seed=seed,
                    )
                )

    negative_candidates: list[tuple[dict[str, str], dict[str, str]]] = []
    sorted_refs = sorted(references, key=lambda row: row["reference_id"])
    for first, second in _unordered_pairs(sorted_refs):
        if first["target_char"] != second["target_char"]:
            negative_candidates.append((first, second))
    negative_candidates.sort(
        key=lambda pair: _stable_hash(
            seed,
            "negative",
            pair[0]["reference_id"],
            pair[1]["reference_id"],
        )
    )
    for first, second in negative_candidates[:negative_pairs]:
        pairs.append(
            _pair_row(
                first,
                second,
                pair_type="different_character_negative",
                seed=seed,
            )
        )
    return sorted(pairs, key=lambda row: (PAIR_TYPES.index(row["pair_type"]), row["pair_id"]))


def score_cross_reference_pairs(
    pairs: Sequence[Mapping[str, Any]],
    cached_references: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {str(row["reference_id"]): row for row in cached_references}
    scores: list[dict[str, Any]] = []
    for pair in pairs:
        candidate_id = str(pair["candidate_reference_id"])
        reference_id = str(pair["reference_reference_id"])
        if candidate_id == reference_id:
            raise ValueError(f"self-pair is forbidden: {pair!r}")
        missing = [value for value in (candidate_id, reference_id) if value not in by_id]
        if missing:
            raise ValueError(f"pair references are missing from cache: {missing}")
        evidence, _ = score_masks(
            np.asarray(by_id[candidate_id]["masks"], dtype=bool),
            np.asarray(by_id[reference_id]["masks"], dtype=bool),
        )
        scores.append(
            {
                **dict(pair),
                "prototype_structure_score": evidence["prototype_structure_score"],
                "direction_macro_dice": evidence["direction_macro_dice"],
                "ink_iou": evidence["ink_iou"],
                "keypoint_f1_radius_3": evidence["keypoint_tolerant_f1_radius_3"],
                "selected_scale": evidence["selected_transform"]["scale"],
                "selected_rotation_degrees": evidence["selected_transform"][
                    "rotation_degrees"
                ],
                "selected_translation_x": evidence["selected_transform"]["translation_x"],
                "selected_translation_y": evidence["selected_transform"]["translation_y"],
            }
        )
    return scores


def cliffs_delta(first: Sequence[float], second: Sequence[float]) -> float | None:
    if not first or not second:
        return None
    greater = sum(left > right for left in first for right in second)
    less = sum(left < right for left in first for right in second)
    return float((greater - less) / (len(first) * len(second)))


def summarize_cross_reference_scores(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_iterations: int = 2000,
    seed: int = 20260811,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: defaultdict[str, list[float]] = defaultdict(list)
    style_grouped: defaultdict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        score = float(row["prototype_structure_score"])
        pair_type = str(row["pair_type"])
        grouped[pair_type].append(score)
        style_grouped[
            (
                pair_type,
                str(row["candidate_style_id"]),
                str(row["reference_style_id"]),
            )
        ].append(score)

    summaries: list[dict[str, Any]] = []
    for pair_type in PAIR_TYPES:
        values = grouped.get(pair_type, [])
        low, high = bootstrap_mean_ci95(
            values,
            seed_key=f"cross-reference:{seed}:{pair_type}",
            iterations=bootstrap_iterations,
        )
        summaries.append(
            {
                "pair_type": pair_type,
                "n": len(values),
                "mean": float(np.mean(values)) if values else None,
                "median": float(np.median(values)) if values else None,
                "std_ddof1": float(np.std(values, ddof=1)) if len(values) > 1 else None,
                "mean_ci95_low": low,
                "mean_ci95_high": high,
            }
        )
    negative = grouped.get("different_character_negative", [])
    effects = {
        pair_type: {
            "comparison": f"{pair_type} minus different_character_negative",
            "cliffs_delta": cliffs_delta(grouped.get(pair_type, []), negative),
        }
        for pair_type in PAIR_TYPES[:2]
    }
    style_summaries = [
        {
            "pair_type": key[0],
            "candidate_style_id": key[1],
            "reference_style_id": key[2],
            "n": len(values),
            "mean": float(np.mean(values)),
            "median": float(np.median(values)),
        }
        for key, values in sorted(style_grouped.items())
    ]
    metadata = {
        "effects_vs_negative": effects,
        "style_stratified": style_summaries,
        "paired_difference": {
            "status": (
                "SUPPORTED"
                if grouped.get("same_character_same_style_different_instance")
                and grouped.get("same_character_cross_style")
                else "UNSUPPORTED_BY_CURRENT_REFERENCE_LIBRARY"
            ),
            "reason": (
                None
                if grouped.get("same_character_same_style_different_instance")
                and grouped.get("same_character_cross_style")
                else "No same-character same-style different-instance pairs are available."
            ),
        },
    }
    return summaries, metadata


def write_cross_reference_outputs(
    output_dir: str | Path,
    *,
    availability: Mapping[str, Any],
    pairs: Sequence[Mapping[str, Any]],
    scores: Sequence[Mapping[str, Any]] | None = None,
    input_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "cross_reference_pair_availability.json").write_text(
        json.dumps(availability, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_csv(output / "cross_reference_pairs.csv", pairs)
    report: dict[str, Any] = {
        "schema_version": 1,
        "benchmark_name": "onestroke_cross_reference_v1",
        "availability": dict(availability),
        "pair_count": len(pairs),
        "pair_type_counts": dict(Counter(str(row["pair_type"]) for row in pairs)),
        "input_metadata": dict(input_metadata or {}),
        "formal_results_available": scores is not None,
    }
    if scores is None:
        (output / "BLOCKED.md").write_text(
            """# Cross-Reference Formal Run Blocked

Pair availability and score-independent selection are complete.
Formal scoring is blocked because the approved real reference mask cache is unavailable.
No synthetic scores are substituted.
""",
            encoding="utf-8",
        )
    else:
        (output / "BLOCKED.md").unlink(missing_ok=True)
        _write_csv(output / "cross_reference_scores.csv", scores)
        summary, statistics = summarize_cross_reference_scores(scores)
        _write_csv(output / "cross_reference_summary.csv", summary)
        (output / "cross_reference_statistics.json").write_text(
            json.dumps(statistics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report["summary"] = summary
        report["statistics"] = statistics
    (output / "cross_reference_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown = [
        "# Cross-Reference Structural Assessment",
        "",
        f"- Formal scores available: **{report['formal_results_available']}**",
        f"- Selected pairs: **{report['pair_count']}**",
        f"- Pair counts: `{report['pair_type_counts']}`",
        f"- Same-style different-instance supported: **{availability['availability']['same_character_same_style_different_instance']['supported']}**",
        f"- Cross-style same-character supported: **{availability['availability']['same_character_cross_style']['supported']}**",
        "",
        "Different-character pairs are a negative sanity check only. Self-pairs are forbidden.",
    ]
    if scores is None:
        markdown.extend(
            [
                "",
                "Formal score distributions are BLOCKED by the missing approved real cache.",
            ]
        )
    (output / "cross_reference_report.md").write_text(
        "\n".join(markdown) + "\n",
        encoding="utf-8",
    )
    return report
