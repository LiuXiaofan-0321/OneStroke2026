"""Build an internal-review pool for natural same-character expert pairs.

This module deliberately stops before blinded evaluator packaging.  Its outputs
are candidate-only artifacts for the project team to inspect.  In particular,
it never creates ``frozen_expert_pairs_v1.csv`` and never treats the legacy
``sample_index`` as a writer identity.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import subprocess
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from onestroke_model.controlled_perturbations import PreparedReferenceScorer
from onestroke_model.structure_score_audit import (
    compute_score_components,
    score_v1_coverage_corrected,
    score_v1_current,
)

CANDIDATE_STATUS = "CANDIDATE_ONLY_DO_NOT_RATE"
FREEZE_STATUS = "NOT_FROZEN"
WRITER_IDENTITY_STATUS = "UNRECOVERABLE_FROM_AVAILABLE_EVIDENCE"
STYLE_ID = "unknown_legacy_collection"
STYLE_PROVENANCE_STATUS = "UNAVAILABLE"

# Character IDs 0-19 are named directly in stroke_vector_mapping.py.  IDs
# 20-39 are recovered from the ordered prompts in stroke_collector/lib/main.dart
# and cross-checked against the ordered stroke counts in the same mapping file.
LEGACY_CHARACTER_NAMES: dict[str, str] = {
    "0": "禾",
    "1": "汗",
    "2": "心",
    "3": "火",
    "4": "粒",
    "5": "梓",
    "6": "苦",
    "7": "头",
    "8": "手",
    "9": "划",
    "10": "水",
    "11": "李",
    "12": "云",
    "13": "冷",
    "14": "风",
    "15": "外",
    "16": "比",
    "17": "的",
    "18": "事",
    "19": "餐",
    "20": "卢",
    "21": "文",
    "22": "仃",
    "23": "杆",
    "24": "才",
    "25": "尽",
    "26": "半",
    "27": "何",
    "28": "亲",
    "29": "走",
    "30": "级",
    "31": "卖",
    "32": "废",
    "33": "鲦",
    "34": "氢",
    "35": "陈",
    "36": "畅",
    "37": "欢",
    "38": "尴",
    "39": "她",
}

PAIR_FIELDS = (
    "schema_version",
    "study_status",
    "freeze_status",
    "pair_id",
    "pair_type",
    "char_id",
    "target_char",
    "character_name_status",
    "candidate_instance_id",
    "reference_instance_id",
    "candidate_sample_index",
    "reference_sample_index",
    "candidate_image_path",
    "reference_image_path",
    "candidate_image_sha256",
    "reference_image_sha256",
    "candidate_mask_sha256",
    "reference_mask_sha256",
    "same_instance_detected",
    "same_image_detected",
    "same_mask_detected",
    "raw_image_foreground_dice",
    "raw_mask_macro_dice",
    "near_duplicate_suspected",
    "writer_id",
    "writer_identity_status",
    "different_writer_claim",
    "style_id",
    "style_provenance_status",
    "cross_style_design",
    "cross_style_verified",
    "current_score",
    "coverage_aware_score",
    "coverage_correction_points",
    "direction_macro_dice",
    "ink_iou",
    "keypoint_tolerant_f1_radius_3",
    "selected_scale",
    "selected_rotation_degrees",
    "selected_translation_x",
    "selected_translation_y",
    "alignment_ink_iou",
    "selection_seed",
    "pair_generation_policy",
)

REVIEW_FIELDS = (
    "study_status",
    "freeze_status",
    "selection_rank",
    "pair_id",
    "char_id",
    "target_char",
    "candidate_instance_id",
    "reference_instance_id",
    "current_score",
    "coverage_aware_score",
    "coverage_correction_points",
    "within_character_score_rank",
    "within_character_score_quantile",
    "score_bin_10pt",
    "review_sheet",
    "review_sheet_slot",
    "character_balance_ok",
    "score_range_ok",
    "same_instance_suspected",
    "writer_id_claim_ok",
    "cross_style_mislabel_suspected",
    "bad_image_suspected",
    "keep_for_freeze",
    "review_notes",
)


@dataclass
class SampleRecord:
    sample_id: str
    char_id: str
    target_char: str
    sample_index: int
    image_path: Path
    mask_path: Path
    image_array: np.ndarray | None
    masks: np.ndarray | None
    image_sha256: str
    image_pixel_sha256: str
    mask_sha256: str
    mask_content_sha256: str
    image_width: int
    image_height: int
    image_foreground_ratio: float
    ink_ratio: float
    image_mask_iou: float
    border_ink_fraction: float
    active_direction_count: int
    keypoint_pixels: int
    binary_masks: bool
    quality_flags: list[str]
    hard_exclusion_reasons: list[str]
    exact_duplicate_group_id: str = ""
    exact_duplicate_group_size: int = 1
    duplicate_canonical_sample_id: str = ""
    is_duplicate_canonical: bool = True

    @property
    def eligible(self) -> bool:
        return not self.hard_exclusion_reasons and self.is_duplicate_canonical


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
        fields = discovered or ("status",)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fields),
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def _stable_hash(seed: int, *values: str) -> str:
    payload = ":".join([str(seed), *values])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_array(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(value.shape).encode("ascii"))
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(value.tobytes())
    return digest.hexdigest()


def _as_binary_masks(value: np.ndarray) -> tuple[np.ndarray, bool]:
    array = np.asarray(value)
    if array.ndim != 3 or array.shape[-1] != 6:
        raise ValueError(f"expected [H,W,6] masks, got {array.shape}")
    unique = np.unique(array)
    binary = bool(np.all(np.isin(unique, [0, 1, 255])))
    return array > 0, binary


def _mask_iou(first: np.ndarray, second: np.ndarray) -> float:
    intersection = int(np.count_nonzero(first & second))
    union = int(np.count_nonzero(first | second))
    return 1.0 if union == 0 else float(intersection / union)


def _dice(first: np.ndarray, second: np.ndarray) -> float:
    denominator = int(np.count_nonzero(first)) + int(np.count_nonzero(second))
    if denominator == 0:
        return 1.0
    intersection = int(np.count_nonzero(first & second))
    return float(2.0 * intersection / denominator)


def _manifest_sample_path(
    dataset_root: Path,
    row: Mapping[str, str],
) -> tuple[Path, Path]:
    char_id = str(row["char_id"]).strip()
    sample_index = str(row["sample_index"]).strip()
    sample_dir = dataset_root / char_id / sample_index
    return sample_dir / "0.jpg", sample_dir / "0.npy"


def audit_samples(
    manifest_path: str | Path,
    dataset_root: str | Path,
    *,
    image_mask_iou_exclusion_threshold: float = 0.80,
) -> tuple[list[SampleRecord], list[dict[str, Any]], list[dict[str, Any]]]:
    """Audit complete GT samples and remove only explicit corruption/duplicates."""

    manifest = _read_csv(Path(manifest_path))
    root = Path(dataset_root).resolve()
    records: list[SampleRecord] = []
    for row in manifest:
        if str(row.get("has_all_masks", "")).strip().lower() != "true":
            continue
        char_id = str(row["char_id"]).strip()
        sample_id = str(row["sample_id"]).strip()
        image_path, mask_path = _manifest_sample_path(root, row)
        flags: list[str] = []
        exclusions: list[str] = []
        image_array: np.ndarray | None = None
        masks: np.ndarray | None = None
        image_sha256 = ""
        image_pixel_sha256 = ""
        mask_sha256 = ""
        mask_content_sha256 = ""
        image_width = 0
        image_height = 0
        image_foreground_ratio = math.nan
        ink_ratio = math.nan
        image_mask_iou = math.nan
        border_ink_fraction = math.nan
        active_direction_count = 0
        keypoint_pixels = 0
        binary_masks = False
        try:
            with Image.open(image_path) as image:
                grayscale = np.asarray(image.convert("L"))
            image_height, image_width = grayscale.shape
            image_array = grayscale
            image_sha256 = _sha256_file(image_path)
            image_pixel_sha256 = _sha256_array(grayscale)
        except (OSError, ValueError) as exc:
            exclusions.append(f"IMAGE_DECODE_ERROR:{type(exc).__name__}")
        try:
            raw_masks = np.load(mask_path, allow_pickle=False)
            masks, binary_masks = _as_binary_masks(raw_masks)
            mask_sha256 = _sha256_file(mask_path)
            mask_content_sha256 = _sha256_array(masks.astype(np.uint8))
            if not binary_masks:
                exclusions.append("NON_BINARY_MASK_VALUES")
        except (OSError, ValueError) as exc:
            exclusions.append(f"MASK_LOAD_ERROR:{type(exc).__name__}")

        if image_array is not None and masks is not None:
            if masks.shape[:2] != image_array.shape:
                exclusions.append("IMAGE_MASK_SHAPE_MISMATCH")
            else:
                image_foreground = image_array < 240
                direction_ink = np.any(masks[..., :5], axis=-1)
                image_foreground_ratio = float(np.mean(image_foreground))
                ink_ratio = float(np.mean(direction_ink))
                image_mask_iou = _mask_iou(image_foreground, direction_ink)
                ink_pixels = int(direction_ink.sum())
                border_pixels = int(
                    direction_ink[0, :].sum()
                    + direction_ink[-1, :].sum()
                    + direction_ink[:, 0].sum()
                    + direction_ink[:, -1].sum()
                )
                border_ink_fraction = float(border_pixels / max(1, ink_pixels))
                active_direction_count = int(
                    sum(bool(np.any(masks[..., index])) for index in range(5))
                )
                keypoint_pixels = int(masks[..., 5].sum())
                if not np.any(image_foreground):
                    exclusions.append("EMPTY_SOURCE_IMAGE")
                if ink_pixels == 0:
                    exclusions.append("EMPTY_DIRECTION_GT")
                if active_direction_count == 0:
                    exclusions.append("NO_ACTIVE_DIRECTION_CHANNEL")
                if keypoint_pixels == 0:
                    exclusions.append("EMPTY_KEYPOINT_GT")
                if image_mask_iou < image_mask_iou_exclusion_threshold:
                    exclusions.append(
                        f"IMAGE_GT_MISMATCH_IOU_LT_{image_mask_iou_exclusion_threshold:.2f}"
                    )
                if border_ink_fraction > 0.01:
                    exclusions.append("EXCESSIVE_CANVAS_BORDER_CLIPPING")
                if image_mask_iou < 0.95:
                    flags.append("LOW_IMAGE_GT_IOU_REVIEW")
                if ink_ratio < 0.02:
                    flags.append("LOW_INK_AREA_REVIEW")
                if ink_ratio > 0.22:
                    flags.append("HIGH_INK_AREA_REVIEW")
                if border_ink_fraction > 0:
                    flags.append("INK_TOUCHES_CANVAS_BORDER")
                if active_direction_count < 3:
                    flags.append("FEWER_THAN_THREE_ACTIVE_DIRECTIONS")

        records.append(
            SampleRecord(
                sample_id=sample_id,
                char_id=char_id,
                target_char=LEGACY_CHARACTER_NAMES.get(char_id, ""),
                sample_index=int(row["sample_index"]),
                image_path=image_path,
                mask_path=mask_path,
                image_array=image_array,
                masks=masks,
                image_sha256=image_sha256,
                image_pixel_sha256=image_pixel_sha256,
                mask_sha256=mask_sha256,
                mask_content_sha256=mask_content_sha256,
                image_width=image_width,
                image_height=image_height,
                image_foreground_ratio=image_foreground_ratio,
                ink_ratio=ink_ratio,
                image_mask_iou=image_mask_iou,
                border_ink_fraction=border_ink_fraction,
                active_direction_count=active_direction_count,
                keypoint_pixels=keypoint_pixels,
                binary_masks=binary_masks,
                quality_flags=flags,
                hard_exclusion_reasons=exclusions,
            )
        )

    duplicate_groups: defaultdict[tuple[str, str, str], list[SampleRecord]] = defaultdict(list)
    for record in records:
        if record.image_pixel_sha256 and record.mask_content_sha256:
            duplicate_groups[
                (
                    record.char_id,
                    record.image_pixel_sha256,
                    record.mask_content_sha256,
                )
            ].append(record)

    duplicate_rows: list[dict[str, Any]] = []
    for key, group in duplicate_groups.items():
        if len(group) <= 1:
            continue
        ordered = sorted(group, key=lambda item: (item.sample_index, item.sample_id))
        canonical = ordered[0]
        group_id = f"DUP-{hashlib.sha256(':'.join(key).encode('utf-8')).hexdigest()[:12]}"
        for record in ordered:
            record.exact_duplicate_group_id = group_id
            record.exact_duplicate_group_size = len(ordered)
            record.duplicate_canonical_sample_id = canonical.sample_id
            record.is_duplicate_canonical = record.sample_id == canonical.sample_id
            if not record.is_duplicate_canonical:
                record.quality_flags.append("EXACT_DUPLICATE_NONCANONICAL")
            duplicate_rows.append(
                {
                    "schema_version": 1,
                    "study_status": CANDIDATE_STATUS,
                    "duplicate_group_id": group_id,
                    "char_id": record.char_id,
                    "target_char": record.target_char,
                    "sample_id": record.sample_id,
                    "sample_index": record.sample_index,
                    "canonical_sample_id": canonical.sample_id,
                    "group_size": len(ordered),
                    "image_pixel_sha256": record.image_pixel_sha256,
                    "mask_content_sha256": record.mask_content_sha256,
                    "action": (
                        "KEEP_CANONICAL"
                        if record.is_duplicate_canonical
                        else "EXCLUDE_FROM_PAIR_POOL"
                    ),
                }
            )

    quality_rows = [
        {
            "schema_version": 1,
            "study_status": CANDIDATE_STATUS,
            "sample_id": record.sample_id,
            "instance_id": record.sample_id,
            "char_id": record.char_id,
            "target_char": record.target_char,
            "character_name_status": (
                "RECOVERED_FROM_LEGACY_CODE"
                if record.target_char
                else "UNKNOWN"
            ),
            "sample_index": record.sample_index,
            "writer_id": "",
            "writer_identity_status": WRITER_IDENTITY_STATUS,
            "source_id": "",
            "style_id": STYLE_ID,
            "style_provenance_status": STYLE_PROVENANCE_STATUS,
            "image_path": str(record.image_path),
            "mask_path": str(record.mask_path),
            "image_width": record.image_width,
            "image_height": record.image_height,
            "image_sha256": record.image_sha256,
            "image_pixel_sha256": record.image_pixel_sha256,
            "stacked_mask_sha256": record.mask_sha256,
            "mask_content_sha256": record.mask_content_sha256,
            "binary_masks": record.binary_masks,
            "image_foreground_ratio": record.image_foreground_ratio,
            "direction_ink_ratio": record.ink_ratio,
            "image_gt_ink_iou": record.image_mask_iou,
            "border_ink_fraction": record.border_ink_fraction,
            "active_direction_count": record.active_direction_count,
            "keypoint_pixels": record.keypoint_pixels,
            "exact_duplicate_group_id": record.exact_duplicate_group_id,
            "exact_duplicate_group_size": record.exact_duplicate_group_size,
            "duplicate_canonical_sample_id": record.duplicate_canonical_sample_id,
            "is_duplicate_canonical": record.is_duplicate_canonical,
            "quality_flags": "|".join(record.quality_flags),
            "hard_exclusion_reasons": "|".join(record.hard_exclusion_reasons),
            "eligible_for_pair_pool": record.eligible,
        }
        for record in sorted(
            records,
            key=lambda item: (int(item.char_id), item.sample_index),
        )
    ]
    return records, quality_rows, duplicate_rows


def construct_balanced_pairs(
    samples: Sequence[Mapping[str, Any]],
    *,
    pairs_per_character: int = 10,
    seed: int = 20260812,
) -> list[dict[str, Any]]:
    """Create score-independent, role-fixed pairs with controlled sample reuse."""

    by_character: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in samples:
        if not bool(row.get("eligible", True)):
            continue
        by_character[str(row["char_id"])].append(dict(row))
    pairs: list[dict[str, Any]] = []
    for char_id in sorted(by_character, key=int):
        rows = sorted(
            by_character[char_id],
            key=lambda row: _stable_hash(seed, "sample-order", str(row["sample_id"])),
        )
        if len(rows) < 2:
            raise ValueError(f"character {char_id} has fewer than two eligible instances")
        anchor_count = min(
            max(1, math.ceil(pairs_per_character / 2)),
            len(rows) - 1,
        )
        anchors = rows[:anchor_count]
        candidates = rows[anchor_count:]
        if not candidates:
            candidates = rows[1:]
        seen_unordered: set[tuple[str, str]] = set()
        usage: Counter[str] = Counter()
        for index in range(pairs_per_character):
            ranked: list[tuple[tuple[int, int, str], dict[str, Any], dict[str, Any]]] = []
            for anchor in anchors:
                for candidate in candidates:
                    first = str(anchor["sample_id"])
                    second = str(candidate["sample_id"])
                    if first == second:
                        continue
                    unordered = tuple(sorted((first, second)))
                    if unordered in seen_unordered:
                        continue
                    rank = (
                        max(usage[first], usage[second]),
                        usage[first] + usage[second],
                        _stable_hash(seed, "pair-order", char_id, *unordered),
                    )
                    ranked.append((rank, candidate, anchor))
            if not ranked:
                raise ValueError(
                    f"character {char_id} cannot supply {pairs_per_character} unique pairs"
                )
            _, candidate, reference = min(ranked, key=lambda item: item[0])
            candidate_id = str(candidate["sample_id"])
            reference_id = str(reference["sample_id"])
            unordered = tuple(sorted((candidate_id, reference_id)))
            seen_unordered.add(unordered)
            usage[candidate_id] += 1
            usage[reference_id] += 1
            pair_id = (
                "NAT-"
                + char_id.zfill(2)
                + "-"
                + _stable_hash(seed, "natural-pair", char_id, *unordered)[:12]
            )
            pairs.append(
                {
                    "pair_id": pair_id,
                    "char_id": char_id,
                    "candidate_sample_id": candidate_id,
                    "reference_sample_id": reference_id,
                    "selection_seed": seed,
                    "pair_generation_policy": (
                        "score-independent balanced anchor/candidate pairing; "
                        "fixed candidate/reference roles"
                    ),
                }
            )
    return pairs


def _score_pair(
    pair: Mapping[str, Any],
    sample_lookup: Mapping[str, SampleRecord],
    scorer_cache: dict[str, PreparedReferenceScorer],
    dataset_root: Path,
) -> dict[str, Any]:
    candidate = sample_lookup[str(pair["candidate_sample_id"])]
    reference = sample_lookup[str(pair["reference_sample_id"])]
    if candidate.sample_id == reference.sample_id:
        raise ValueError(f"self pair is forbidden: {pair!r}")
    if candidate.char_id != reference.char_id:
        raise ValueError(f"cross-character pair is forbidden: {pair!r}")
    same_image = candidate.image_pixel_sha256 == reference.image_pixel_sha256
    same_mask = candidate.mask_content_sha256 == reference.mask_content_sha256
    if same_image or same_mask:
        raise ValueError(f"duplicate instance entered pair pool: {pair!r}")
    if candidate.masks is None or reference.masks is None:
        raise ValueError(f"eligible pair contains unloaded masks: {pair!r}")
    if candidate.image_array is None or reference.image_array is None:
        raise ValueError(f"eligible pair contains unloaded source images: {pair!r}")
    raw_image_foreground_dice = _dice(
        candidate.image_array < 240,
        reference.image_array < 240,
    )
    raw_mask_macro_dice = float(
        np.mean(
            [
                _dice(
                    candidate.masks[..., channel],
                    reference.masks[..., channel],
                )
                for channel in range(6)
            ]
        )
    )
    near_duplicate_suspected = bool(
        raw_image_foreground_dice >= 0.995
        and raw_mask_macro_dice >= 0.995
    )
    scorer = scorer_cache.get(reference.sample_id)
    if scorer is None:
        scorer = PreparedReferenceScorer(reference.masks)
        scorer_cache[reference.sample_id] = scorer
    evidence, aligned_reference = scorer.score(candidate.masks)
    components = compute_score_components(
        candidate.masks,
        aligned_reference,
        source_reference_masks=reference.masks,
    )
    current_score = score_v1_current(components)
    if not math.isclose(
        current_score,
        float(evidence["prototype_structure_score"]),
        rel_tol=0,
        abs_tol=1e-9,
    ):
        raise RuntimeError("production score and decomposed current score diverged")
    coverage_score = score_v1_coverage_corrected(components)
    transform = evidence["selected_transform"]
    return {
        "schema_version": 1,
        "study_status": CANDIDATE_STATUS,
        "freeze_status": FREEZE_STATUS,
        "pair_id": pair["pair_id"],
        "pair_type": "same_character_different_instance_natural_gt",
        "char_id": candidate.char_id,
        "target_char": candidate.target_char,
        "character_name_status": "RECOVERED_FROM_LEGACY_CODE",
        "candidate_instance_id": candidate.sample_id,
        "reference_instance_id": reference.sample_id,
        "candidate_sample_index": candidate.sample_index,
        "reference_sample_index": reference.sample_index,
        "candidate_image_path": str(candidate.image_path.relative_to(dataset_root.parent.parent)),
        "reference_image_path": str(reference.image_path.relative_to(dataset_root.parent.parent)),
        "candidate_image_sha256": candidate.image_pixel_sha256,
        "reference_image_sha256": reference.image_pixel_sha256,
        "candidate_mask_sha256": candidate.mask_content_sha256,
        "reference_mask_sha256": reference.mask_content_sha256,
        "same_instance_detected": False,
        "same_image_detected": same_image,
        "same_mask_detected": same_mask,
        "raw_image_foreground_dice": raw_image_foreground_dice,
        "raw_mask_macro_dice": raw_mask_macro_dice,
        "near_duplicate_suspected": near_duplicate_suspected,
        "writer_id": "",
        "writer_identity_status": WRITER_IDENTITY_STATUS,
        "different_writer_claim": False,
        "style_id": STYLE_ID,
        "style_provenance_status": STYLE_PROVENANCE_STATUS,
        "cross_style_design": False,
        "cross_style_verified": False,
        "current_score": float(current_score),
        "coverage_aware_score": float(coverage_score),
        "coverage_correction_points": float(coverage_score - current_score),
        "direction_macro_dice": float(evidence["direction_macro_dice"]),
        "ink_iou": float(evidence["ink_iou"]),
        "keypoint_tolerant_f1_radius_3": float(
            evidence["keypoint_tolerant_f1_radius_3"]
        ),
        "selected_scale": float(transform["scale"]),
        "selected_rotation_degrees": float(transform["rotation_degrees"]),
        "selected_translation_x": float(transform["translation_x"]),
        "selected_translation_y": float(transform["translation_y"]),
        "alignment_ink_iou": float(transform["alignment_ink_iou"]),
        "selection_seed": pair["selection_seed"],
        "pair_generation_policy": pair["pair_generation_policy"],
    }


def score_natural_pairs(
    pairs: Sequence[Mapping[str, Any]],
    records: Sequence[SampleRecord],
    dataset_root: str | Path,
) -> list[dict[str, Any]]:
    lookup = {record.sample_id: record for record in records if record.eligible}
    scorer_cache: dict[str, PreparedReferenceScorer] = {}
    scored: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs, start=1):
        scored.append(
            _score_pair(pair, lookup, scorer_cache, Path(dataset_root).resolve())
        )
        if index % 50 == 0:
            print(f"scored_pairs={index}/{len(pairs)}")
    return scored


def select_internal_review_pairs(
    scored_pairs: Sequence[Mapping[str, Any]],
    *,
    target_pairs: int = 150,
    three_pair_character_count: int = 10,
    seed: int = 20260812,
) -> list[dict[str, Any]]:
    """Select 3-4 score-stratified pairs per character for internal review."""

    by_character: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored_pairs:
        by_character[str(row["char_id"])].append(dict(row))
    character_ids = sorted(by_character, key=int)
    if target_pairs != (
        len(character_ids) * 4 - three_pair_character_count
    ):
        raise ValueError(
            "target_pairs must match four per character minus "
            "three_pair_character_count"
        )
    three_pair_characters = set(
        sorted(
            character_ids,
            key=lambda char_id: _stable_hash(
                seed,
                "three-pair-character",
                char_id,
            ),
        )[:three_pair_character_count]
    )
    selected: list[dict[str, Any]] = []
    for char_id in character_ids:
        ordered = sorted(
            by_character[char_id],
            key=lambda row: (float(row["current_score"]), str(row["pair_id"])),
        )
        count = 3 if char_id in three_pair_characters else 4
        target_ranks = (
            [0, (len(ordered) - 1) // 2, len(ordered) - 1]
            if count == 3
            else [
                0,
                round((len(ordered) - 1) / 3),
                round(2 * (len(ordered) - 1) / 3),
                len(ordered) - 1,
            ]
        )
        used: set[int] = set()
        for rank in target_ranks:
            if rank in used:
                alternatives = [
                    index
                    for index in range(len(ordered))
                    if index not in used
                ]
                rank = min(alternatives, key=lambda value: abs(value - rank))
            used.add(rank)
            row = dict(ordered[rank])
            row["within_character_score_rank"] = rank + 1
            row["within_character_score_quantile"] = (
                rank / max(1, len(ordered) - 1)
            )
            selected.append(row)
    selected.sort(
        key=lambda row: (
            int(row["char_id"]),
            int(row["within_character_score_rank"]),
        )
    )
    if len(selected) != target_pairs:
        raise RuntimeError(f"selected {len(selected)} pairs, expected {target_pairs}")
    for index, row in enumerate(selected, start=1):
        row["selection_rank"] = index
        row["score_bin_10pt"] = min(9, int(float(row["current_score"]) // 10))
    return selected


def _summary(values: Sequence[float]) -> dict[str, float | int | None]:
    finite = np.asarray([value for value in values if math.isfinite(value)], dtype=float)
    if len(finite) == 0:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "p05": None,
            "p95": None,
            "max": None,
        }
    return {
        "n": int(len(finite)),
        "mean": float(np.mean(finite)),
        "median": float(np.median(finite)),
        "std": float(np.std(finite, ddof=1)) if len(finite) > 1 else 0.0,
        "min": float(np.min(finite)),
        "p05": float(np.quantile(finite, 0.05)),
        "p95": float(np.quantile(finite, 0.95)),
        "max": float(np.max(finite)),
    }


def build_score_distribution(
    candidates: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    distribution_rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    for scope, rows in (("candidate_400", candidates), ("selection_150", selected)):
        summary[scope] = {
            "current_score": _summary(
                [float(row["current_score"]) for row in rows]
            ),
            "coverage_aware_score": _summary(
                [float(row["coverage_aware_score"]) for row in rows]
            ),
            "coverage_correction_points": _summary(
                [float(row["coverage_correction_points"]) for row in rows]
            ),
        }
        for bin_index in range(10):
            lower = bin_index * 10
            upper = 100 if bin_index == 9 else (bin_index + 1) * 10
            subset = [
                row
                for row in rows
                if lower <= float(row["current_score"])
                and (
                    float(row["current_score"]) <= upper
                    if bin_index == 9
                    else float(row["current_score"]) < upper
                )
            ]
            distribution_rows.append(
                {
                    "scope": scope,
                    "score_variant": "current_score",
                    "bin_index": bin_index,
                    "bin_lower_inclusive": lower,
                    "bin_upper": upper,
                    "upper_inclusive": bin_index == 9,
                    "count": len(subset),
                    "fraction": len(subset) / max(1, len(rows)),
                }
            )
    return distribution_rows, summary


def build_per_character_summary(
    records: Sequence[SampleRecord],
    candidates: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_records: defaultdict[str, list[SampleRecord]] = defaultdict(list)
    by_candidates: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_selected: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        by_records[record.char_id].append(record)
    for row in candidates:
        by_candidates[str(row["char_id"])].append(row)
    for row in selected:
        by_selected[str(row["char_id"])].append(row)
    rows: list[dict[str, Any]] = []
    for char_id in sorted(by_records, key=int):
        source = by_records[char_id]
        pair_rows = by_candidates[char_id]
        selected_rows = by_selected[char_id]
        endpoint_counts: Counter[str] = Counter()
        for pair in pair_rows:
            endpoint_counts[str(pair["candidate_instance_id"])] += 1
            endpoint_counts[str(pair["reference_instance_id"])] += 1
        scores = [float(row["current_score"]) for row in pair_rows]
        rows.append(
            {
                "char_id": char_id,
                "target_char": LEGACY_CHARACTER_NAMES.get(char_id, ""),
                "complete_gt_instances": len(source),
                "quality_excluded_instances": sum(
                    bool(item.hard_exclusion_reasons) for item in source
                ),
                "duplicate_noncanonical_instances": sum(
                    not item.is_duplicate_canonical for item in source
                ),
                "eligible_unique_instances": sum(item.eligible for item in source),
                "candidate_pair_count": len(pair_rows),
                "selected_pair_count": len(selected_rows),
                "candidate_current_score_min": min(scores) if scores else None,
                "candidate_current_score_median": (
                    statistics.median(scores) if scores else None
                ),
                "candidate_current_score_max": max(scores) if scores else None,
                "max_instance_pair_usage": max(endpoint_counts.values(), default=0),
                "writer_id_status": WRITER_IDENTITY_STATUS,
                "style_provenance_status": STYLE_PROVENANCE_STATUS,
            }
        )
    return rows


def _font(size: int) -> ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def render_review_sheets(
    selected: list[dict[str, Any]],
    sample_lookup: Mapping[str, SampleRecord],
    output_dir: str | Path,
    *,
    pairs_per_sheet: int = 20,
) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    title_font = _font(22)
    text_font = _font(17)
    small_font = _font(14)
    cell_width, cell_height = 470, 250
    columns, rows_per_page = 4, 5
    if pairs_per_sheet != columns * rows_per_page:
        raise ValueError("current review-sheet layout requires 20 pairs per sheet")
    paths: list[Path] = []
    for page_index, start in enumerate(range(0, len(selected), pairs_per_sheet), start=1):
        page_rows = selected[start : start + pairs_per_sheet]
        canvas = Image.new(
            "RGB",
            (columns * cell_width, 52 + rows_per_page * cell_height),
            "white",
        )
        draw = ImageDraw.Draw(canvas)
        draw.text(
            (18, 12),
            (
                f"Internal review only | {CANDIDATE_STATUS} | "
                f"sheet {page_index:02d}"
            ),
            fill=(150, 0, 0),
            font=title_font,
        )
        for slot, row in enumerate(page_rows, start=1):
            local_index = slot - 1
            column = local_index % columns
            grid_row = local_index // columns
            left = column * cell_width
            top = 52 + grid_row * cell_height
            draw.rectangle(
                (left, top, left + cell_width - 1, top + cell_height - 1),
                outline=(180, 180, 180),
                width=1,
            )
            candidate = sample_lookup[str(row["candidate_instance_id"])]
            reference = sample_lookup[str(row["reference_instance_id"])]
            if candidate.image_array is None or reference.image_array is None:
                raise ValueError("selected review pair contains an unreadable image")
            candidate_image = Image.fromarray(candidate.image_array).convert("RGB")
            reference_image = Image.fromarray(reference.image_array).convert("RGB")
            candidate_image.thumbnail((165, 165), Image.Resampling.LANCZOS)
            reference_image.thumbnail((165, 165), Image.Resampling.LANCZOS)
            canvas.paste(candidate_image, (left + 18, top + 45))
            canvas.paste(reference_image, (left + 212, top + 45))
            draw.text(
                (left + 10, top + 8),
                (
                    f"{start + slot:03d}  char_id={row['char_id']} "
                    f"({row['target_char']})"
                ),
                fill="black",
                font=text_font,
            )
            draw.text(
                (left + 18, top + 215),
                f"C {candidate.sample_id}",
                fill=(0, 70, 150),
                font=small_font,
            )
            draw.text(
                (left + 212, top + 215),
                f"R {reference.sample_id}",
                fill=(100, 60, 0),
                font=small_font,
            )
            draw.text(
                (left + 18, top + 232),
                (
                    f"current={float(row['current_score']):.2f}  "
                    f"coverage={float(row['coverage_aware_score']):.2f}"
                ),
                fill=(30, 30, 30),
                font=small_font,
            )
            row["review_sheet"] = f"review_sheet_{page_index:02d}.png"
            row["review_sheet_slot"] = slot
        path = output / f"review_sheet_{page_index:02d}.png"
        canvas.save(path)
        paths.append(path)
    return paths


def render_quality_exclusion_sheet(
    records: Sequence[SampleRecord],
    output_path: str | Path,
) -> Path | None:
    excluded = sorted(
        (record for record in records if record.hard_exclusion_reasons),
        key=lambda item: (int(item.char_id), item.sample_index),
    )
    if not excluded:
        return None
    cell_width, cell_height = 580, 260
    columns = 3
    rows = math.ceil(len(excluded) / columns)
    canvas = Image.new("RGB", (columns * cell_width, 55 + rows * cell_height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (18, 12),
        "Quality exclusions: source image (left) vs six-channel GT ink overlay (right)",
        fill=(150, 0, 0),
        font=_font(21),
    )
    text_font = _font(16)
    small_font = _font(13)
    for index, record in enumerate(excluded):
        column = index % columns
        row = index // columns
        left = column * cell_width
        top = 55 + row * cell_height
        draw.rectangle(
            (left, top, left + cell_width - 1, top + cell_height - 1),
            outline=(180, 180, 180),
            width=1,
        )
        if record.image_array is None or record.masks is None:
            draw.text(
                (left + 12, top + 55),
                "Unreadable image or mask",
                fill=(170, 0, 0),
                font=text_font,
            )
            continue
        source = Image.fromarray(record.image_array).convert("RGB")
        source.thumbnail((205, 205), Image.Resampling.LANCZOS)
        direction_ink = np.any(record.masks[..., :5], axis=-1)
        overlay = np.full((*direction_ink.shape, 3), 255, dtype=np.uint8)
        overlay[direction_ink] = (20, 80, 220)
        overlay_image = Image.fromarray(overlay)
        overlay_image.thumbnail((205, 205), Image.Resampling.NEAREST)
        canvas.paste(source, (left + 15, top + 38))
        canvas.paste(overlay_image, (left + 250, top + 38))
        draw.text(
            (left + 12, top + 8),
            (
                f"{record.sample_id} ({record.target_char}) "
                f"image/GT IoU={record.image_mask_iou:.3f}"
            ),
            fill="black",
            font=text_font,
        )
        draw.text(
            (left + 12, top + 240),
            "|".join(record.hard_exclusion_reasons),
            fill=(145, 0, 0),
            font=small_font,
        )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)
    return path


def _legacy_git_show(git_dir: Path, object_path: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", f"--git-dir={git_dir}", "show", f"HEAD:{object_path}"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout


def build_writer_forensics(
    manifest_path: str | Path,
    *,
    dataset_root: str | Path | None = None,
    legacy_git_dir: str | Path | None = None,
) -> dict[str, Any]:
    rows = _read_csv(Path(manifest_path))
    complete = [
        row
        for row in rows
        if str(row.get("has_all_masks", "")).strip().lower() == "true"
    ]
    nonempty_writers = sorted(
        {
            str(row.get("writer_id", "")).strip()
            for row in complete
            if str(row.get("writer_id", "")).strip()
        }
    )
    nonempty_sources = sorted(
        {
            str(row.get("source_id", "")).strip()
            for row in complete
            if str(row.get("source_id", "")).strip()
        }
    )
    evidence: list[dict[str, Any]] = [
        {
            "source": str(Path(manifest_path).resolve()),
            "finding": "All complete recovered rows have empty writer_id and source_id.",
            "writer_values": len(nonempty_writers),
            "source_values": len(nonempty_sources),
        }
    ]
    image_metadata_scan: dict[str, Any] | None = None
    if dataset_root is not None:
        root = Path(dataset_root)
        scanned = 0
        decode_errors = 0
        exif_images = 0
        exif_identity_fields: list[dict[str, Any]] = []
        metadata_key_counts: Counter[str] = Counter()
        identity_tokens = (
            "artist",
            "author",
            "creator",
            "owner",
            "user",
            "writer",
            "person",
            "name",
        )
        for row in complete:
            image_path, _ = _manifest_sample_path(root, row)
            try:
                with Image.open(image_path) as image:
                    scanned += 1
                    exif = image.getexif()
                    if exif:
                        exif_images += 1
                    for key in image.info:
                        metadata_key_counts[str(key)] += 1
                    for key, value in exif.items():
                        rendered = f"{key}:{value}"
                        if any(token in rendered.lower() for token in identity_tokens):
                            exif_identity_fields.append(
                                {
                                    "sample_id": row["sample_id"],
                                    "key": str(key),
                                    "value": str(value),
                                }
                            )
            except OSError:
                decode_errors += 1
        image_metadata_scan = {
            "images_scanned": scanned,
            "decode_errors": decode_errors,
            "images_with_exif": exif_images,
            "identity_like_exif_fields": exif_identity_fields,
            "image_info_key_counts": dict(sorted(metadata_key_counts.items())),
        }
        evidence.append(
            {
                "source": str(root.resolve()),
                "finding": (
                    f"Scanned {scanned} complete-sample JPEG files: "
                    f"{exif_images} contained EXIF and "
                    f"{len(exif_identity_fields)} identity-like EXIF fields were found. "
                    "Container metadata such as JFIF/DPI does not identify a writer."
                ),
            }
        )
    collector_has_identity = None
    filter_uses_directory_count = None
    if legacy_git_dir is not None and Path(legacy_git_dir).is_dir():
        git_dir = Path(legacy_git_dir)
        collector = _legacy_git_show(git_dir, "stroke_collector/lib/main.dart")
        filter_code = _legacy_git_show(git_dir, "StrokeSegmentation/data/filter.py")
        tool_code = _legacy_git_show(git_dir, "StrokeSegmentation/data/tools/tool.py")
        if collector is not None:
            collector_has_identity = any(
                token in collector
                for token in (
                    "writer_id",
                    "writerId",
                    "user_id",
                    "userId",
                    "participant_id",
                )
            )
            evidence.append(
                {
                    "source": "legacy_git:stroke_collector/lib/main.dart",
                    "finding": (
                        "Image export uses ImageGallerySaver.saveImage; no explicit "
                        "writer/user/participant identity field was found."
                    ),
                    "identity_token_found": collector_has_identity,
                }
            )
        if filter_code is not None and tool_code is not None:
            filter_uses_directory_count = (
                "get_directory_count" in filter_code
                and "def get_directory_count" in tool_code
            )
            evidence.append(
                {
                    "source": (
                        "legacy_git:StrokeSegmentation/data/filter.py and "
                        "data/tools/tool.py"
                    ),
                    "finding": (
                        "Instance directories are assigned from the current "
                        "directory count, which is an ordinal storage index rather "
                        "than a recorded writer identity."
                    ),
                    "directory_count_assignment_confirmed": filter_uses_directory_count,
                }
            )
    return {
        "schema_version": 1,
        "study_status": CANDIDATE_STATUS,
        "conclusion": WRITER_IDENTITY_STATUS,
        "writer_id_recoverable": False,
        "source_id_recoverable": False,
        "sample_index_is_writer_id": False,
        "sample_index_allowed_label": "instance ordinal / grouping proxy only",
        "different_writer_claim_allowed": False,
        "unseen_writer_claim_allowed": False,
        "complete_sample_count": len(complete),
        "nonempty_writer_id_count": len(nonempty_writers),
        "nonempty_source_id_count": len(nonempty_sources),
        "legacy_collector_identity_token_found": collector_has_identity,
        "legacy_filter_directory_count_assignment_confirmed": filter_uses_directory_count,
        "image_metadata_scan": image_metadata_scan,
        "evidence": evidence,
        "required_human_follow_up": (
            "Ask the original collectors whether an external roster maps acquisition "
            "batches or image ranges to participants.  Do not infer this mapping from "
            "sample_index."
        ),
    }


def write_writer_forensics(
    output_dir: str | Path,
    report: Mapping[str, Any],
) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "writer_identity_forensics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Writer identity forensics",
        "",
        f"Status: `{CANDIDATE_STATUS}`.",
        "",
        "## Conclusion",
        "",
        f"`{WRITER_IDENTITY_STATUS}`.",
        "",
        "The recovered 840 complete GT samples do not contain a trustworthy writer ID. "
        "`sample_index` is an instance/storage ordinal and must not be relabeled as a "
        "writer. Therefore this study may claim **same-character different-instance** "
        "pairs only; it may not claim different-writer or unseen-writer pairs.",
        "",
        "## Evidence",
        "",
    ]
    for item in report["evidence"]:
        lines.append(f"- `{item['source']}`: {item['finding']}")
    lines.extend(
        [
            "",
            "## Human follow-up",
            "",
            str(report["required_human_follow_up"]),
            "",
            "Until external acquisition records are supplied and verified, all pair "
            "tables keep `writer_id` empty and set "
            f"`writer_identity_status={WRITER_IDENTITY_STATUS}`.",
            "",
        ]
    )
    (output / "writer_identity_forensics.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _review_rows(selected: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "study_status": CANDIDATE_STATUS,
            "freeze_status": FREEZE_STATUS,
            "selection_rank": row["selection_rank"],
            "pair_id": row["pair_id"],
            "char_id": row["char_id"],
            "target_char": row["target_char"],
            "candidate_instance_id": row["candidate_instance_id"],
            "reference_instance_id": row["reference_instance_id"],
            "current_score": row["current_score"],
            "coverage_aware_score": row["coverage_aware_score"],
            "coverage_correction_points": row["coverage_correction_points"],
            "within_character_score_rank": row["within_character_score_rank"],
            "within_character_score_quantile": row[
                "within_character_score_quantile"
            ],
            "score_bin_10pt": row["score_bin_10pt"],
            "review_sheet": row.get("review_sheet", ""),
            "review_sheet_slot": row.get("review_sheet_slot", ""),
            "character_balance_ok": "",
            "score_range_ok": "",
            "same_instance_suspected": "",
            "writer_id_claim_ok": "",
            "cross_style_mislabel_suspected": "",
            "bad_image_suspected": "",
            "keep_for_freeze": "",
            "review_notes": "",
        }
        for row in selected
    ]


def write_candidate_review_report(
    output_dir: str | Path,
    *,
    records: Sequence[SampleRecord],
    candidates: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
    per_character: Sequence[Mapping[str, Any]],
    score_summary: Mapping[str, Any],
    writer_forensics: Mapping[str, Any],
    review_sheets: Sequence[Path],
    seed: int,
) -> None:
    output = Path(output_dir)
    hard_quality = [
        record for record in records if bool(record.hard_exclusion_reasons)
    ]
    duplicate_noncanonical = [
        record for record in records if not record.is_duplicate_canonical
    ]
    candidate_stats = score_summary["candidate_400"]["current_score"]
    selection_stats = score_summary["selection_150"]["current_score"]
    selected_counts = Counter(str(row["char_id"]) for row in selected)
    selected_score_bins = Counter(int(row["score_bin_10pt"]) for row in selected)
    lines = [
        "# Expert pair candidate review report",
        "",
        f"Status: **{CANDIDATE_STATUS} / {FREEZE_STATUS}**.",
        "",
        "> These pairs are for internal inspection only. Do not send them to an "
        "evaluator. This run did not create `frozen_expert_pairs_v1.csv`.",
        "",
        "## What was built",
        "",
        f"- Complete recovered six-channel GT samples audited: **{len(records)}**.",
        f"- Obvious image/GT or file-quality exclusions: **{len(hard_quality)}**.",
        "- Exact duplicate non-canonical instances excluded: "
        f"**{len(duplicate_noncanonical)}**.",
        f"- Natural same-character candidate pairs: **{len(candidates)}**.",
        f"- Internal-review selection: **{len(selected)}**.",
        f"- Review contact sheets: **{len(review_sheets)}**.",
        f"- Deterministic seed: `{seed}`.",
        "",
        "The 200 SegFormer reference-cache images were not used as ground truth or as "
        "expert-pair sources.",
        "",
        "The automatic hard exclusion for image/GT mismatch uses source-foreground vs "
        "direction-GT ink IoU `< 0.80`. The excluded cases sit below a visible gap in "
        "the empirical distribution and are rendered in "
        "`quality_exclusions_source_vs_gt.png`; they should still receive a final "
        "team sanity check.",
        "",
        "## Identity and style limits",
        "",
        f"- Writer identity: `{writer_forensics['conclusion']}`.",
        "- `sample_index` remains an instance ordinal; it is not a writer ID.",
        "- Pair claim: same character, different non-duplicate instances.",
        f"- Style label: `{STYLE_ID}`; legacy style provenance is unavailable.",
        "- `cross_style_design=false` means the experiment was not designed as a "
        "cross-style comparison. It does not assert that both images have a verified "
        "shared style.",
        "",
        "## Pair construction",
        "",
        "- Exactly 10 score-independent candidate pairs were generated for each of 40 "
        "characters.",
        "- Candidate/reference roles were fixed before scoring.",
        "- Self-pairs, repeated unordered pairs, equal image hashes, and equal GT-mask "
        "hashes are forbidden.",
        "- Selected candidate pairs also expose raw source-image Dice and raw six-channel "
        "mask macro Dice. No generated candidate crossed the conservative "
        "`>=0.995` near-duplicate suspicion rule in this run.",
        "- Endpoint use is balanced within each character; see "
        "`per_character_summary.csv`.",
        "- The 150 review pairs were then stratified within character over low, middle, "
        "and high current-score ranks: 30 characters contribute 4 pairs and 10 "
        "characters contribute 3 pairs.",
        "",
        "## Score coverage",
        "",
        (
            "- Candidate current score: "
            f"N={candidate_stats['n']}, mean={candidate_stats['mean']:.3f}, "
            f"median={candidate_stats['median']:.3f}, "
            f"range=[{candidate_stats['min']:.3f}, {candidate_stats['max']:.3f}], "
            f"P05/P95={candidate_stats['p05']:.3f}/{candidate_stats['p95']:.3f}."
        ),
        (
            "- Selected current score: "
            f"N={selection_stats['n']}, mean={selection_stats['mean']:.3f}, "
            f"median={selection_stats['median']:.3f}, "
            f"range=[{selection_stats['min']:.3f}, {selection_stats['max']:.3f}], "
            f"P05/P95={selection_stats['p05']:.3f}/{selection_stats['p95']:.3f}."
        ),
        "",
        "Selected-pair 10-point bins:",
        "",
        "| Score interval | N |",
        "|---|---:|",
    ]
    for bin_index in range(10):
        closing = "]" if bin_index == 9 else ")"
        lines.append(
            f"| [{bin_index * 10}, {(bin_index + 1) * 10}{closing} | "
            f"{selected_score_bins.get(bin_index, 0)} |"
        )
    lines.extend(
        [
            "",
            "## Character balance",
            "",
            "| char_id | character | candidate pairs | selected pairs | eligible instances |",
            "|---:|:---:|---:|---:|---:|",
        ]
    )
    for row in per_character:
        lines.append(
            f"| {row['char_id']} | {row['target_char']} | "
            f"{row['candidate_pair_count']} | {selected_counts[row['char_id']]} | "
            f"{row['eligible_unique_instances']} |"
        )
    lines.extend(
        [
            "",
            "## Team review checklist",
            "",
            "Review `candidate_review_form.csv` together with the numbered contact sheets:",
            "",
            "1. Confirm no character dominates (expected: 3-4 selected pairs each).",
            "2. Confirm the current-score range is sufficiently broad both globally and "
            "within characters.",
            "3. Check that candidate and reference are genuinely different instances.",
            "4. Confirm no field or report implies a recovered writer identity.",
            "5. Confirm no pair is described as verified cross-style.",
            "6. Flag any remaining damaged, truncated, blank, or mismatched image.",
            "",
            "Only after this review is complete may a separate explicit freeze step create "
            "`frozen_expert_pairs_v1.csv`. Once human scoring starts, the frozen pair list "
            "must not change.",
            "",
        ]
    )
    (output / "CANDIDATE_REVIEW_REPORT.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def build_expert_candidate_review(
    *,
    manifest_path: str | Path,
    dataset_root: str | Path,
    output_dir: str | Path,
    legacy_git_dir: str | Path | None = None,
    seed: int = 20260812,
    pairs_per_character: int = 10,
    selected_pairs: int = 150,
    image_mask_iou_exclusion_threshold: float = 0.80,
) -> dict[str, Any]:
    output = Path(output_dir)
    frozen_path = output / "frozen_expert_pairs_v1.csv"
    if frozen_path.exists():
        raise RuntimeError(
            "refusing to overwrite a directory containing frozen_expert_pairs_v1.csv"
        )
    output.mkdir(parents=True, exist_ok=True)
    writer_forensics = build_writer_forensics(
        manifest_path,
        dataset_root=dataset_root,
        legacy_git_dir=legacy_git_dir,
    )
    write_writer_forensics(output, writer_forensics)
    records, quality_rows, duplicate_rows = audit_samples(
        manifest_path,
        dataset_root,
        image_mask_iou_exclusion_threshold=image_mask_iou_exclusion_threshold,
    )
    eligible_rows = [
        {
            "sample_id": record.sample_id,
            "char_id": record.char_id,
            "eligible": record.eligible,
        }
        for record in records
    ]
    pairs = construct_balanced_pairs(
        eligible_rows,
        pairs_per_character=pairs_per_character,
        seed=seed,
    )
    candidates = score_natural_pairs(pairs, records, dataset_root)
    selected = select_internal_review_pairs(
        candidates,
        target_pairs=selected_pairs,
        seed=seed,
    )
    lookup = {record.sample_id: record for record in records}
    review_sheets = render_review_sheets(
        selected,
        lookup,
        output,
    )
    quality_exclusion_sheet = render_quality_exclusion_sheet(
        records,
        output / "quality_exclusions_source_vs_gt.png",
    )
    distribution_rows, score_summary = build_score_distribution(
        candidates,
        selected,
    )
    per_character = build_per_character_summary(
        records,
        candidates,
        selected,
    )
    _write_csv(output / "image_quality_audit.csv", quality_rows)
    _write_csv(output / "duplicate_instance_audit.csv", duplicate_rows)
    _write_csv(
        output / f"natural_pair_candidates_{len(candidates)}.csv",
        candidates,
        PAIR_FIELDS,
    )
    _write_csv(
        output / f"candidate_selection_{len(selected)}.csv",
        selected,
    )
    _write_csv(
        output / "candidate_review_form.csv",
        _review_rows(selected),
        REVIEW_FIELDS,
    )
    _write_csv(output / "score_distribution.csv", distribution_rows)
    _write_csv(output / "per_character_summary.csv", per_character)
    metadata = {
        "schema_version": 1,
        "study_status": CANDIDATE_STATUS,
        "freeze_status": FREEZE_STATUS,
        "manifest_path": str(Path(manifest_path).resolve()),
        "dataset_root": str(Path(dataset_root).resolve()),
        "reference_cache_used_as_ground_truth": False,
        "labels_generated_or_fabricated": False,
        "complete_gt_samples_audited": len(records),
        "quality_excluded_instances": sum(
            bool(record.hard_exclusion_reasons) for record in records
        ),
        "exact_duplicate_noncanonical_instances": sum(
            not record.is_duplicate_canonical for record in records
        ),
        "eligible_unique_instances": sum(record.eligible for record in records),
        "candidate_pair_count": len(candidates),
        "selected_internal_review_pair_count": len(selected),
        "seed": seed,
        "writer_identity": writer_forensics,
        "style_provenance_status": STYLE_PROVENANCE_STATUS,
        "score_summary": score_summary,
        "review_sheets": [path.name for path in review_sheets],
        "quality_exclusion_sheet": (
            quality_exclusion_sheet.name
            if quality_exclusion_sheet is not None
            else None
        ),
        "frozen_file_created": frozen_path.exists(),
        "next_gate": (
            "Team reviews candidate_review_form.csv and contact sheets. "
            "Do not collect human ratings before an explicit freeze step."
        ),
    }
    (output / "candidate_review_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_candidate_review_report(
        output,
        records=records,
        candidates=candidates,
        selected=selected,
        per_character=per_character,
        score_summary=score_summary,
        writer_forensics=writer_forensics,
        review_sheets=review_sheets,
        seed=seed,
    )
    if frozen_path.exists():
        raise RuntimeError("candidate builder must never create the frozen pair file")
    return metadata
