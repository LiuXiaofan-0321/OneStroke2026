from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from onestroke_model.constants import CHANNELS, MASK_FILENAMES, SCHEMA_VERSION, STACKED_MASK_FILENAME


IMAGE_CANDIDATES = ("0.jpg", "image.jpg", "input.jpg", "mask_img.jpg")


@dataclass(frozen=True)
class AuditResult:
    rows: list[dict[str, Any]]
    report: dict[str, Any]


def _safe_image_size(path: Path | None) -> tuple[int | None, int | None, str | None]:
    if path is None or not path.exists():
        return None, None, "missing_image"
    try:
        with Image.open(path) as im:
            width, height = im.size
        return width, height, None
    except Exception as exc:  # pragma: no cover - depends on corrupt files
        return None, None, f"bad_image:{type(exc).__name__}"


def _safe_npy_shape(path: Path) -> tuple[str | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        arr = np.load(path, mmap_mode="r")
        return "x".join(str(v) for v in arr.shape), None
    except Exception as exc:  # pragma: no cover - depends on corrupt files
        return None, f"bad_npy:{type(exc).__name__}"


def _sample_index(sample_dir: Path) -> int | None:
    try:
        return int(sample_dir.name)
    except ValueError:
        return None


def discover_samples(data_root: str | Path) -> list[Path]:
    root = Path(data_root)
    if not root.exists():
        raise FileNotFoundError(f"data_root does not exist: {root}")
    samples: list[Path] = []
    for char_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
        for sample_dir in sorted((p for p in char_dir.iterdir() if p.is_dir()), key=lambda p: p.name):
            samples.append(sample_dir)
    return samples


def audit_data(data_root: str | Path, data_version: str = "old_onestroke") -> AuditResult:
    root = Path(data_root).resolve()
    rows: list[dict[str, Any]] = []
    char_dirs: set[str] = set()
    missing_masks = 0
    bad_samples = 0

    for sample_dir in discover_samples(root):
        char_dir = sample_dir.parent
        char_id = char_dir.name
        char_dirs.add(char_id)
        sample_index = _sample_index(sample_dir)
        sample_id = f"{char_id}/{sample_dir.name}"

        image_path = next((sample_dir / name for name in IMAGE_CANDIDATES if (sample_dir / name).exists()), None)
        width, height, image_error = _safe_image_size(image_path)

        stacked_path = sample_dir / STACKED_MASK_FILENAME
        stacked_shape, stacked_error = _safe_npy_shape(stacked_path)

        errors: list[str] = []
        if image_error:
            errors.append(image_error)
        if stacked_error:
            errors.append(f"stacked_mask:{stacked_error}")

        row: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "data_version": data_version,
            "sample_id": sample_id,
            "char_id": char_id,
            "char_name": "",
            "sample_index": "" if sample_index is None else sample_index,
            "source_id": "",
            "writer_id": "",
            "sample_dir": str(sample_dir),
            "image_path": "" if image_path is None else str(image_path),
            "image_width": "" if width is None else width,
            "image_height": "" if height is None else height,
            "stacked_mask_path": str(stacked_path) if stacked_path.exists() else "",
            "stacked_mask_shape": stacked_shape or "",
        }

        mask_shapes: set[str] = set()
        has_all_masks = True
        for channel in CHANNELS:
            mask_path = sample_dir / MASK_FILENAMES[channel]
            shape, err = _safe_npy_shape(mask_path)
            row[f"{channel}_path"] = str(mask_path) if mask_path.exists() else ""
            row[f"{channel}_shape"] = shape or ""
            if shape:
                mask_shapes.add(shape)
            if err:
                has_all_masks = False
                errors.append(f"{channel}:{err}")

        if not has_all_masks:
            missing_masks += 1
        if len(mask_shapes) > 1:
            errors.append("mask_shape_mismatch")
        if errors:
            bad_samples += 1

        row["has_all_masks"] = str(has_all_masks).lower()
        sample_index_key = "" if sample_index is None else str(sample_index)
        row["split_group_key"] = row["writer_id"] or row["source_id"] or sample_index_key or sample_id
        row["errors"] = "|".join(errors)
        rows.append(row)

    report = {
        "data_root": str(root),
        "schema_version": SCHEMA_VERSION,
        "channels": list(CHANNELS),
        "num_char_dirs": len(char_dirs),
        "num_samples": len(rows),
        "num_samples_with_errors": bad_samples,
        "num_samples_missing_any_mask": missing_masks,
        "num_complete_samples": sum(1 for r in rows if r["has_all_masks"] == "true" and not r["errors"]),
    }
    return AuditResult(rows=rows, report=report)


MANIFEST_FIELDNAMES = [
    "schema_version",
    "data_version",
    "sample_id",
    "char_id",
    "char_name",
    "sample_index",
    "source_id",
    "writer_id",
    "sample_dir",
    "image_path",
    "image_width",
    "image_height",
    "stacked_mask_path",
    "stacked_mask_shape",
    *[f"{c}_path" for c in CHANNELS],
    *[f"{c}_shape" for c in CHANNELS],
    "has_all_masks",
    "split_group_key",
    "errors",
]
