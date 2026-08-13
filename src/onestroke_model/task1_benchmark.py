"""Planning, resumable execution, and summarization for the formal Task 1 matrix."""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from onestroke_model.config import load_yaml
from onestroke_model.data.data_contract import validate_data_contract
from onestroke_model.reproducibility import sha256_file, utc_now_iso
from onestroke_model.scripts.generate_task1_configs import MODELS, SEEDS, SPLITS

SUMMARY_METRICS = (
    "macro_dice",
    "macro_iou",
    "keypoint_f1",
    "boundary_f1",
    "keypoint_f1_tolerance_1",
    "keypoint_f1_tolerance_3",
    "keypoint_f1_tolerance_5",
)


def task1_config_paths() -> tuple[Path, ...]:
    return tuple(
        Path("configs/paper_ijdar")
        / f"{split_name}_{model_key}_seed_{seed}.yaml"
        for split_name in SPLITS
        for model_key in MODELS
        for seed in SEEDS
    )


def _commands(config_path: Path, output_dir: Path) -> list[str]:
    checkpoint = output_dir / "checkpoints/best.pt"
    thresholds = output_dir / "thresholds_val.json"
    metrics = output_dir / "test_metrics.json"
    return [
        f'python train.py --config "{config_path.as_posix()}"',
        (
            "python -m onestroke_model.scripts.calibrate_thresholds "
            f'--config "{config_path.as_posix()}" '
            f'--checkpoint "{checkpoint.as_posix()}" '
            f'--output "{thresholds.as_posix()}"'
        ),
        (
            f'python eval.py --config "{config_path.as_posix()}" '
            f'--checkpoint "{checkpoint.as_posix()}" '
            f'--thresholds-json "{thresholds.as_posix()}" '
            f'--split test --output "{metrics.as_posix()}"'
        ),
    ]


def _is_complete(root: Path, output_dir: Path) -> bool:
    required = (
        output_dir / "checkpoints/best.pt",
        output_dir / "thresholds_val.json",
        output_dir / "test_metrics.json",
    )
    if not all((root / path).is_file() for path in required):
        return False
    thresholds = json.loads((root / required[1]).read_text(encoding="utf-8"))
    metrics = json.loads((root / required[2]).read_text(encoding="utf-8"))
    return (
        thresholds.get("calibration_split") == "val"
        and metrics.get("split") == "test"
    )


def build_task1_plan(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    runs: list[dict[str, Any]] = []
    for relative_config in task1_config_paths():
        config_path = root / relative_config
        if not config_path.is_file():
            raise ValueError(f"Task 1 config is missing: {relative_config}")
        config = load_yaml(config_path)
        contract = validate_data_contract(config["data"], project_root=root)
        model_name = str(config["model"]["name"])
        if model_name == "deeplabv3plus" and not (
            root / "src/onestroke_model/models/deeplabv3plus.py"
        ).is_file():
            raise ValueError("real DeepLabV3+ implementation is missing")
        output_dir = Path(str(config["output_dir"]))
        completed = _is_complete(root, output_dir)
        runs.append(
            {
                "experiment_name": config["experiment_name"],
                "split_name": relative_config.name.split(f"_{model_name}", 1)[0],
                "model_name": model_name,
                "seed": int(config["seed"]),
                "config": relative_config.as_posix(),
                "config_sha256": sha256_file(config_path),
                "output_dir": output_dir.as_posix(),
                "status": "COMPLETED" if completed else "READY",
                "data_contract": contract,
                "commands": _commands(relative_config, output_dir),
            }
        )
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now_iso(),
        "project_root": str(root),
        "training_executed": False,
        "run_count": len(runs),
        "completed_run_count": sum(run["status"] == "COMPLETED" for run in runs),
        "ready_run_count": sum(run["status"] == "READY" for run in runs),
        "runs": runs,
        "policies": {
            "resume": "complete train+val-calibration+test runs are skipped",
            "threshold_calibration": "validation only",
            "test_model_selection": False,
            "failed_seed_removal": False,
        },
    }


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
    tolerance = metrics.get("keypoint_tolerance", {})
    if name.startswith("keypoint_f1_tolerance_") and isinstance(tolerance, dict):
        radius = name.rsplit("_", 1)[-1]
        payload = tolerance.get(radius)
        if isinstance(payload, dict) and payload.get("f1") is not None:
            return float(payload["f1"])
    return None


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize_task1(plan: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    root = Path(plan["project_root"])
    rows: list[dict[str, object]] = []
    missing: list[str] = []
    for run in plan["runs"]:
        output = root / run["output_dir"]
        metrics_path = output / "test_metrics.json"
        thresholds_path = output / "thresholds_val.json"
        checkpoint_path = output / "checkpoints/best.pt"
        if not all(path.is_file() for path in (metrics_path, thresholds_path, checkpoint_path)):
            missing.append(run["experiment_name"])
            continue
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
        if metrics.get("split") != "test":
            raise ValueError(f"non-test result: {metrics_path}")
        if thresholds.get("calibration_split") != "val":
            raise ValueError(f"non-validation threshold calibration: {thresholds_path}")
        row: dict[str, object] = {
            "experiment_name": run["experiment_name"],
            "split_name": run["split_name"],
            "model_name": run["model_name"],
            "seed": run["seed"],
            "config_sha256": run["config_sha256"],
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "thresholds_sha256": sha256_file(thresholds_path),
            "test_metrics_sha256": sha256_file(metrics_path),
        }
        for metric in SUMMARY_METRICS:
            value = _extract_metric(metrics, metric)
            row[metric] = "" if value is None else value
        rows.append(row)

    grouped: defaultdict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["split_name"]), str(row["model_name"]))].append(row)
    summary_rows: list[dict[str, object]] = []
    for (split_name, model_name), model_rows in sorted(grouped.items()):
        summary: dict[str, object] = {
            "split_name": split_name,
            "model_name": model_name,
            "completed_seed_count": len(model_rows),
            "seeds": ";".join(str(row["seed"]) for row in model_rows),
        }
        for metric in SUMMARY_METRICS:
            values = [
                float(row[metric])
                for row in model_rows
                if row.get(metric) not in ("", None)
            ]
            summary[f"{metric}_mean"] = statistics.mean(values) if values else ""
            summary[f"{metric}_std"] = (
                statistics.stdev(values) if len(values) >= 2 else ""
            )
        summary_rows.append(summary)

    per_seed_fields = [
        "experiment_name",
        "split_name",
        "model_name",
        "seed",
        "config_sha256",
        "checkpoint_sha256",
        "thresholds_sha256",
        "test_metrics_sha256",
        *SUMMARY_METRICS,
    ]
    summary_fields = ["split_name", "model_name", "completed_seed_count", "seeds"]
    for metric in SUMMARY_METRICS:
        summary_fields.extend((f"{metric}_mean", f"{metric}_std"))
    output = Path(output_dir)
    _write_csv(output / "results_per_seed.csv", rows, per_seed_fields)
    _write_csv(output / "results_summary.csv", summary_rows, summary_fields)
    result = {
        "schema_version": 1,
        "generated_at_utc": utc_now_iso(),
        "completed_run_count": len(rows),
        "missing_experiments": missing,
        "test_used_for_model_selection": False,
        "threshold_calibration_split": "val",
    }
    (output / "summary_manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def run_task1(
    project_root: str | Path,
    *,
    execute: bool = False,
    output_dir: str | Path = "artifacts/paper_ijdar/task1",
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    plan = build_task1_plan(root)
    output = root / output_dir
    output.mkdir(parents=True, exist_ok=True)
    (output / "execution_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not execute:
        return plan

    plan["training_executed"] = True
    for run in plan["runs"]:
        if run["status"] == "COMPLETED":
            continue
        run_output = root / run["output_dir"]
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
                _run_command(
                    command,
                    cwd=root,
                    log_path=run_output / "benchmark.log",
                )
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
    refreshed = build_task1_plan(root)
    return {"plan": refreshed, "summary": summarize_task1(refreshed, output)}
