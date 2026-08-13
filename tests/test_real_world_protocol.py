from __future__ import annotations

from pathlib import Path

from onestroke_model.real_world_protocol import (
    validate_real_world_rows,
    write_real_world_templates,
)


def test_templates_are_explicitly_pending(tmp_path: Path) -> None:
    metadata = write_real_world_templates(tmp_path)
    assert metadata["status"] == "PENDING_DATA_COLLECTION"
    assert (tmp_path / "smartphone_manifest_template.csv").is_file()
    assert (tmp_path / "smartphone_annotation_template.csv").is_file()


def test_consent_and_ethics_are_hard_gates() -> None:
    row = {
        "sample_id": "s1",
        "writer_anonymized_id": "writer-001",
        "char_id": "永",
        "image_path": "future.png",
        "annotation_status": "unannotated",
        "consent_status": "pending",
        "ethics_status": "pending",
    }
    report = validate_real_world_rows([row])
    assert report["status"] == "FAIL"
    assert report["formal_evaluation_ready"] is False
    assert {error["field"] for error in report["errors"]} >= {
        "consent_status",
        "ethics_status",
    }


def test_ready_metadata_passes_without_requiring_local_files() -> None:
    row = {
        "sample_id": "s1",
        "writer_anonymized_id": "writer-001",
        "char_id": "永",
        "image_path": "future.png",
        "annotation_status": "complete",
        "consent_status": "confirmed",
        "ethics_status": "approved",
    }
    report = validate_real_world_rows([row], require_local_images=False)
    assert report["status"] == "PASS"
    assert report["formal_evaluation_ready"] is True
