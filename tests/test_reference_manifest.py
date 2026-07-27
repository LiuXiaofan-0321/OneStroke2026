from __future__ import annotations

import csv

import yaml

from onestroke_model.scripts.validate_reference_manifest import validate_reference_manifest


def _write_registry(path, enabled: bool) -> None:
    path.write_text(
        yaml.safe_dump({"styles": [{"style_id": "test_style", "enabled": enabled}]}),
        encoding="utf-8",
    )


def _write_manifest(path, review_status: str) -> None:
    fields = [
        "schema_version", "reference_id", "style_id", "target_char", "image_path",
        "source_type", "source_url", "source_license", "source_work_id", "source_version",
        "author_id", "script_style", "is_synthetic", "review_status", "reviewer", "review_date",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "schema_version": "1", "reference_id": "ref_1", "style_id": "test_style",
                "target_char": "永", "image_path": "reference.png", "source_type": "manual",
                "source_url": "https://example.test", "source_license": "test-license",
                "source_work_id": "work_1", "source_version": "v1", "author_id": "author",
                "script_style": "kaishu", "is_synthetic": "false", "review_status": review_status,
                "reviewer": "reviewer", "review_date": "2026-07-27",
            }
        )


def test_reference_manifest_requires_enabled_style_for_approved_rows(tmp_path) -> None:
    registry = tmp_path / "registry.yaml"
    manifest = tmp_path / "manifest.csv"
    _write_registry(registry, enabled=False)
    _write_manifest(manifest, review_status="approved")

    report = validate_reference_manifest(manifest, registry)

    assert report["valid"] is False
    assert any(error["message"] == "style is not enabled" for error in report["errors"])


def test_reference_manifest_accepts_approved_rows_for_enabled_style(tmp_path) -> None:
    registry = tmp_path / "registry.yaml"
    manifest = tmp_path / "manifest.csv"
    _write_registry(registry, enabled=True)
    _write_manifest(manifest, review_status="approved")

    report = validate_reference_manifest(manifest, registry, require_approved=True)

    assert report["valid"] is True
    assert report["num_approved"] == 1


def test_reference_manifest_resolves_images_relative_to_manifest(tmp_path) -> None:
    registry = tmp_path / "registry.yaml"
    manifest = tmp_path / "manifest.csv"
    image = tmp_path / "reference.png"
    image.write_bytes(b"placeholder")
    _write_registry(registry, enabled=True)
    _write_manifest(manifest, review_status="approved")

    report = validate_reference_manifest(manifest, registry, check_files=True)

    assert report["valid"] is True
