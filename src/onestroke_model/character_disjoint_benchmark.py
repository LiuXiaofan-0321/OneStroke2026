"""Frozen character-disjoint benchmark orchestration and result summarization."""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from onestroke_model.character_disjoint_runs import (
    DEFAULT_CONFIGS,
    build_character_disjoint_run_plan,
)
from onestroke_model.config import load_yaml
from onestroke_model.reproducibility import sha256_file, utc_now_iso

SUMMARY_METRICS = (
    "macro_dice",
    "macro_iou",
    "keypoint_f1",
    "boundary_f1",
    "keypoint_f1_tolerance_1",
    "keypoint_f1_tolerance_3",
    "keypoint_f1_tolerance_5",
)


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _run_command(command: str, *, cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n[{utc_now_iso()}] $ {command}\n")
        log.flush()
        completed = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            check=False,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed with exit code {completed.returncode}; see {log_path}"
        )


def _extract_metric(metrics: dict[str, Any], name: str) -> float | None:
    value = metrics.get(name)
    if value is not None:
        return float(value)
    tolerant = metrics.get("keypoint_tolerance", {})
    if name.startswith("keypoint_f1_tolerance_") and isinstance(tolerant, dict):
        radius = name.rsplit("_", 1)[-1]
        payload = tolerant.get(radius)
        if isinstance(payload, dict) and payload.get("f1") is not None:
            return float(payload["f1"])
    return None


def summarize_character_disjoint_runs(
    plan: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Summarize completed test metrics without inventing missing runs."""

    output = Path(output_dir)
    per_run: list[dict[str, object]] = []
    missing: list[str] = []
    for run in plan["runs"]:
        if run["status"] == "BLOCKED_BY_TASK1":
            continue
        config_path = Path(run["config"])
        run_output = Path(load_yaml(config_path)["output_dir"])
        if not run_output.is_absolute():
            run_output = Path(plan["project_root"]) / run_output
        metrics_path = run_output / "test_metrics.json"
        thresholds_path = run_output / "thresholds_val.json"
        checkpoint_path = run_output / "checkpoints/best.pt"
        if not metrics_path.is_file():
            missing.append(run["experiment_name"])
            continue
        if not thresholds_path.is_file():
            raise ValueError(
                f"test metrics exist without validation thresholds: {thresholds_path}"
            )
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if metrics.get("split") != "test":
            raise ValueError(f"non-test metrics found at {metrics_path}")
        thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
        if thresholds.get("calibration_split") != "val":
            raise ValueError(f"thresholds were not calibrated on validation: {thresholds_path}")
        row: dict[str, object] = {
            "experiment_name": run["experiment_name"],
            "model_name": run["model_name"],
            "seed": run["seed"],
            "config_sha256": run["config_sha256"],
            "checkpoint_sha256": (
                sha256_file(checkpoint_path) if checkpoint_path.is_file() else ""
            ),
            "thresholds_sha256": sha256_file(thresholds_path),
            "test_metrics_sha256": sha256_file(metrics_path),
        }
        for name in SUMMARY_METRICS:
            value = _extract_metric(metrics, name)
            row[name] = "" if value is None else value
        per_run.append(row)

    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for row in per_run:
        grouped[str(row["model_name"])].append(row)
    summary_rows: list[dict[str, object]] = []
    for model_name, rows in sorted(grouped.items()):
        summary: dict[str, object] = {
            "model_name": model_name,
            "completed_seed_count": len(rows),
            "seeds": ";".join(str(row["seed"]) for row in rows),
        }
        for metric in SUMMARY_METRICS:
            values = [
                float(row[metric])
                for row in rows
                if row.get(metric) not in ("", None)
            ]
            summary[f"{metric}_mean"] = statistics.mean(values) if values else ""
            summary[f"{metric}_std"] = (
                statistics.stdev(values) if len(values) >= 2 else ""
            )
        summary_rows.append(summary)

    per_run_fields = [
        "experiment_name",
        "model_name",
        "seed",
        "config_sha256",
        "checkpoint_sha256",
        "thresholds_sha256",
        "test_metrics_sha256",
        *SUMMARY_METRICS,
    ]
    summary_fields = ["model_name", "completed_seed_count", "seeds"]
    for metric in SUMMARY_METRICS:
        summary_fields.extend([f"{metric}_mean", f"{metric}_std"])
    _write_csv(output / "results_per_seed.csv", per_run, per_run_fields)
    _write_csv(output / "results_summary.csv", summary_rows, summary_fields)
    result = {
        "schema_version": 1,
        "generated_at_utc": utc_now_iso(),
        "completed_run_count": len(per_run),
        "missing_experiments": missing,
        "test_used_for_model_selection": False,
        "threshold_calibration_split": "val",
        "per_seed_csv": str((output / "results_per_seed.csv").resolve()),
        "summary_csv": str((output / "results_summary.csv").resolve()),
    }
    (output / "summary_manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def run_character_disjoint_benchmark(
    project_root: str | Path,
    *,
    split_report_path: str | Path,
    config_paths: Sequence[str | Path] = DEFAULT_CONFIGS,
    execute: bool = False,
    output_plan: str | Path = (
        "artifacts/paper_ijdar/character_disjoint/character_disjoint_execution_plan.json"
    ),
    expected_split_sha256: str | None = None,
    expected_sample_counts: dict[str, int] | None = None,
    expected_character_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build the plan; execute only after every frozen prerequisite is ready."""

    root = Path(project_root).resolve()
    plan_kwargs: dict[str, Any] = {}
    if expected_split_sha256 is not None:
        plan_kwargs["expected_split_sha256"] = expected_split_sha256
    if expected_sample_counts is not None:
        plan_kwargs["expected_sample_counts"] = expected_sample_counts
    if expected_character_counts is not None:
        plan_kwargs["expected_character_counts"] = expected_character_counts
    plan = build_character_disjoint_run_plan(
        root,
        split_report_path=split_report_path,
        config_paths=config_paths,
        **plan_kwargs,
    )
    plan["project_root"] = str(root)
    plan["requested_execute"] = bool(execute)
    output_plan_path = root / output_plan
    output_plan_path.parent.mkdir(parents=True, exist_ok=True)
    output_plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not execute:
        return plan

    blocked = [
        f"{run['experiment_name']}:{run['status']}"
        for run in plan["runs"]
        if run["status"] != "READY"
    ]
    if blocked:
        raise RuntimeError(
            "training refused because the frozen benchmark is not fully ready: "
            + ", ".join(blocked)
        )

    for run in plan["runs"]:
        run_output = root / Path(
            load_yaml(Path(run["config"]))["output_dir"]
        )
        log_path = run_output / "benchmark.log"
        state_path = run_output / "benchmark_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "schema_version": 1,
            "experiment_name": run["experiment_name"],
            "status": "RUNNING",
            "started_at_utc": utc_now_iso(),
            "commands": run["commands"],
        }
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            for command in run["commands"]:
                _run_command(command, cwd=root, log_path=log_path)
        except Exception:
            state["status"] = "FAILED"
            state["ended_at_utc"] = utc_now_iso()
            state_path.write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            raise
        state["status"] = "COMPLETED"
        state["ended_at_utc"] = utc_now_iso()
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary = summarize_character_disjoint_runs(
        plan,
        root / "artifacts/paper_ijdar/character_disjoint",
    )
    return {"plan": plan, "summary": summary}
