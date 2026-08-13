"""Safe restoration and exhaustive validation of the recovered legacy GT archive."""

from __future__ import annotations

import csv
import json
import os
import shutil
import tarfile
import tempfile
import time
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
from PIL import Image

from onestroke_model.constants import CHANNELS
from onestroke_model.reproducibility import sha256_file

LEGACY_ARCHIVE_SHA256 = "b9924007099033cc8b62128dc2139ea9cb04a66a48e56c46518407677254450d"
LEGACY_ARCHIVE_PREFIX = PurePosixPath(
    "OneStroke-main/StrokeSegmentation/data/output_img"
)
EXPECTED_COMPLETE_SAMPLE_COUNT = 840
EXPECTED_TOTAL_SAMPLE_COUNT = 894

MASK_FILENAMES = {
    "vec1": "mask_1.npy",
    "vec2": "mask_2.npy",
    "vec3": "mask_3.npy",
    "vec4": "mask_4.npy",
    "vec5": "mask_5.npy",
    "keypoint": "mask_key_point.npy",
}
REQUIRED_COMPLETE_FILENAMES = ("0.jpg", "0.npy", *MASK_FILENAMES.values())


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _read_manifest(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"manifest has no header: {path}")
        return list(reader), list(reader.fieldnames)


def _write_manifest(
    path: Path,
    rows: list[dict[str, object]],
    fieldnames: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_relative_member(member_name: str) -> PurePosixPath:
    """Return a safe POSIX archive member path or raise.

    The function rejects absolute paths, parent traversal, Windows drive-like
    prefixes, and NUL bytes before any filesystem write is attempted.
    """

    if "\x00" in member_name:
        raise ValueError("archive member contains a NUL byte")
    normalized = member_name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe archive member path: {member_name}")
    if path.parts and ":" in path.parts[0]:
        raise ValueError(f"drive-qualified archive member path: {member_name}")
    return path


def _relative_to_dataset(path: PurePosixPath) -> PurePosixPath | None:
    try:
        relative = path.relative_to(LEGACY_ARCHIVE_PREFIX)
    except ValueError:
        return None
    if not relative.parts:
        return None
    return relative


def _archive_inventory(
    archive: tarfile.TarFile,
) -> tuple[dict[str, tarfile.TarInfo], set[str]]:
    files: dict[str, tarfile.TarInfo] = {}
    sample_ids: set[str] = set()
    for member in archive.getmembers():
        safe_member_path = _safe_relative_member(member.name)
        relative = _relative_to_dataset(safe_member_path)
        if relative is None:
            continue
        if member.issym() or member.islnk() or member.isdev() or member.isfifo():
            raise ValueError(f"unsupported special archive member: {member.name}")
        if not member.isfile():
            continue
        if len(relative.parts) < 3:
            if relative.name == ".DS_Store":
                continue
            raise ValueError(f"unexpected dataset member layout: {member.name}")
        sample_id = f"{relative.parts[0]}/{relative.parts[1]}"
        sample_ids.add(sample_id)
        files[relative.as_posix()] = member
    return files, sample_ids


def _validate_inventory_against_manifest(
    files: dict[str, tarfile.TarInfo],
    archive_sample_ids: set[str],
    manifest_rows: list[dict[str, str]],
) -> tuple[set[str], set[str]]:
    manifest_ids = {row["sample_id"].strip() for row in manifest_rows}
    complete_ids = {
        row["sample_id"].strip()
        for row in manifest_rows
        if _truthy(row.get("has_all_masks"))
        and not str(row.get("errors", "")).strip()
    }
    if len(manifest_ids) != EXPECTED_TOTAL_SAMPLE_COUNT:
        raise ValueError(
            f"expected {EXPECTED_TOTAL_SAMPLE_COUNT} manifest IDs, got {len(manifest_ids)}"
        )
    if len(complete_ids) != EXPECTED_COMPLETE_SAMPLE_COUNT:
        raise ValueError(
            "expected "
            f"{EXPECTED_COMPLETE_SAMPLE_COUNT} complete manifest IDs, got {len(complete_ids)}"
        )
    if archive_sample_ids != manifest_ids:
        missing = sorted(manifest_ids - archive_sample_ids)
        extra = sorted(archive_sample_ids - manifest_ids)
        raise ValueError(
            "archive/manifest sample-ID mismatch: "
            f"missing={missing[:10]} extra={extra[:10]}"
        )
    for sample_id in sorted(complete_ids):
        for filename in REQUIRED_COMPLETE_FILENAMES:
            relative = f"{sample_id}/{filename}"
            if relative not in files:
                raise ValueError(f"complete sample is missing from archive: {relative}")
    return manifest_ids, complete_ids


def _extract_inventory(
    archive: tarfile.TarFile,
    files: dict[str, tarfile.TarInfo],
    destination: Path,
) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    resolved_destination = destination.resolve()
    for relative_name, member in files.items():
        relative = _safe_relative_member(relative_name)
        output = destination.joinpath(*relative.parts)
        resolved_output = output.resolve()
        if (
            resolved_output == resolved_destination
            or resolved_destination not in resolved_output.parents
        ):
            raise ValueError(f"archive extraction escaped destination: {member.name}")
        output.parent.mkdir(parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise ValueError(f"could not read archive member: {member.name}")
        with source, output.open("wb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)


def _is_binary(array: np.ndarray) -> bool:
    if array.dtype == np.bool_:
        return True
    return bool(np.logical_or(array == 0, array == 1).all())


def _validate_sample_arrays(sample_dir: Path, sample_id: str) -> dict[str, Any]:
    image_path = sample_dir / "0.jpg"
    with Image.open(image_path) as image:
        width, height = image.size
        image.verify()

    independent = [
        np.load(sample_dir / MASK_FILENAMES[channel], allow_pickle=False)
        for channel in CHANNELS
    ]
    stacked = np.load(sample_dir / "0.npy", allow_pickle=False)
    shapes = [tuple(array.shape) for array in independent]
    expected_stacked = np.stack(independent, axis=-1)
    if len(set(shapes)) != 1:
        raise ValueError(f"{sample_id}: independent mask shapes differ: {shapes}")
    if stacked.shape != expected_stacked.shape:
        raise ValueError(
            f"{sample_id}: stacked shape {stacked.shape} != {expected_stacked.shape}"
        )
    if not all(_is_binary(array) for array in [*independent, stacked]):
        raise ValueError(f"{sample_id}: one or more masks are not binary")
    if not np.array_equal(stacked, expected_stacked):
        mismatch_count = int(np.count_nonzero(stacked != expected_stacked))
        raise ValueError(
            f"{sample_id}: stacked mask differs from independent masks "
            f"at {mismatch_count} values"
        )
    return {
        "image_width": width,
        "image_height": height,
        "independent_shape": list(independent[0].shape),
        "stacked_shape": list(stacked.shape),
    }


def validate_restored_ground_truth(
    dataset_root: str | Path,
    source_manifest: str | Path,
    *,
    progress: Callable[[int, int, str], None] | None = None,
) -> tuple[list[dict[str, object]], list[str], dict[str, Any]]:
    """Validate all recovered samples and construct a path-resolved manifest."""

    root = Path(dataset_root).resolve()
    source_path = Path(source_manifest).resolve()
    rows, fieldnames = _read_manifest(source_path)
    manifest_ids = {row["sample_id"].strip() for row in rows}
    complete_ids = {
        row["sample_id"].strip()
        for row in rows
        if _truthy(row.get("has_all_masks"))
        and not str(row.get("errors", "")).strip()
    }
    if len(manifest_ids) != EXPECTED_TOTAL_SAMPLE_COUNT:
        raise ValueError(
            f"expected {EXPECTED_TOTAL_SAMPLE_COUNT} manifest IDs, got {len(manifest_ids)}"
        )
    if len(complete_ids) != EXPECTED_COMPLETE_SAMPLE_COUNT:
        raise ValueError(
            f"expected {EXPECTED_COMPLETE_SAMPLE_COUNT} complete IDs, got {len(complete_ids)}"
        )

    resolved_rows: list[dict[str, object]] = []
    verified = 0
    for index, row in enumerate(rows, start=1):
        sample_id = row["sample_id"].strip()
        sample_dir = root.joinpath(*sample_id.split("/"))
        image_path = sample_dir / "0.jpg"
        is_declared_complete = sample_id in complete_ids
        required_exist = all(
            (sample_dir / filename).is_file()
            for filename in REQUIRED_COMPLETE_FILENAMES
        )
        if not image_path.is_file():
            raise ValueError(f"{sample_id}: input image is missing after restoration")
        if is_declared_complete and not required_exist:
            raise ValueError(f"{sample_id}: declared-complete sample is incomplete")

        updated: dict[str, object] = dict(row)
        updated["data_version"] = "legacy_gt_recovered_v1"
        updated["sample_dir"] = str(sample_dir)
        updated["image_path"] = str(image_path)
        updated["stacked_mask_path"] = (
            str(sample_dir / "0.npy") if (sample_dir / "0.npy").is_file() else ""
        )
        for channel, filename in MASK_FILENAMES.items():
            path = sample_dir / filename
            updated[f"{channel}_path"] = str(path) if path.is_file() else ""

        if is_declared_complete:
            metadata = _validate_sample_arrays(sample_dir, sample_id)
            verified += 1
            updated["image_width"] = metadata["image_width"]
            updated["image_height"] = metadata["image_height"]
            updated["stacked_mask_shape"] = "x".join(
                str(value) for value in metadata["stacked_shape"]
            )
            independent_shape = "x".join(
                str(value) for value in metadata["independent_shape"]
            )
            for channel in CHANNELS:
                updated[f"{channel}_shape"] = independent_shape
            updated["has_all_masks"] = "true"
            updated["errors"] = ""
        else:
            updated["has_all_masks"] = "false"
        resolved_rows.append(updated)
        if progress is not None and (index % 50 == 0 or index == len(rows)):
            progress(index, len(rows), sample_id)

    actual_dirs = {
        f"{char_dir.name}/{sample_dir.name}"
        for char_dir in root.iterdir()
        if char_dir.is_dir()
        for sample_dir in char_dir.iterdir()
        if sample_dir.is_dir()
    }
    if actual_dirs != manifest_ids:
        missing = sorted(manifest_ids - actual_dirs)
        extra = sorted(actual_dirs - manifest_ids)
        raise ValueError(
            "restored directory/manifest ID mismatch: "
            f"missing={missing[:10]} extra={extra[:10]}"
        )
    if verified != EXPECTED_COMPLETE_SAMPLE_COUNT:
        raise ValueError(
            f"expected to verify {EXPECTED_COMPLETE_SAMPLE_COUNT}, verified {verified}"
        )
    report = {
        "schema_version": 1,
        "status": "VERIFIED",
        "dataset_root": str(root),
        "source_manifest": str(source_path),
        "source_manifest_sha256": sha256_file(source_path),
        "total_sample_count": len(manifest_ids),
        "complete_gt_sample_count": len(complete_ids),
        "incomplete_sample_count": len(manifest_ids - complete_ids),
        "fully_array_verified_sample_count": verified,
        "stacked_equals_independent_for_all_complete_samples": True,
        "binary_masks_for_all_complete_samples": True,
        "reference_cache_used_as_ground_truth": False,
        "labels_generated_or_fabricated": False,
        "excluded_character_ids": ["40", "41", "42"],
        "channel_order": list(CHANNELS),
    }
    return resolved_rows, fieldnames, report


def restore_legacy_ground_truth(
    archive_path: str | Path,
    destination_root: str | Path,
    source_manifest: str | Path,
    resolved_manifest: str | Path,
    verification_report: str | Path,
    *,
    expected_archive_sha256: str = LEGACY_ARCHIVE_SHA256,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Restore the canonical archive and exhaustively verify all 840 complete GTs."""

    started = time.monotonic()
    archive_value = Path(archive_path).resolve()
    destination = Path(destination_root).resolve()
    source_manifest_value = Path(source_manifest).resolve()
    resolved_manifest_value = Path(resolved_manifest).resolve()
    report_value = Path(verification_report).resolve()
    if not archive_value.is_file():
        raise FileNotFoundError(f"legacy archive not found: {archive_value}")
    actual_archive_sha256 = sha256_file(archive_value)
    if actual_archive_sha256 != expected_archive_sha256:
        raise ValueError(
            "legacy archive SHA-256 mismatch: "
            f"expected={expected_archive_sha256} actual={actual_archive_sha256}"
        )

    manifest_rows, _ = _read_manifest(source_manifest_value)
    extracted_now = False
    if destination.exists():
        if not destination.is_dir():
            raise ValueError(f"destination exists but is not a directory: {destination}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_parent = destination.parent.resolve()
        temp_path = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}.extracting-", dir=temp_parent)
        ).resolve()
        try:
            with tarfile.open(archive_value, "r:gz") as archive:
                files, archive_sample_ids = _archive_inventory(archive)
                _validate_inventory_against_manifest(
                    files,
                    archive_sample_ids,
                    manifest_rows,
                )
                extraction_root = temp_path / "output_img"
                _extract_inventory(archive, files, extraction_root)
            os.replace(extraction_root, destination)
            extracted_now = True
        finally:
            if temp_path.exists():
                shutil.rmtree(temp_path)

    resolved_rows, fieldnames, report = validate_restored_ground_truth(
        destination,
        source_manifest_value,
        progress=progress,
    )
    _write_manifest(resolved_manifest_value, resolved_rows, fieldnames)
    report.update(
        {
            "archive_path": str(archive_value),
            "archive_sha256": actual_archive_sha256,
            "archive_contract_sha256": expected_archive_sha256,
            "archive_prefix": LEGACY_ARCHIVE_PREFIX.as_posix(),
            "extracted_now": extracted_now,
            "resolved_manifest": str(resolved_manifest_value),
            "resolved_manifest_sha256": sha256_file(resolved_manifest_value),
            "verification_report": str(report_value),
            "elapsed_seconds": time.monotonic() - started,
        }
    )
    report_value.parent.mkdir(parents=True, exist_ok=True)
    report_value.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report
