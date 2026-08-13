from __future__ import annotations

import csv
import io
import tarfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from onestroke_model.data import legacy_gt_recovery as recovery


def _write_manifest(path: Path, sample_id: str = "0/0") -> None:
    fieldnames = [
        "schema_version",
        "data_version",
        "sample_id",
        "char_id",
        "sample_index",
        "sample_dir",
        "image_path",
        "image_width",
        "image_height",
        "stacked_mask_path",
        "stacked_mask_shape",
        "vec1_path",
        "vec2_path",
        "vec3_path",
        "vec4_path",
        "vec5_path",
        "keypoint_path",
        "vec1_shape",
        "vec2_shape",
        "vec3_shape",
        "vec4_shape",
        "vec5_shape",
        "keypoint_shape",
        "has_all_masks",
        "errors",
    ]
    row = {name: "" for name in fieldnames}
    row.update(
        {
            "schema_version": "1",
            "data_version": "old",
            "sample_id": sample_id,
            "char_id": sample_id.split("/")[0],
            "sample_index": sample_id.split("/")[1],
            "has_all_masks": "true",
        }
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def _array_bytes(array: np.ndarray) -> bytes:
    output = io.BytesIO()
    np.save(output, array)
    return output.getvalue()


def _image_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (4, 4), color="white").save(output, format="JPEG")
    return output.getvalue()


def _add_bytes(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(data)
    archive.addfile(member, io.BytesIO(data))


def _build_archive(path: Path, *, add_unsafe: bool = False) -> None:
    masks = [np.zeros((4, 4), dtype=bool) for _ in range(6)]
    masks[0][1:3, 1:3] = True
    prefix = f"{recovery.LEGACY_ARCHIVE_PREFIX.as_posix()}/0/0"
    with tarfile.open(path, "w:gz") as archive:
        _add_bytes(archive, f"{prefix}/0.jpg", _image_bytes())
        _add_bytes(archive, f"{prefix}/0.npy", _array_bytes(np.stack(masks, axis=-1)))
        for channel, mask in zip(recovery.CHANNELS, masks, strict=True):
            _add_bytes(
                archive,
                f"{prefix}/{recovery.MASK_FILENAMES[channel]}",
                _array_bytes(mask),
            )
        if add_unsafe:
            _add_bytes(archive, "../escape.txt", b"unsafe")


def test_recovery_enforces_archive_hash(tmp_path: Path, monkeypatch) -> None:
    archive = tmp_path / "legacy.tar.gz"
    manifest = tmp_path / "manifest.csv"
    _build_archive(archive)
    _write_manifest(manifest)
    monkeypatch.setattr(recovery, "EXPECTED_TOTAL_SAMPLE_COUNT", 1)
    monkeypatch.setattr(recovery, "EXPECTED_COMPLETE_SAMPLE_COUNT", 1)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        recovery.restore_legacy_ground_truth(
            archive,
            tmp_path / "restored",
            manifest,
            tmp_path / "resolved.csv",
            tmp_path / "report.json",
            expected_archive_sha256="0" * 64,
        )


def test_recovery_rejects_path_traversal(tmp_path: Path, monkeypatch) -> None:
    archive = tmp_path / "legacy.tar.gz"
    manifest = tmp_path / "manifest.csv"
    _build_archive(archive, add_unsafe=True)
    _write_manifest(manifest)
    monkeypatch.setattr(recovery, "EXPECTED_TOTAL_SAMPLE_COUNT", 1)
    monkeypatch.setattr(recovery, "EXPECTED_COMPLETE_SAMPLE_COUNT", 1)
    with pytest.raises(ValueError, match="unsafe archive member"):
        recovery.restore_legacy_ground_truth(
            archive,
            tmp_path / "restored",
            manifest,
            tmp_path / "resolved.csv",
            tmp_path / "report.json",
            expected_archive_sha256=recovery.sha256_file(archive),
        )


def test_recovery_verifies_stacked_masks_and_writes_resolved_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    archive = tmp_path / "legacy.tar.gz"
    manifest = tmp_path / "manifest.csv"
    resolved = tmp_path / "resolved.csv"
    report_path = tmp_path / "report.json"
    _build_archive(archive)
    _write_manifest(manifest)
    monkeypatch.setattr(recovery, "EXPECTED_TOTAL_SAMPLE_COUNT", 1)
    monkeypatch.setattr(recovery, "EXPECTED_COMPLETE_SAMPLE_COUNT", 1)
    report = recovery.restore_legacy_ground_truth(
        archive,
        tmp_path / "restored",
        manifest,
        resolved,
        report_path,
        expected_archive_sha256=recovery.sha256_file(archive),
    )
    assert report["fully_array_verified_sample_count"] == 1
    assert report["stacked_equals_independent_for_all_complete_samples"] is True
    assert report["reference_cache_used_as_ground_truth"] is False
    assert report["labels_generated_or_fabricated"] is False
    rows = list(csv.DictReader(resolved.open(encoding="utf-8")))
    assert Path(rows[0]["image_path"]).is_file()
    assert "references/cache" not in rows[0]["image_path"].replace("\\", "/")
