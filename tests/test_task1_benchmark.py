from __future__ import annotations

import json
from pathlib import Path

from onestroke_model.task1_benchmark import _is_complete, task1_config_paths


def test_task1_matrix_paths_are_complete_and_unique() -> None:
    paths = task1_config_paths()
    assert len(paths) == 18
    assert len(set(paths)) == 18


def test_completed_run_requires_checkpoint_val_thresholds_and_test_metrics(
    tmp_path: Path,
) -> None:
    output = Path("run")
    run_dir = tmp_path / output
    (run_dir / "checkpoints").mkdir(parents=True)
    (run_dir / "checkpoints/best.pt").write_bytes(b"checkpoint")
    (run_dir / "thresholds_val.json").write_text(
        json.dumps({"calibration_split": "val"}),
        encoding="utf-8",
    )
    (run_dir / "test_metrics.json").write_text(
        json.dumps({"split": "test"}),
        encoding="utf-8",
    )
    assert _is_complete(tmp_path, output)
    (run_dir / "test_metrics.json").write_text(
        json.dumps({"split": "val"}),
        encoding="utf-8",
    )
    assert not _is_complete(tmp_path, output)
