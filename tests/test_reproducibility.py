from __future__ import annotations

from pathlib import Path

from onestroke_model.reproducibility import (
    build_run_manifest,
    sha256_file,
    write_run_manifest,
)


def test_run_manifest_hashes_inputs_and_records_status(tmp_path: Path) -> None:
    input_path = tmp_path / "input.txt"
    input_path.write_text("evidence", encoding="utf-8")
    manifest = build_run_manifest(
        experiment_name="test",
        status="BLOCKED",
        started_at="2026-08-11T00:00:00+00:00",
        ended_at="2026-08-11T00:00:01+00:00",
        project_root=tmp_path,
        command="python test.py",
        seed=7,
        input_paths=[input_path, tmp_path / "missing.txt"],
        additional={"reason": "missing cache"},
    )
    assert manifest["status"] == "BLOCKED"
    assert manifest["inputs"][0]["sha256"] == sha256_file(input_path)
    assert manifest["inputs"][1]["exists"] is False
    path = write_run_manifest(tmp_path / "output", manifest)
    assert path.is_file()
