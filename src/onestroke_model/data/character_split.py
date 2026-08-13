"""Deterministic character-disjoint train/validation/test splitting."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SPLIT_NAMES = ("train", "val", "test")
ALGORITHM_VERSION = "character_disjoint_balanced_v1"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def _git_commit(project_root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None


def _largest_remainder_counts(total: int, ratios: dict[str, float]) -> dict[str, int]:
    raw = {name: total * ratios[name] for name in SPLIT_NAMES}
    counts = {name: int(raw[name]) for name in SPLIT_NAMES}
    remaining = total - sum(counts.values())
    order = sorted(
        SPLIT_NAMES,
        key=lambda name: (
            -round(raw[name] - counts[name], 12),
            SPLIT_NAMES.index(name),
        ),
    )
    for name in order[:remaining]:
        counts[name] += 1
    return counts


def _identity_values(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    output = {"writer_id": set(), "source_id": set()}
    for row in rows:
        for field, collected_values in output.items():
            value = str(row.get(field, "")).strip()
            if value:
                collected_values.add(value)
    return output


def _cross_split_identity_overlap(
    char_rows: dict[str, list[dict[str, str]]],
    assignments: dict[str, str],
) -> dict[str, Any]:
    identities: dict[str, defaultdict[str, set[str]]] = {
        "writer_id": defaultdict(set),
        "source_id": defaultdict(set),
    }
    for char_id, split in assignments.items():
        for row in char_rows[char_id]:
            for field in identities:
                value = str(row.get(field, "")).strip()
                if value:
                    identities[field][value].add(split)
    details: dict[str, Any] = {}
    for field, mapping in identities.items():
        overlaps = {
            value: sorted(splits)
            for value, splits in mapping.items()
            if len(splits) > 1
        }
        details[field] = {
            "unique_values": len(mapping),
            "cross_split_values": overlaps,
            "cross_split_value_count": len(overlaps),
        }
    return details


def assign_character_disjoint(
    manifest_rows: list[dict[str, str]],
    *,
    seed: int,
    train_ratio: float,
    val_ratio: float,
) -> tuple[list[dict[str, object]], dict[str, Any]]:
    if not 0 < train_ratio < 1 or not 0 < val_ratio < 1 or train_ratio + val_ratio >= 1:
        raise ValueError("ratios must satisfy 0 < train, val and train + val < 1")
    usable = [
        row
        for row in manifest_rows
        if _truthy(row.get("has_all_masks")) and not str(row.get("errors", "")).strip()
    ]
    if not usable:
        raise ValueError("manifest contains no usable complete samples")
    if any(not str(row.get("char_id", "")).strip() for row in usable):
        raise ValueError("every usable sample must have a non-empty char_id")

    char_rows: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in usable:
        char_rows[str(row["char_id"]).strip()].append(row)
    if len(char_rows) < 3:
        raise ValueError("at least three distinct characters are required")

    ratios = {
        "train": float(train_ratio),
        "val": float(val_ratio),
        "test": float(1.0 - train_ratio - val_ratio),
    }
    target_char_counts = _largest_remainder_counts(len(char_rows), ratios)
    target_sample_counts = {name: len(usable) * ratios[name] for name in SPLIT_NAMES}

    # Large character groups are assigned first. The seeded hash is only a
    # deterministic tie-breaker and never depends on model performance.
    ordered_chars = sorted(
        char_rows,
        key=lambda char_id: (-len(char_rows[char_id]), _stable_hash(seed, char_id)),
    )
    assignments: dict[str, str] = {}
    split_chars = {name: [] for name in SPLIT_NAMES}
    split_samples = Counter({name: 0 for name in SPLIT_NAMES})
    split_identities = {
        name: {"writer_id": set(), "source_id": set()} for name in SPLIT_NAMES
    }

    for char_id in ordered_chars:
        rows = char_rows[char_id]
        identities = _identity_values(rows)
        candidates = [
            name
            for name in SPLIT_NAMES
            if len(split_chars[name]) < target_char_counts[name]
        ]
        if not candidates:
            raise RuntimeError("internal split capacity error")

        def assignment_cost(
            split: str,
            *,
            current_rows: list[dict[str, str]] = rows,
            current_identities: dict[str, set[str]] = identities,
        ) -> tuple[float, float, int]:
            sample_after = split_samples[split] + len(current_rows)
            normalized_sample_deviation = abs(
                sample_after - target_sample_counts[split]
            ) / max(1.0, target_sample_counts[split])
            cross_split_identity_count = 0
            for field, values in current_identities.items():
                for other in SPLIT_NAMES:
                    if other != split:
                        cross_split_identity_count += len(values & split_identities[other][field])
            sample_fill_ratio = sample_after / max(1.0, target_sample_counts[split])
            return (
                normalized_sample_deviation + 0.10 * cross_split_identity_count,
                sample_fill_ratio,
                SPLIT_NAMES.index(split),
            )

        selected = min(candidates, key=assignment_cost)
        assignments[char_id] = selected
        split_chars[selected].append(char_id)
        split_samples[selected] += len(rows)
        identities = _identity_values(rows)
        for field, values in identities.items():
            split_identities[selected][field].update(values)

    output_rows: list[dict[str, object]] = []
    for char_id in sorted(char_rows):
        split = assignments[char_id]
        for row in sorted(char_rows[char_id], key=lambda item: item["sample_id"]):
            output_rows.append(
                {
                    "sample_id": row["sample_id"],
                    "char_id": char_id,
                    "sample_index": row.get("sample_index", ""),
                    "writer_id": row.get("writer_id", ""),
                    "source_id": row.get("source_id", ""),
                    "split": split,
                    "split_seed": seed,
                    "algorithm_version": ALGORITHM_VERSION,
                }
            )

    char_sets = {name: set(split_chars[name]) for name in SPLIT_NAMES}
    overlaps = {
        "train_val": sorted(char_sets["train"] & char_sets["val"]),
        "train_test": sorted(char_sets["train"] & char_sets["test"]),
        "val_test": sorted(char_sets["val"] & char_sets["test"]),
    }
    if any(overlaps.values()):
        raise RuntimeError(f"character-disjoint invariant failed: {overlaps}")
    report = {
        "schema_version": 1,
        "split_type": "character_disjoint",
        "algorithm_version": ALGORITHM_VERSION,
        "seed": seed,
        "ratios": ratios,
        "num_usable_samples": len(usable),
        "num_characters": len(char_rows),
        "target_character_counts": target_char_counts,
        "target_sample_counts": target_sample_counts,
        "actual_character_counts": {name: len(split_chars[name]) for name in SPLIT_NAMES},
        "actual_sample_counts": dict(split_samples),
        "characters": {name: sorted(split_chars[name]) for name in SPLIT_NAMES},
        "character_sample_counts": {
            char_id: len(rows) for char_id, rows in sorted(char_rows.items())
        },
        "character_overlap": overlaps,
        "assertions": {
            "train_val_character_overlap_zero": not overlaps["train_val"],
            "train_test_character_overlap_zero": not overlaps["train_test"],
            "val_test_character_overlap_zero": not overlaps["val_test"],
            "all_usable_samples_assigned_once": len(output_rows) == len(usable),
        },
        "identity_overlap": _cross_split_identity_overlap(char_rows, assignments),
        "selection_policy": (
            "Characters ordered by descending sample count with a seeded SHA-256 tie-breaker; "
            "assigned under fixed largest-remainder character capacities to balance samples "
            "and discourage writer/source overlap. No model score is read."
        ),
    }
    return output_rows, report


def build_character_disjoint_split(
    manifest_path: str | Path,
    output_path: str | Path,
    report_path: str | Path,
    *,
    seed: int = 20260811,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path).resolve()
    output_path = Path(output_path)
    report_path = Path(report_path)
    rows, report = assign_character_disjoint(
        _read_csv(manifest_path),
        seed=seed,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
    )
    _write_csv(
        output_path,
        rows,
        [
            "sample_id",
            "char_id",
            "sample_index",
            "writer_id",
            "source_id",
            "split",
            "split_seed",
            "algorithm_version",
        ],
    )
    root = Path(project_root or Path.cwd()).resolve()
    report.update(
        {
            "manifest": str(manifest_path),
            "manifest_sha256": _sha256(manifest_path),
            "split_csv": str(output_path.resolve()),
            "split_sha256": _sha256(output_path),
            "git_commit_at_freeze": _git_commit(root),
            "exact_command": (
                "python -m onestroke_model.scripts.build_character_disjoint_split "
                f"--manifest {manifest_path} --output {output_path} "
                f"--report {report_path} --seed {seed} "
                f"--train-ratio {train_ratio} --val-ratio {val_ratio}"
            ),
            "freeze_policy": (
                "This split must not be changed after inspecting validation or test performance. "
                "Test is evaluation-only."
            ),
        }
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
