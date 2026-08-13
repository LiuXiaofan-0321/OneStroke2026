"""Repository and data preflight checks for the IJDAR experiment pipeline."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from onestroke_model.constants import CHANNELS, SCHEMA_VERSION

TASK1_EXPECTED = {
    "unet_model": ("src/onestroke_model/models/unet.py",),
    "deeplabv3plus_model": (
        "src/onestroke_model/models/deeplabv3plus.py",
        "src/onestroke_model/models/deeplab.py",
    ),
    "segformer_b2_release": ("releases/segformer_b2_v1/test_metrics.json",),
    "dataset_qc_report": ("artifacts/data_qc/dataset_qc_report_v1.json",),
    "dataset_qc_exclusions": (
        "artifacts/data_qc/dataset_qc_exclusion_contract_v1.csv",
    ),
    "dataset_qc_manifest": ("artifacts/data_qc/manifest_qc_v1.csv",),
    "dataset_qc_standard_split": ("artifacts/data_qc/standard_splits_qc_v1.csv",),
    "dataset_qc_character_split": (
        "artifacts/data_qc/character_disjoint_splits_qc_v1.csv",
    ),
}

WORKFLOW_EXPECTED = {
    "controlled_perturbation": (
        "src/onestroke_model/controlled_perturbations.py",
        "src/onestroke_model/perturbation_benchmark.py",
        "src/onestroke_model/scripts/run_controlled_perturbation_benchmark.py",
        "docs/controlled_perturbation_benchmark.md",
        "tests/test_controlled_perturbations.py",
        "tests/test_perturbation_benchmark.py",
    ),
    "structure_score_audit": (
        "src/onestroke_model/structure_score_audit.py",
        "src/onestroke_model/structure_score_audit_benchmark.py",
        "src/onestroke_model/scripts/run_structure_score_audit.py",
        "docs/structure_score_audit.md",
        "tests/test_structure_score_audit.py",
        "tests/test_structure_score_audit_benchmark.py",
    ),
    "feedback_diagnostic": (
        "src/onestroke_model/feedback_diagnostic_benchmark.py",
        "src/onestroke_model/feedback_diagnostic_rules.py",
        "src/onestroke_model/scripts/run_feedback_diagnostic_benchmark.py",
        "src/onestroke_model/scripts/compare_feedback_diagnostic_runs.py",
        "docs/feedback_diagnostic_accuracy_benchmark.md",
        "docs/feedback_diagnostic_fixes_v2.md",
    ),
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _candidate_exists(project_root: Path, candidates: Iterable[str]) -> tuple[bool, list[str]]:
    paths = [str(candidate) for candidate in candidates]
    return any((project_root / path).is_file() for path in paths), paths


def _resolve_manifest_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (project_root / path).resolve()


def audit_task1(project_root: Path) -> dict[str, Any]:
    components: dict[str, Any] = {}
    for name, candidates in TASK1_EXPECTED.items():
        exists, paths = _candidate_exists(project_root, candidates)
        components[name] = {"status": "PRESENT" if exists else "MISSING", "candidates": paths}

    result_candidates = list(
        project_root.glob("artifacts/**/seed*")
    ) + list(project_root.glob("artifacts/**/*multi*seed*"))
    components["multi_seed_results"] = {
        "status": "PRESENT" if result_candidates else "MISSING",
        "candidates": [str(path.relative_to(project_root)) for path in result_candidates],
    }
    task1_ready = all(
        components[key]["status"] == "PRESENT"
        for key in (
            "unet_model",
            "deeplabv3plus_model",
            "segformer_b2_release",
            "dataset_qc_report",
            "dataset_qc_exclusions",
            "dataset_qc_manifest",
            "dataset_qc_standard_split",
            "dataset_qc_character_split",
            "multi_seed_results",
        )
    )
    return {
        "status": "READY" if task1_ready else "PENDING_TASK1",
        "components": components,
        "policy": (
            "Task 1 is ready only with the DeepLabV3+ implementation, multi-seed "
            "results, and the frozen 769-sample QC-clean data contract."
        ),
    }


def audit_workflows(project_root: Path) -> dict[str, Any]:
    workflows: dict[str, Any] = {}
    for workflow, expected in WORKFLOW_EXPECTED.items():
        missing = [path for path in expected if not (project_root / path).is_file()]
        workflows[workflow] = {
            "status": "READY" if not missing else "MISSING_PREREQUISITES",
            "expected_files": list(expected),
            "missing_files": missing,
        }
    return workflows


def audit_standard_data(
    project_root: Path,
    manifest_path: Path,
    splits_path: Path,
) -> dict[str, Any]:
    if not manifest_path.is_file() or not splits_path.is_file():
        return {
            "status": "BLOCKED",
            "manifest": str(manifest_path),
            "splits": str(splits_path),
            "missing": [
                str(path)
                for path in (manifest_path, splits_path)
                if not path.is_file()
            ],
        }

    manifest = _read_csv(manifest_path)
    splits = _read_csv(splits_path)
    usable = [
        row
        for row in manifest
        if _truthy(row.get("has_all_masks")) and not str(row.get("errors", "")).strip()
    ]
    split_names = ("train", "val", "test")
    split_groups = {name: set() for name in split_names}
    split_chars = {name: set() for name in split_names}
    split_counts: Counter[str] = Counter()
    for row in splits:
        split = row.get("split", "")
        if split not in split_groups:
            continue
        split_counts[split] += 1
        split_groups[split].add(row.get("group_key", ""))
        split_chars[split].add(row.get("char_id", ""))

    group_overlap = {
        "train_val": sorted(split_groups["train"] & split_groups["val"]),
        "train_test": sorted(split_groups["train"] & split_groups["test"]),
        "val_test": sorted(split_groups["val"] & split_groups["test"]),
    }
    char_overlap = {
        "train_val": sorted(split_chars["train"] & split_chars["val"]),
        "train_test": sorted(split_chars["train"] & split_chars["test"]),
        "val_test": sorted(split_chars["val"] & split_chars["test"]),
    }
    path_fields = ("image_path", "vec1_path", "vec2_path", "vec3_path", "vec4_path", "vec5_path", "keypoint_path")
    existing_samples = 0
    for row in usable:
        if all(
            _resolve_manifest_path(project_root, row.get(field, "")).is_file()
            for field in path_fields
        ):
            existing_samples += 1

    duplicate_split_samples = [
        sample_id
        for sample_id, count in Counter(row.get("sample_id", "") for row in splits).items()
        if sample_id and count > 1
    ]
    usable_ids = {row.get("sample_id", "") for row in usable}
    split_ids = {row.get("sample_id", "") for row in splits}
    return {
        "status": "PASS" if not any(group_overlap.values()) and not duplicate_split_samples else "FAIL",
        "manifest": str(manifest_path.resolve()),
        "manifest_sha256": _sha256(manifest_path),
        "splits": str(splits_path.resolve()),
        "splits_sha256": _sha256(splits_path),
        "manifest_rows": len(manifest),
        "usable_rows": len(usable),
        "unusable_rows": len(manifest) - len(usable),
        "split_counts": dict(split_counts),
        "split_group_counts": {name: len(split_groups[name]) for name in split_names},
        "split_character_counts": {name: len(split_chars[name]) for name in split_names},
        "group_overlap": group_overlap,
        "character_overlap": char_overlap,
        "standard_split_is_character_disjoint": not any(char_overlap.values()),
        "duplicate_split_sample_ids": duplicate_split_samples,
        "usable_samples_missing_from_split": sorted(usable_ids - split_ids),
        "unknown_samples_in_split": sorted(split_ids - usable_ids),
        "samples_with_all_local_paths_available": existing_samples,
        "samples_with_missing_local_paths": len(usable) - existing_samples,
        "local_training_data_available": existing_samples == len(usable) and bool(usable),
        "note": (
            "The standard split is group-disjoint but intentionally not character-disjoint. "
            "Character overlap here is not leakage for the standard benchmark; a separate frozen "
            "character-disjoint split is required for the generalization experiment."
        ),
    }


def audit_reference_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        return {"status": "BLOCKED", "manifest": str(manifest_path), "missing": True}
    rows = _read_csv(manifest_path)
    approved = [row for row in rows if row.get("review_status", "").strip().lower() == "approved"]
    by_style_char: defaultdict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_char: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in approved:
        by_style_char[(row.get("style_id", ""), row.get("target_char", ""))].append(row)
        by_char[row.get("target_char", "")].append(row)
    duplicate_ids = [
        value
        for value, count in Counter(row.get("reference_id", "") for row in approved).items()
        if value and count > 1
    ]
    same_style_different_instance = sum(len(items) * (len(items) - 1) // 2 for items in by_style_char.values())
    cross_style_same_character = sum(
        1
        for items in by_char.values()
        if len({item.get("style_id", "") for item in items}) >= 2
    )
    return {
        "status": "PASS" if not duplicate_ids else "FAIL",
        "manifest": str(manifest_path.resolve()),
        "manifest_sha256": _sha256(manifest_path),
        "rows": len(rows),
        "approved_references": len(approved),
        "style_count": len({row.get("style_id", "") for row in approved}),
        "unique_character_count": len(by_char),
        "duplicate_reference_ids": duplicate_ids,
        "same_style_different_instance_pair_count": same_style_different_instance,
        "same_character_cross_style_character_count": cross_style_same_character,
        "pair_support": {
            "same_character_same_style_different_instance": same_style_different_instance > 0,
            "same_character_cross_style": cross_style_same_character > 0,
            "different_character_negative": len(by_char) > 1,
        },
    }


def _cache_candidates(project_root: Path, preferred: Path) -> list[Path]:
    candidates: list[Path] = []
    if preferred.is_file():
        candidates.append(preferred)
    cache_root = project_root / "references" / "cache"
    if cache_root.is_dir():
        for path in sorted(cache_root.glob("**/index.json")):
            if path not in candidates:
                candidates.append(path)
    return candidates


def audit_reference_cache(
    project_root: Path,
    preferred_index: Path,
    reference_manifest_path: Path,
) -> dict[str, Any]:
    candidates = _cache_candidates(project_root, preferred_index)
    gitignore_path = project_root / ".gitignore"
    gitignore_text = gitignore_path.read_text(encoding="utf-8") if gitignore_path.is_file() else ""
    ignored_by_policy = "references/cache/" in gitignore_text.replace("\\", "/")
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "preferred_index": str(preferred_index),
        "searched_glob": "references/cache/**/index.json",
        "cache_gitignored": ignored_by_policy,
        "candidate_indexes": [str(path.resolve()) for path in candidates],
    }
    if not candidates:
        return {
            **base,
            "status": "BLOCKED",
            "reason": "REAL_REFERENCE_CACHE_MISSING",
            "formal_experiments_blocked": [
                "controlled_perturbation",
                "structure_score_audit",
                "feedback_diagnostic_before_after",
                "alignment_ablation",
                "cross_reference_scoring",
            ],
        }

    index_path = candidates[0]
    errors: list[str] = []
    warnings: list[str] = []
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {**base, "status": "FAIL", "index": str(index_path), "errors": [str(exc)]}
    if not isinstance(index, dict):
        return {**base, "status": "FAIL", "index": str(index_path), "errors": ["index must be a JSON object"]}

    if list(index.get("channels", [])) != list(CHANNELS):
        errors.append(f"channel schema mismatch: {index.get('channels')!r}")
    references = index.get("references")
    if not isinstance(references, list) or not references:
        errors.append("index.references must be a non-empty list")
        references = []
    if not index.get("model_version"):
        errors.append("model_version is missing")
    if not index.get("checkpoint_sha256"):
        errors.append("checkpoint_sha256 is missing")
    if index.get("cache_format") != "binary_masks_hwc_uint8":
        warnings.append(f"unexpected cache_format: {index.get('cache_format')!r}")

    reference_ids: list[str] = []
    style_character_pairs: list[tuple[str, str]] = []
    shapes: Counter[str] = Counter()
    missing_artifacts: list[str] = []
    invalid_artifacts: list[dict[str, str]] = []
    for item in references:
        if not isinstance(item, dict):
            errors.append("reference entry must be an object")
            continue
        reference_id = str(item.get("reference_id", ""))
        style_id = str(item.get("style_id", ""))
        target_char = str(item.get("target_char", ""))
        cache_path = index_path.parent / str(item.get("cache_path", ""))
        reference_ids.append(reference_id)
        style_character_pairs.append((style_id, target_char))
        if not reference_id or not style_id or len(target_char) != 1:
            errors.append(f"invalid reference metadata: {item!r}")
        if not cache_path.is_file():
            missing_artifacts.append(str(cache_path))
            continue
        try:
            with np.load(cache_path) as cached:
                masks = np.asarray(cached["binary_masks"])
                channels = [str(value) for value in cached["channels"].tolist()]
            if masks.ndim != 3 or masks.shape[-1] != len(CHANNELS):
                raise ValueError(f"expected [H,W,6], got {masks.shape}")
            if channels != list(CHANNELS):
                raise ValueError(f"channel schema mismatch: {channels!r}")
            if not np.all(np.isin(np.unique(masks), (0, 1, False, True))):
                raise ValueError("binary_masks contains values other than 0/1")
            if not np.any(masks[..., :5]):
                raise ValueError("direction masks contain no foreground")
            shapes[str(tuple(int(value) for value in masks.shape))] += 1
        except (OSError, KeyError, ValueError) as exc:
            invalid_artifacts.append({"reference_id": reference_id, "error": str(exc)})

    duplicates = sorted(
        value for value, count in Counter(reference_ids).items() if value and count > 1
    )
    duplicate_style_character = sorted(
        f"{style_id}:{target_char}"
        for (style_id, target_char), count in Counter(style_character_pairs).items()
        if style_id and target_char and count > 1
    )
    approved_ids: set[str] = set()
    if reference_manifest_path.is_file():
        approved_ids = {
            row.get("reference_id", "")
            for row in _read_csv(reference_manifest_path)
            if row.get("review_status", "").strip().lower() == "approved"
        }
    cache_ids = {value for value in reference_ids if value}
    if missing_artifacts:
        errors.append(f"{len(missing_artifacts)} cache artifacts are missing")
    if invalid_artifacts:
        errors.append(f"{len(invalid_artifacts)} cache artifacts are invalid")
    if duplicates:
        errors.append(f"{len(duplicates)} duplicate reference_id values")
    if len(shapes) > 1:
        errors.append(f"inconsistent mask shapes: {dict(shapes)}")
    if approved_ids and cache_ids != approved_ids:
        warnings.append("cache reference IDs do not exactly match approved reference manifest IDs")

    return {
        **base,
        "status": "PASS" if not errors else "FAIL",
        "index": str(index_path.resolve()),
        "index_sha256": _sha256(index_path),
        "index_schema_version": index.get("schema_version"),
        "model_version": index.get("model_version"),
        "checkpoint": index.get("checkpoint"),
        "checkpoint_sha256": index.get("checkpoint_sha256"),
        "channels": index.get("channels"),
        "canvas_size": index.get("canvas_size"),
        "num_references_declared": index.get("num_references"),
        "num_reference_entries": len(references),
        "mask_shapes": dict(shapes),
        "duplicate_reference_ids": duplicates,
        "duplicate_style_character_pairs": duplicate_style_character,
        "missing_artifacts": missing_artifacts,
        "invalid_artifacts": invalid_artifacts,
        "approved_manifest_reference_count": len(approved_ids),
        "cache_only_reference_ids": sorted(cache_ids - approved_ids) if approved_ids else [],
        "approved_references_missing_from_cache": sorted(approved_ids - cache_ids) if approved_ids else [],
        "errors": errors,
        "warnings": warnings,
    }


def build_preflight_report(
    project_root: str | Path,
    manifest: str | Path = "artifacts/data_recovery/manifest_resolved.csv",
    splits: str | Path = "artifacts/data_audit/splits.csv",
    reference_manifest: str | Path = "references/calli_tongji_beta_manifest.csv",
    cache_index: str | Path = "references/cache/segformer_b2_v1/index.json",
) -> dict[str, Any]:
    root = Path(project_root).resolve()

    def resolve(value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else root / path

    manifest_path = resolve(manifest)
    splits_path = resolve(splits)
    reference_manifest_path = resolve(reference_manifest)
    cache_index_path = resolve(cache_index)
    return {
        "schema_version": 1,
        "report_type": "ijdar_repository_preflight",
        "project_root": str(root),
        "git_commit": _git_commit(root),
        "task1": audit_task1(root),
        "workflows": audit_workflows(root),
        "standard_data": audit_standard_data(root, manifest_path, splits_path),
        "reference_manifest": audit_reference_manifest(reference_manifest_path),
        "reference_cache": audit_reference_cache(root, cache_index_path, reference_manifest_path),
    }


def missing_prerequisites(report: dict[str, Any]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    if report["task1"]["status"] != "READY":
        missing.append(
            {
                "status": "PENDING_TASK1",
                "item": "Task 1 model comparison and multi-seed artifacts",
                "details": report["task1"]["components"],
                "blocks": [
                    "DeepLabV3+ character-disjoint launcher execution",
                    "unified main segmentation table",
                    "multi-seed mean and sample standard deviation",
                ],
            }
        )
    for name, workflow in report["workflows"].items():
        if workflow["status"] != "READY":
            missing.append(
                {
                    "status": "BLOCKED",
                    "item": f"{name} workflow",
                    "details": {"missing_files": workflow["missing_files"]},
                    "blocks": [name],
                }
            )
    if report["reference_cache"]["status"] != "PASS":
        missing.append(
            {
                "status": "BLOCKED",
                "item": "Approved real reference mask cache",
                "details": report["reference_cache"],
                "blocks": report["reference_cache"].get("formal_experiments_blocked", []),
            }
        )
    if not report["standard_data"].get("local_training_data_available", False):
        missing.append(
            {
                "status": "BLOCKED",
                "item": "Locally resolvable segmentation dataset paths",
                "details": {
                    "samples_with_missing_local_paths": report["standard_data"].get(
                        "samples_with_missing_local_paths"
                    ),
                    "manifest": report["standard_data"].get("manifest"),
                },
                "blocks": ["character-disjoint training and evaluation on this machine"],
            }
        )
    return missing


def _status_markdown(report: dict[str, Any], missing: list[dict[str, Any]]) -> str:
    workflow_lines = "\n".join(
        f"| {name} | {value['status']} | {', '.join(value['missing_files']) or '-'} |"
        for name, value in report["workflows"].items()
    )
    data = report["standard_data"]
    refs = report["reference_manifest"]
    cache = report["reference_cache"]
    return "\n".join(
        [
            "# IJDAR Preflight Status",
            "",
            "This report is generated from the current worktree. It does not contain synthetic paper results.",
            "",
            "## Repository State",
            "",
            f"- Git commit: `{report.get('git_commit')}`",
            f"- Task 1 status: **{report['task1']['status']}**",
            f"- Missing prerequisite groups: **{len(missing)}**",
            "",
            "## Benchmark Workflows",
            "",
            "| Workflow | Status | Missing files |",
            "|---|---|---|",
            workflow_lines,
            "",
            "## Standard Segmentation Data",
            "",
            f"- Manifest rows: **{data.get('manifest_rows')}**",
            f"- Usable complete rows: **{data.get('usable_rows')}**",
            f"- Standard split counts: `{data.get('split_counts')}`",
            f"- Group overlap: `{data.get('group_overlap')}`",
            f"- Character overlap: train/val/test share **{len(data.get('character_overlap', {}).get('train_test', []))}** characters.",
            f"- Locally resolvable complete samples: **{data.get('samples_with_all_local_paths_available')} / {data.get('usable_rows')}**",
            "- Interpretation: the standard split is group-disjoint, but a separate character-disjoint split is still required.",
            "",
            "## Reference Library",
            "",
            f"- Approved references: **{refs.get('approved_references')}**",
            f"- Styles: **{refs.get('style_count')}**",
            f"- Unique characters: **{refs.get('unique_character_count')}**",
            f"- Same-style different-instance pairs supported: **{refs.get('pair_support', {}).get('same_character_same_style_different_instance')}**",
            f"- Same-character cross-style characters: **{refs.get('same_character_cross_style_character_count')}**",
            "",
            "## Real Reference Cache",
            "",
            f"- Status: **{cache.get('status')}**",
            f"- Preferred path: `{cache.get('preferred_index')}`",
            f"- Cache excluded by `.gitignore`: **{cache.get('cache_gitignored')}**",
            f"- Reason/errors: `{cache.get('reason', cache.get('errors', []))}`",
            "",
            "## Immediate Gates",
            "",
            "- Formal real-reference results may only be generated when `reference_cache.status == PASS`.",
            "- Synthetic smoke results remain implementation diagnostics and must not enter the paper.",
            "- Character-disjoint training requires the verified resolved manifest and the immutable frozen split.",
            "- DeepLabV3+ and multi-seed Task 1 outputs must be consumed when merged; they are not reimplemented here.",
            "",
        ]
    )


def _missing_markdown(missing: list[dict[str, Any]]) -> str:
    lines = [
        "# Missing IJDAR Prerequisites",
        "",
        "Missing inputs are reported explicitly. No synthetic or fabricated data is substituted.",
        "",
    ]
    if not missing:
        lines.append("No missing prerequisites were detected.")
        return "\n".join(lines) + "\n"
    for index, item in enumerate(missing, start=1):
        lines.extend(
            [
                f"## {index}. {item['item']}",
                "",
                f"- Status: **{item['status']}**",
                f"- Blocks: `{item.get('blocks', [])}`",
                "",
                "```json",
                json.dumps(item.get("details", {}), ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def write_preflight_outputs(output_dir: str | Path, report: dict[str, Any]) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    missing = missing_prerequisites(report)
    report_path = output / "preflight_report.json"
    cache_path = output.parent / "controlled_perturbation" / "cache_preflight.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    status_path = output / "STATUS.md"
    missing_path = output / "missing_prerequisites.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    cache_path.write_text(
        json.dumps(report["reference_cache"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    status_path.write_text(_status_markdown(report, missing), encoding="utf-8")
    missing_path.write_text(_missing_markdown(missing), encoding="utf-8")
    return {
        "preflight_report": report_path,
        "cache_preflight": cache_path,
        "status": status_path,
        "missing_prerequisites": missing_path,
    }
