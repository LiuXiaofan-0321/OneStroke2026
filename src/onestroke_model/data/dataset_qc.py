"""Semantic quality control for the recovered legacy segmentation dataset."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from onestroke_model.constants import CHANNELS
from onestroke_model.data.legacy_gt_recovery import MASK_FILENAMES
from onestroke_model.reproducibility import sha256_file, utc_now_iso

QC_SCHEMA_VERSION = 1
QC_VERSION = "dataset_qc_v1"
DEFAULT_MISMATCH_IOU_THRESHOLD = 0.80


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _sample_sort_key(sample_id: str) -> tuple[tuple[int, object], ...]:
    parts: list[tuple[int, object]] = []
    for value in str(sample_id).split("/"):
        try:
            parts.append((0, int(value)))
        except ValueError:
            parts.append((1, value))
    return tuple(parts)


def _sha256_array(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(value.shape).encode("ascii"))
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(value.tobytes())
    return digest.hexdigest()


def _mask_iou(first: np.ndarray, second: np.ndarray) -> float:
    intersection = int(np.count_nonzero(first & second))
    union = int(np.count_nonzero(first | second))
    return 1.0 if union == 0 else float(intersection / union)


def _portable_path(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _resolve_sample_paths(
    row: Mapping[str, str],
    dataset_root: Path,
) -> tuple[Path, Path]:
    char_id = str(row["char_id"]).strip()
    sample_index = str(row["sample_index"]).strip()
    sample_dir = dataset_root / char_id / sample_index
    return sample_dir / "0.jpg", sample_dir / "0.npy"


def _load_binary_masks(path: Path) -> tuple[np.ndarray, bool]:
    value = np.asarray(np.load(path, allow_pickle=False))
    if value.ndim != 3 or value.shape[-1] != len(CHANNELS):
        raise ValueError(f"expected [H,W,{len(CHANNELS)}], got {value.shape}")
    binary_values = bool(np.all(np.isin(np.unique(value), [0, 1, 255])))
    return value > 0, binary_values


def _audit_complete_samples(
    manifest_path: Path,
    dataset_root: Path,
    *,
    mismatch_iou_threshold: float,
) -> list[dict[str, Any]]:
    rows = [
        row
        for row in _read_csv(manifest_path)
        if _truthy(row.get("has_all_masks")) and not str(row.get("errors", "")).strip()
    ]
    audited: list[dict[str, Any]] = []
    for row in rows:
        sample_id = str(row["sample_id"]).strip()
        image_path, mask_path = _resolve_sample_paths(row, dataset_root)
        hard_reasons: list[str] = []
        image_array: np.ndarray | None = None
        masks: np.ndarray | None = None
        image_pixel_sha256 = ""
        mask_content_sha256 = ""
        image_gt_ink_iou = math.nan
        binary_masks = False
        try:
            with Image.open(image_path) as image:
                image_array = np.asarray(image.convert("L"))
            image_pixel_sha256 = _sha256_array(image_array)
        except (OSError, ValueError) as exc:
            hard_reasons.append(f"IMAGE_DECODE_ERROR:{type(exc).__name__}")
        try:
            masks, binary_masks = _load_binary_masks(mask_path)
            mask_content_sha256 = _sha256_array(masks.astype(np.uint8))
            if not binary_masks:
                hard_reasons.append("NON_BINARY_MASK_VALUES")
        except (OSError, ValueError) as exc:
            hard_reasons.append(f"MASK_LOAD_ERROR:{type(exc).__name__}")

        if image_array is not None and masks is not None:
            if masks.shape[:2] != image_array.shape:
                hard_reasons.append("IMAGE_MASK_SHAPE_MISMATCH")
            else:
                image_foreground = image_array < 240
                direction_ink = np.any(masks[..., :5], axis=-1)
                image_gt_ink_iou = _mask_iou(image_foreground, direction_ink)
                if image_gt_ink_iou < mismatch_iou_threshold:
                    hard_reasons.append(
                        f"IMAGE_GT_MISMATCH_IOU_LT_{mismatch_iou_threshold:.2f}"
                    )

        audited.append(
            {
                "schema_version": QC_SCHEMA_VERSION,
                "qc_version": QC_VERSION,
                "sample_id": sample_id,
                "char_id": str(row["char_id"]).strip(),
                "sample_index": str(row["sample_index"]).strip(),
                "image_relative_path": str(image_path.relative_to(dataset_root)).replace(
                    "\\", "/"
                ),
                "stacked_mask_relative_path": str(
                    mask_path.relative_to(dataset_root)
                ).replace("\\", "/"),
                "image_pixel_sha256": image_pixel_sha256,
                "mask_content_sha256": mask_content_sha256,
                "binary_masks": binary_masks,
                "image_gt_ink_iou": image_gt_ink_iou,
                "duplicate_group_id": "",
                "duplicate_group_size": 1,
                "canonical_sample_id": "",
                "is_duplicate_canonical": True,
                "hard_exclusion_reasons": hard_reasons,
            }
        )
    return audited


def _annotate_exact_duplicates(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    groups: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        image_hash = str(row["image_pixel_sha256"])
        mask_hash = str(row["mask_content_sha256"])
        if image_hash and mask_hash:
            groups[(image_hash, mask_hash)].append(row)

    duplicate_members: dict[str, list[str]] = {}
    for key, members in sorted(groups.items()):
        if len(members) <= 1:
            continue
        ordered = sorted(members, key=lambda row: _sample_sort_key(str(row["sample_id"])))
        canonical = str(ordered[0]["sample_id"])
        group_digest = hashlib.sha256(":".join(key).encode("ascii")).hexdigest()[:12]
        group_id = f"DUP-{group_digest}"
        duplicate_members[group_id] = [str(row["sample_id"]) for row in ordered]
        for index, row in enumerate(ordered):
            row["duplicate_group_id"] = group_id
            row["duplicate_group_size"] = len(ordered)
            row["canonical_sample_id"] = canonical
            row["is_duplicate_canonical"] = index == 0
            if index > 0:
                row["hard_exclusion_reasons"].append("EXACT_DUPLICATE_NONCANONICAL")
    return duplicate_members


def _split_audit(
    split_rows: Sequence[Mapping[str, str]],
    audited_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    counts_before = Counter()
    counts_after = Counter()
    mismatch_counts = Counter()
    duplicate_counts = Counter()
    retained: list[dict[str, str]] = []
    duplicate_group_splits: defaultdict[str, set[str]] = defaultdict(set)
    for split_row in split_rows:
        sample_id = str(split_row["sample_id"]).strip()
        split = str(split_row["split"]).strip()
        counts_before[split] += 1
        audit = audited_by_id.get(sample_id)
        if audit is None:
            raise ValueError(f"split references a sample absent from the QC audit: {sample_id}")
        reasons = list(audit["hard_exclusion_reasons"])
        if any(str(reason).startswith("IMAGE_GT_MISMATCH") for reason in reasons):
            mismatch_counts[split] += 1
        if "EXACT_DUPLICATE_NONCANONICAL" in reasons:
            duplicate_counts[split] += 1
        group_id = str(audit["duplicate_group_id"])
        if group_id:
            duplicate_group_splits[group_id].add(split)
        if not reasons:
            retained.append(dict(split_row))
            counts_after[split] += 1

    cross_split_groups = {
        group_id: sorted(splits)
        for group_id, splits in duplicate_group_splits.items()
        if len(splits) > 1
    }
    return (
        {
            "counts_before": dict(counts_before),
            "counts_after": dict(counts_after),
            "mismatch_exclusions": dict(mismatch_counts),
            "duplicate_noncanonical_exclusions": dict(duplicate_counts),
            "cross_split_exact_duplicate_group_count": len(cross_split_groups),
            "cross_split_exact_duplicate_groups": cross_split_groups,
        },
        retained,
    )


def _split_report(
    rows: Sequence[Mapping[str, str]],
    *,
    split_csv: Path,
    source_split_sha256: str,
    exclusion_csv: Path,
) -> dict[str, Any]:
    split_names = ("train", "val", "test")
    characters = {
        split: {
            str(row.get("char_id", "")).strip()
            for row in rows
            if str(row.get("split", "")).strip() == split
        }
        for split in split_names
    }
    sample_ids = [str(row["sample_id"]).strip() for row in rows]
    overlaps = {
        "train_val": sorted(characters["train"] & characters["val"]),
        "train_test": sorted(characters["train"] & characters["test"]),
        "val_test": sorted(characters["val"] & characters["test"]),
    }
    return {
        "schema_version": QC_SCHEMA_VERSION,
        "qc_version": QC_VERSION,
        "split_type": "character_disjoint_qc_filtered",
        "source_character_assignment_sha256": source_split_sha256,
        "split_csv": split_csv.as_posix(),
        "split_sha256": sha256_file(split_csv),
        "qc_exclusions": exclusion_csv.as_posix(),
        "qc_exclusions_sha256": sha256_file(exclusion_csv),
        "actual_sample_counts": dict(
            Counter(str(row.get("split", "")).strip() for row in rows)
        ),
        "actual_character_counts": {
            split: len(characters[split]) for split in split_names
        },
        "characters": {
            split: sorted(characters[split], key=lambda value: int(value))
            for split in split_names
        },
        "character_overlap": overlaps,
        "assertions": {
            "train_val_character_overlap_zero": not overlaps["train_val"],
            "train_test_character_overlap_zero": not overlaps["train_test"],
            "val_test_character_overlap_zero": not overlaps["val_test"],
            "all_active_samples_assigned_once": len(sample_ids) == len(set(sample_ids)),
        },
        "freeze_policy": (
            "The original character assignment is immutable. This derived split only "
            "applies the frozen QC exclusion list and must not be regenerated in response "
            "to model results."
        ),
    }


def _portable_clean_manifest(
    manifest_rows: Sequence[Mapping[str, str]],
    *,
    clean_sample_ids: set[str],
    dataset_root: Path,
    project_root: Path,
) -> tuple[list[dict[str, str]], list[str]]:
    output: list[dict[str, str]] = []
    fieldnames = list(manifest_rows[0]) if manifest_rows else []
    for row in manifest_rows:
        sample_id = str(row["sample_id"]).strip()
        if sample_id not in clean_sample_ids:
            continue
        item = dict(row)
        char_id = str(item["char_id"]).strip()
        sample_index = str(item["sample_index"]).strip()
        sample_dir = dataset_root / char_id / sample_index
        item.update(
            {
                "data_version": "legacy_gt_qc_v1",
                "sample_dir": _portable_path(sample_dir, project_root),
                "image_path": _portable_path(sample_dir / "0.jpg", project_root),
                "stacked_mask_path": _portable_path(sample_dir / "0.npy", project_root),
                "has_all_masks": "true",
                "errors": "",
            }
        )
        for channel in CHANNELS:
            item[f"{channel}_path"] = _portable_path(
                sample_dir / MASK_FILENAMES[channel],
                project_root,
            )
        output.append(item)
    output.sort(key=lambda row: _sample_sort_key(row["sample_id"]))
    return output, fieldnames


def _report_markdown(report: Mapping[str, Any]) -> str:
    standard = report["splits"]["standard"]
    character = report["splits"]["character_disjoint"]
    return "\n".join(
        [
            "# Dataset QC Report V1",
            "",
            f"Generated: `{report['generated_at_utc']}`",
            "",
            "## Frozen decision",
            "",
            "- Recovered complete GT files: **840**.",
            f"- Source-image/GT mismatches excluded: **{report['mismatch_sample_count']}**.",
            (
                "- Exact image+mask duplicate non-canonical instances excluded: "
                f"**{report['duplicate_noncanonical_sample_count']}**."
            ),
            f"- QC-clean unique segmentation observations: **{report['clean_sample_count']}**.",
            "",
            "The 200 SegFormer reference-cache masks are model outputs and are prohibited as",
            "segmentation ground truth. No label is generated, repaired, or fabricated here.",
            "",
            "## Standard split",
            "",
            f"- Before QC: `{standard['counts_before']}`",
            f"- After QC: `{standard['counts_after']}`",
            f"- Mismatches by split: `{standard['mismatch_exclusions']}`",
            (
                "- Duplicate non-canonical instances by split: "
                f"`{standard['duplicate_noncanonical_exclusions']}`"
            ),
            (
                "- Cross-split exact duplicate groups: "
                f"**{standard['cross_split_exact_duplicate_group_count']}**"
            ),
            "",
            "## Character-disjoint split",
            "",
            f"- Before QC: `{character['counts_before']}`",
            f"- After QC: `{character['counts_after']}`",
            f"- Mismatches by split: `{character['mismatch_exclusions']}`",
            (
                "- Duplicate non-canonical instances by split: "
                f"`{character['duplicate_noncanonical_exclusions']}`"
            ),
            (
                "- Cross-split exact duplicate groups: "
                f"**{character['cross_split_exact_duplicate_group_count']}**"
            ),
            "",
            "The original character assignment and its frozen SHA-256 remain unchanged.",
            "QC is a predeclared exclusion layer applied after that assignment.",
            "",
            "## Training rule",
            "",
            "Task 1 and the character-disjoint benchmark must use the tracked QC-clean split",
            "files and the exact exclusion-list SHA-256 recorded in the JSON report.",
            "The preliminary July B2 release remains engineering evidence only.",
            "",
        ]
    )


def build_dataset_qc(
    manifest_path: str | Path,
    dataset_root: str | Path,
    standard_splits_path: str | Path,
    character_disjoint_splits_path: str | Path,
    output_dir: str | Path,
    *,
    mismatch_iou_threshold: float = DEFAULT_MISMATCH_IOU_THRESHOLD,
) -> dict[str, Any]:
    """Build the immutable QC exclusion layer and derived clean splits."""

    manifest = Path(manifest_path).resolve()
    root = Path(dataset_root).resolve()
    standard_splits = Path(standard_splits_path).resolve()
    character_splits = Path(character_disjoint_splits_path).resolve()
    output = Path(output_dir)
    project_root = Path.cwd().resolve()
    if not 0 < mismatch_iou_threshold < 1:
        raise ValueError("mismatch_iou_threshold must be between 0 and 1")

    manifest_rows = _read_csv(manifest)
    audited = _audit_complete_samples(
        manifest,
        root,
        mismatch_iou_threshold=mismatch_iou_threshold,
    )
    duplicate_groups = _annotate_exact_duplicates(audited)
    audited_by_id = {str(row["sample_id"]): row for row in audited}
    exclusions = [
        row
        for row in audited
        if row["hard_exclusion_reasons"]
    ]
    for row in audited:
        reasons = list(row.pop("hard_exclusion_reasons"))
        row["hard_exclusion_reasons"] = "|".join(reasons)
        row["decision"] = "EXCLUDE" if reasons else "KEEP"
        row["review_status"] = (
            "AUTO_HARD_EXCLUSION_PENDING_HUMAN_CONFIRMATION" if reasons else "AUTO_KEEP"
        )
        row["reviewer"] = ""
        row["review_date"] = ""

    # Rebuild lookups after serializing the reason list.
    audited_by_id = {str(row["sample_id"]): row for row in audited}
    standard_audit, standard_clean = _split_audit(
        _read_csv(standard_splits),
        {
            sample_id: {
                **row,
                "hard_exclusion_reasons": [
                    value
                    for value in str(row["hard_exclusion_reasons"]).split("|")
                    if value
                ],
            }
            for sample_id, row in audited_by_id.items()
        },
    )
    character_audit, character_clean = _split_audit(
        _read_csv(character_splits),
        {
            sample_id: {
                **row,
                "hard_exclusion_reasons": [
                    value
                    for value in str(row["hard_exclusion_reasons"]).split("|")
                    if value
                ],
            }
            for sample_id, row in audited_by_id.items()
        },
    )

    output.mkdir(parents=True, exist_ok=True)
    audit_path = output / "dataset_qc_audit_v1.csv"
    exclusions_path = output / "dataset_qc_exclusions_v1.csv"
    clean_manifest_path = output / "manifest_qc_v1.csv"
    standard_clean_path = output / "standard_splits_qc_v1.csv"
    character_clean_path = output / "character_disjoint_splits_qc_v1.csv"
    character_clean_report_path = (
        output / "character_disjoint_splits_qc_v1_report.json"
    )
    report_path = output / "dataset_qc_report_v1.json"
    markdown_path = output / "DATASET_QC_REPORT_V1.md"

    audit_fields = [
        "schema_version",
        "qc_version",
        "sample_id",
        "char_id",
        "sample_index",
        "image_relative_path",
        "stacked_mask_relative_path",
        "image_pixel_sha256",
        "mask_content_sha256",
        "binary_masks",
        "image_gt_ink_iou",
        "duplicate_group_id",
        "duplicate_group_size",
        "canonical_sample_id",
        "is_duplicate_canonical",
        "hard_exclusion_reasons",
        "decision",
        "review_status",
        "reviewer",
        "review_date",
    ]
    _write_csv(audit_path, audited, audit_fields)
    exclusion_ids = {str(row["sample_id"]) for row in exclusions}
    _write_csv(
        exclusions_path,
        [row for row in audited if str(row["sample_id"]) in exclusion_ids],
        audit_fields,
    )
    clean_manifest, manifest_fields = _portable_clean_manifest(
        manifest_rows,
        clean_sample_ids=set(audited_by_id) - exclusion_ids,
        dataset_root=root,
        project_root=project_root,
    )
    _write_csv(clean_manifest_path, clean_manifest, manifest_fields)
    if standard_clean:
        _write_csv(standard_clean_path, standard_clean, list(standard_clean[0]))
    if character_clean:
        _write_csv(character_clean_path, character_clean, list(character_clean[0]))
    character_clean_report = _split_report(
        character_clean,
        split_csv=character_clean_path,
        source_split_sha256=sha256_file(character_splits),
        exclusion_csv=exclusions_path,
    )
    character_clean_report_path.write_text(
        json.dumps(character_clean_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    mismatch_ids = [
        str(row["sample_id"])
        for row in audited
        if "IMAGE_GT_MISMATCH" in str(row["hard_exclusion_reasons"])
    ]
    duplicate_noncanonical_ids = [
        str(row["sample_id"])
        for row in audited
        if "EXACT_DUPLICATE_NONCANONICAL" in str(row["hard_exclusion_reasons"])
    ]
    report: dict[str, Any] = {
        "schema_version": QC_SCHEMA_VERSION,
        "qc_version": QC_VERSION,
        "generated_at_utc": utc_now_iso(),
        "decision_policy": (
            "Exclude only explicit source-image/GT mismatches below the frozen IoU "
            "threshold and non-canonical members of exact image+mask duplicate groups."
        ),
        "mismatch_iou_threshold": mismatch_iou_threshold,
        "complete_gt_sample_count": len(audited),
        "mismatch_sample_count": len(mismatch_ids),
        "mismatch_sample_ids": mismatch_ids,
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_group_size_distribution": dict(
            sorted(Counter(len(values) for values in duplicate_groups.values()).items())
        ),
        "duplicate_group_member_count": sum(len(values) for values in duplicate_groups.values()),
        "duplicate_noncanonical_sample_count": len(duplicate_noncanonical_ids),
        "duplicate_noncanonical_sample_ids": duplicate_noncanonical_ids,
        "mismatch_duplicate_overlap_count": len(
            set(mismatch_ids) & set(duplicate_noncanonical_ids)
        ),
        "clean_sample_count": len(audited) - len(exclusion_ids),
        "labels_generated_or_fabricated": False,
        "reference_cache_used_as_ground_truth": False,
        "inputs": {
            "manifest": _portable_path(manifest, project_root),
            "manifest_sha256": sha256_file(manifest),
            "dataset_root": _portable_path(root, project_root),
            "standard_splits": _portable_path(standard_splits, project_root),
            "standard_splits_sha256": sha256_file(standard_splits),
            "character_disjoint_splits": _portable_path(
                character_splits, project_root
            ),
            "character_disjoint_splits_sha256": sha256_file(character_splits),
        },
        "outputs": {
            "audit_csv": _portable_path(audit_path, project_root),
            "exclusions_csv": _portable_path(exclusions_path, project_root),
            "clean_manifest": _portable_path(clean_manifest_path, project_root),
            "standard_splits_qc": _portable_path(standard_clean_path, project_root),
            "character_disjoint_splits_qc": _portable_path(
                character_clean_path, project_root
            ),
            "character_disjoint_splits_qc_report": _portable_path(
                character_clean_report_path, project_root
            ),
        },
        "splits": {
            "standard": standard_audit,
            "character_disjoint": character_audit,
        },
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report["outputs"].update(
        {
            "audit_csv_sha256": sha256_file(audit_path),
            "exclusions_csv_sha256": sha256_file(exclusions_path),
            "clean_manifest_sha256": sha256_file(clean_manifest_path),
            "standard_splits_qc_sha256": sha256_file(standard_clean_path),
            "character_disjoint_splits_qc_sha256": sha256_file(character_clean_path),
            "character_disjoint_splits_qc_report_sha256": sha256_file(
                character_clean_report_path
            ),
            "report_json": _portable_path(report_path, project_root),
        }
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(_report_markdown(report), encoding="utf-8")
    return report
