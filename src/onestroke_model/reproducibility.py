"""Unified run-manifest generation for paper experiments."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import platform
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import __version__ as pillow_version


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: str | Path) -> str:
    value = Path(path)
    digest = hashlib.sha256()
    with value.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_csv_sha256(path: str | Path) -> str:
    """Hash CSV content independently of LF/CRLF checkout differences."""

    value = Path(path)
    with value.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {value}")
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        lineterminator="\r\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return hashlib.sha256(buffer.getvalue().encode("utf-8")).hexdigest()


def git_commit(project_root: str | Path | None = None) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(project_root or Path.cwd()),
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None


def exact_command(argv: Sequence[str] | None = None) -> str:
    values = list(argv or sys.argv)
    return shlex.join([sys.executable, *values])


def runtime_environment() -> dict[str, Any]:
    result: dict[str, Any] = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "pillow_version": pillow_version,
        "pytorch_version": None,
        "cuda_version": None,
        "cuda_available": False,
        "gpu_models": [],
    }
    try:
        import torch
    except ImportError:
        return result
    result["pytorch_version"] = torch.__version__
    result["cuda_version"] = torch.version.cuda
    result["cuda_available"] = bool(torch.cuda.is_available())
    if torch.cuda.is_available():
        result["gpu_models"] = [
            torch.cuda.get_device_name(index)
            for index in range(torch.cuda.device_count())
        ]
    return result


def _file_record(path: str | Path) -> dict[str, Any]:
    value = Path(path)
    return {
        "path": str(value.resolve()),
        "exists": value.is_file(),
        "sha256": sha256_file(value) if value.is_file() else None,
        "size_bytes": value.stat().st_size if value.is_file() else None,
    }


def build_run_manifest(
    *,
    experiment_name: str,
    status: str,
    started_at: str,
    ended_at: str,
    project_root: str | Path | None = None,
    command: str | None = None,
    seed: int | str | None = None,
    config_paths: Sequence[str | Path] = (),
    input_paths: Sequence[str | Path] = (),
    checkpoint_path: str | Path | None = None,
    thresholds: Mapping[str, float] | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(project_root or Path.cwd()).resolve()
    checkpoint = _file_record(checkpoint_path) if checkpoint_path is not None else None
    return {
        "schema_version": 1,
        "experiment_name": experiment_name,
        "status": status,
        "git_commit": git_commit(root),
        "project_root": str(root),
        "seed": seed,
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "exact_command": command or exact_command(),
        "configs": [_file_record(path) for path in config_paths],
        "inputs": [_file_record(path) for path in input_paths],
        "checkpoint": checkpoint,
        "thresholds": dict(thresholds or {}),
        "environment": runtime_environment(),
        "additional": dict(additional or {}),
    }


def write_run_manifest(output_dir: str | Path, manifest: Mapping[str, Any]) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "run_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
