"""Schemas and validation for the smartphone/unseen-writer study."""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REAL_WORLD_MANIFEST_FIELDS = (
    "schema_version",
    "sample_id",
    "writer_anonymized_id",
    "char_id",
    "image_path",
    "device_type",
    "lighting_category",
    "background_category",
    "image_source",
    "provenance_notes",
    "annotation_status",
    "consent_status",
    "ethics_status",
    "collection_date",
)

REAL_WORLD_ANNOTATION_FIELDS = (
    "sample_id",
    "vec1_path",
    "vec2_path",
    "vec3_path",
    "vec4_path",
    "vec5_path",
    "keypoint_path",
    "annotation_status",
    "annotator_id",
    "reviewer_id",
    "review_status",
    "notes",
)

CONSENT_READY = {"confirmed", "not_required_by_approved_protocol"}
ETHICS_READY = {"approved", "exempt", "not_required_confirmed"}
ANNOTATION_VALUES = {"unannotated", "in_progress", "complete", "reviewed"}


def _write_header(path: Path, fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(fields)


def write_real_world_templates(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "smartphone_manifest_template.csv"
    annotation_path = output / "smartphone_annotation_template.csv"
    _write_header(manifest_path, REAL_WORLD_MANIFEST_FIELDS)
    _write_header(annotation_path, REAL_WORLD_ANNOTATION_FIELDS)
    metadata = {
        "schema_version": 1,
        "status": "PENDING_DATA_COLLECTION",
        "target_sample_range": [100, 200],
        "writer_disjoint_required": True,
        "segmentation_metrics_require_six_channel_ground_truth": True,
        "qualitative_analysis_without_ground_truth_must_be_labeled": True,
        "consent_ready_values": sorted(CONSENT_READY),
        "ethics_ready_values": sorted(ETHICS_READY),
    }
    (output / "smartphone_protocol_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def validate_real_world_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    require_local_images: bool = False,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    sample_ids: list[str] = []
    writer_counts: Counter[str] = Counter()
    annotation_counts: Counter[str] = Counter()
    for row_number, row in enumerate(rows, start=2):
        sample_id = str(row.get("sample_id", "")).strip()
        writer_id = str(row.get("writer_anonymized_id", "")).strip()
        char_id = str(row.get("char_id", "")).strip()
        image_path = str(row.get("image_path", "")).strip()
        sample_ids.append(sample_id)
        if not sample_id:
            errors.append({"row": row_number, "field": "sample_id", "message": "required"})
        if not writer_id:
            errors.append(
                {
                    "row": row_number,
                    "field": "writer_anonymized_id",
                    "message": "required and must be anonymized",
                }
            )
        else:
            writer_counts[writer_id] += 1
        if not char_id:
            errors.append({"row": row_number, "field": "char_id", "message": "required"})
        if not image_path:
            errors.append({"row": row_number, "field": "image_path", "message": "required"})
        elif require_local_images and not Path(image_path).is_file():
            errors.append(
                {
                    "row": row_number,
                    "field": "image_path",
                    "message": "local image not found",
                }
            )
        consent = str(row.get("consent_status", "")).strip()
        ethics = str(row.get("ethics_status", "")).strip()
        if consent not in CONSENT_READY:
            errors.append(
                {
                    "row": row_number,
                    "field": "consent_status",
                    "message": f"not collection-ready: {consent!r}",
                }
            )
        if ethics not in ETHICS_READY:
            errors.append(
                {
                    "row": row_number,
                    "field": "ethics_status",
                    "message": f"not collection-ready: {ethics!r}",
                }
            )
        annotation = str(row.get("annotation_status", "")).strip()
        annotation_counts[annotation] += 1
        if annotation not in ANNOTATION_VALUES:
            warnings.append(
                {
                    "row": row_number,
                    "field": "annotation_status",
                    "message": f"unexpected value: {annotation!r}",
                }
            )
    duplicate_ids = sorted(
        value for value, count in Counter(sample_ids).items() if value and count > 1
    )
    if duplicate_ids:
        errors.append(
            {
                "field": "sample_id",
                "message": "duplicate sample IDs",
                "values": duplicate_ids,
            }
        )
    return {
        "schema_version": 1,
        "status": "PASS" if not errors else "FAIL",
        "sample_count": len(rows),
        "writer_count": len(writer_counts),
        "writer_sample_counts": dict(writer_counts),
        "annotation_counts": dict(annotation_counts),
        "errors": errors,
        "warnings": warnings,
        "formal_evaluation_ready": not errors and bool(rows),
    }
